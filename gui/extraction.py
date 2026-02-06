"""
Multi-Strategy Extraction Module

Implements a layered extraction approach:
1. CSS/XPath selectors (fast, free)
2. Regex patterns (fast, free)
3. LLM extraction (slow, costs money)

This reduces costs by 60%+ by only using LLM when simpler methods fail.
"""

import re
import json
from typing import Any, Optional
from bs4 import BeautifulSoup
try:
    from pydantic import BaseModel, Field, field_validator, ValidationError
    PYDANTIC_AVAILABLE = True
except ImportError:
    # Fallback for older pydantic
    from pydantic import BaseModel, Field, validator as field_validator, ValidationError
    PYDANTIC_AVAILABLE = True
except:
    PYDANTIC_AVAILABLE = False
from datetime import datetime
import httpx


# ============ Pydantic Validation Models ============

class PriceData(BaseModel):
    """Validated price extraction."""
    amount: float = Field(..., gt=0, description="Price amount must be positive")
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    period: Optional[str] = Field(default=None, description="Billing period (monthly, yearly, etc.)")

    @field_validator('amount', mode='before')
    @classmethod
    def parse_amount(cls, v):
        if isinstance(v, str):
            # Remove currency symbols and commas
            cleaned = re.sub(r'[^\d.]', '', v)
            return float(cleaned) if cleaned else 0
        return v


class ProductData(BaseModel):
    """Validated product/service data."""
    name: str = Field(..., min_length=1, max_length=500)
    price: Optional[PriceData] = None
    description: Optional[str] = Field(default=None, max_length=5000)
    features: list[str] = Field(default_factory=list)
    url: Optional[str] = None

    @field_validator('name')
    @classmethod
    def clean_name(cls, v):
        return v.strip() if v else v


class ExtractedData(BaseModel):
    """Container for extracted data with metadata."""
    data: dict = Field(default_factory=dict)
    source_url: str
    extraction_method: str = Field(..., description="css|regex|llm")
    confidence: float = Field(default=0.5, ge=0, le=1)
    timestamp: datetime = Field(default_factory=datetime.now)
    fields_extracted: list[str] = Field(default_factory=list)
    fields_missing: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)

    @property
    def completeness(self) -> float:
        """Calculate data completeness percentage."""
        total = len(self.fields_extracted) + len(self.fields_missing)
        if total == 0:
            return 0
        return len(self.fields_extracted) / total


class ValidationResult(BaseModel):
    """Result of validating extracted data."""
    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    cleaned_data: dict = Field(default_factory=dict)
    confidence_score: float = Field(default=0.5, ge=0, le=1)


# ============ Regex Patterns for Common Data Types ============

REGEX_PATTERNS = {
    'price': [
        r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:/|per)\s*(?:mo|month|yr|year|user))?',
        r'(?:USD|EUR|GBP)\s*[\d,]+(?:\.\d{2})?',
        r'[\d,]+(?:\.\d{2})?\s*(?:USD|EUR|GBP)',
        r'€[\d,]+(?:\.\d{2})?',
        r'£[\d,]+(?:\.\d{2})?',
    ],
    'email': [
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    ],
    'phone': [
        r'\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}',
        r'\+[0-9]{1,3}[-.\s]?[0-9]{6,14}',
    ],
    'date': [
        r'\d{4}-\d{2}-\d{2}',
        r'\d{1,2}/\d{1,2}/\d{2,4}',
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}',
    ],
    'percentage': [
        r'\d+(?:\.\d+)?%',
    ],
    'url': [
        r'https?://[^\s<>"{}|\\^`\[\]]+',
    ],
}


# ============ CSS Selectors for Common Page Structures ============

CSS_SELECTORS = {
    'title': [
        'h1',
        '[class*="title"]',
        '[class*="heading"]',
        'meta[property="og:title"]',
        'title',
    ],
    'price': [
        '[class*="price"]',
        '[class*="cost"]',
        '[class*="amount"]',
        '[data-price]',
        '.pricing',
        '#price',
    ],
    'description': [
        'meta[name="description"]',
        'meta[property="og:description"]',
        '[class*="description"]',
        '[class*="summary"]',
        '[class*="intro"]',
        'p:first-of-type',
    ],
    'features': [
        '[class*="feature"] li',
        '[class*="benefit"] li',
        '.features li',
        'ul[class*="feature"] li',
        '[class*="checklist"] li',
    ],
    'product_name': [
        '[class*="product-name"]',
        '[class*="product-title"]',
        '[itemprop="name"]',
        'h1[class*="product"]',
    ],
}


# ============ Multi-Strategy Extractor ============

class MultiStrategyExtractor:
    """
    Extracts data using multiple strategies in order of cost/speed:
    1. CSS/XPath selectors (free, fast)
    2. Regex patterns (free, fast)
    3. LLM extraction (costly, slow)
    """

    def __init__(self, html_content: str, url: str):
        self.html = html_content
        self.url = url
        # Try lxml first, fall back to html.parser
        if html_content:
            try:
                self.soup = BeautifulSoup(html_content, 'lxml')
            except:
                self.soup = BeautifulSoup(html_content, 'html.parser')
        else:
            self.soup = None
        self.extraction_log = []

    def extract_with_css(self, field_name: str) -> tuple[Optional[str], float]:
        """Try to extract using CSS selectors. Returns (value, confidence)."""
        if not self.soup:
            return None, 0

        selectors = CSS_SELECTORS.get(field_name, [])

        for selector in selectors:
            try:
                if selector.startswith('meta'):
                    # Handle meta tags specially
                    element = self.soup.select_one(selector)
                    if element:
                        value = element.get('content', '')
                        if value:
                            self.extraction_log.append(f"CSS: Found {field_name} via {selector}")
                            return value.strip(), 0.9
                else:
                    elements = self.soup.select(selector)
                    if elements:
                        if field_name == 'features':
                            # Return list for features
                            values = [el.get_text(strip=True) for el in elements if el.get_text(strip=True)]
                            if values:
                                self.extraction_log.append(f"CSS: Found {len(values)} {field_name} via {selector}")
                                return values, 0.85
                        else:
                            value = elements[0].get_text(strip=True)
                            if value:
                                self.extraction_log.append(f"CSS: Found {field_name} via {selector}")
                                return value, 0.85
            except Exception as e:
                continue

        return None, 0

    def extract_with_regex(self, field_name: str, text: Optional[str] = None) -> tuple[Optional[Any], float]:
        """Try to extract using regex patterns. Returns (value, confidence)."""
        if text is None:
            text = self.soup.get_text() if self.soup else self.html

        if not text:
            return None, 0

        patterns = REGEX_PATTERNS.get(field_name, [])

        for pattern in patterns:
            try:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    self.extraction_log.append(f"Regex: Found {field_name} with pattern {pattern[:30]}...")
                    # Return first match for single values, all matches for lists
                    if field_name in ['features', 'email', 'phone']:
                        return list(set(matches)), 0.75
                    return matches[0], 0.75
            except Exception:
                continue

        return None, 0

    def extract_field(self, field_name: str, field_type: str = 'text') -> tuple[Optional[Any], float, str]:
        """
        Extract a field using multi-strategy approach.
        Returns (value, confidence, method_used).
        """
        # Strategy 1: CSS selectors
        value, confidence = self.extract_with_css(field_name)
        if value and confidence > 0.7:
            return value, confidence, 'css'

        # Strategy 2: Regex patterns
        regex_value, regex_confidence = self.extract_with_regex(field_name)
        if regex_value and regex_confidence > confidence:
            return regex_value, regex_confidence, 'regex'

        # Return best result so far (or None if nothing found)
        if value:
            return value, confidence, 'css'
        if regex_value:
            return regex_value, regex_confidence, 'regex'

        return None, 0, 'none'

    def extract_all(self, schema: dict) -> ExtractedData:
        """
        Extract all fields defined in schema using multi-strategy approach.
        Returns ExtractedData with results and metadata.
        """
        extracted = {}
        fields_extracted = []
        fields_missing = []
        total_confidence = 0
        methods_used = []

        for field_name, field_desc in schema.items():
            # Determine field type from description
            field_type = 'text'
            if 'price' in field_name.lower() or 'cost' in field_name.lower():
                field_type = 'price'
            elif 'feature' in field_name.lower() or isinstance(field_desc, list):
                field_type = 'list'
            elif 'email' in field_name.lower():
                field_type = 'email'
            elif 'date' in field_name.lower():
                field_type = 'date'

            value, confidence, method = self.extract_field(field_name, field_type)

            if value is not None:
                extracted[field_name] = value
                fields_extracted.append(field_name)
                total_confidence += confidence
                methods_used.append(method)
            else:
                fields_missing.append(field_name)

        # Calculate overall confidence
        avg_confidence = total_confidence / len(schema) if schema else 0

        # Determine primary extraction method
        if methods_used:
            primary_method = max(set(methods_used), key=methods_used.count)
        else:
            primary_method = 'none'

        return ExtractedData(
            data=extracted,
            source_url=self.url,
            extraction_method=primary_method,
            confidence=avg_confidence,
            fields_extracted=fields_extracted,
            fields_missing=fields_missing
        )


# ============ Validation Functions ============

def validate_extracted_data(data: dict, schema: dict) -> ValidationResult:
    """
    Validate extracted data against expected schema and business rules.
    """
    errors = []
    warnings = []
    cleaned = {}

    for field_name, field_desc in schema.items():
        value = data.get(field_name)

        if value is None:
            warnings.append(f"Missing field: {field_name}")
            continue

        # Type-specific validation
        if 'price' in field_name.lower():
            try:
                if isinstance(value, str):
                    # Parse price string
                    amount_match = re.search(r'[\d,]+(?:\.\d{2})?', value)
                    if amount_match:
                        amount = float(amount_match.group().replace(',', ''))
                        if amount <= 0:
                            errors.append(f"{field_name}: Price must be positive")
                        else:
                            cleaned[field_name] = {
                                'amount': amount,
                                'raw': value,
                                'currency': 'USD' if '$' in value else 'EUR' if '€' in value else 'GBP' if '£' in value else 'USD'
                            }
                    else:
                        errors.append(f"{field_name}: Could not parse price from '{value}'")
                elif isinstance(value, (int, float)):
                    if value <= 0:
                        errors.append(f"{field_name}: Price must be positive")
                    else:
                        cleaned[field_name] = {'amount': value, 'currency': 'USD'}
            except Exception as e:
                errors.append(f"{field_name}: Validation error - {str(e)}")

        elif isinstance(field_desc, list) or 'feature' in field_name.lower():
            # List field validation
            if isinstance(value, list):
                cleaned[field_name] = [v for v in value if v and str(v).strip()]
                if len(cleaned[field_name]) == 0:
                    warnings.append(f"{field_name}: List is empty after cleaning")
            elif isinstance(value, str):
                # Try to split string into list
                cleaned[field_name] = [v.strip() for v in value.split(',') if v.strip()]

        else:
            # String field validation
            if isinstance(value, str):
                cleaned_value = value.strip()
                if len(cleaned_value) == 0:
                    warnings.append(f"{field_name}: Empty string after cleaning")
                elif len(cleaned_value) > 10000:
                    warnings.append(f"{field_name}: Very long value ({len(cleaned_value)} chars)")
                    cleaned[field_name] = cleaned_value[:10000]
                else:
                    cleaned[field_name] = cleaned_value
            else:
                cleaned[field_name] = value

    # Calculate confidence based on validation results
    total_fields = len(schema)
    valid_fields = len(cleaned)
    error_penalty = len(errors) * 0.1
    warning_penalty = len(warnings) * 0.05

    confidence = max(0, (valid_fields / total_fields) - error_penalty - warning_penalty) if total_fields > 0 else 0

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        cleaned_data=cleaned,
        confidence_score=min(1.0, confidence)
    )


def validate_url(url: str) -> bool:
    """Validate URL format."""
    pattern = r'^https?://[^\s<>"{}|\\^`\[\]]+$'
    return bool(re.match(pattern, url))


def validate_price_string(price_str: str) -> Optional[float]:
    """Extract and validate price from string."""
    if not price_str:
        return None
    match = re.search(r'[\d,]+(?:\.\d{2})?', price_str)
    if match:
        try:
            return float(match.group().replace(',', ''))
        except ValueError:
            return None
    return None


# ============ Content Fetching ============

async def fetch_html(url: str, timeout: int = 30) -> tuple[Optional[str], Optional[str]]:
    """
    Fetch HTML content from URL.
    Returns (html_content, error_message).
    """
    if not validate_url(url):
        return None, "Invalid URL format"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            })
            response.raise_for_status()
            return response.text, None
    except httpx.TimeoutException:
        return None, "Request timed out"
    except httpx.HTTPStatusError as e:
        return None, f"HTTP {e.response.status_code}"
    except Exception as e:
        return None, str(e)


def fetch_html_sync(url: str, timeout: int = 30) -> tuple[Optional[str], Optional[str]]:
    """
    Synchronous version of fetch_html.
    Returns (html_content, error_message).
    """
    if not validate_url(url):
        return None, "Invalid URL format"

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = client.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            })
            response.raise_for_status()
            return response.text, None
    except httpx.TimeoutException:
        return None, "Request timed out"
    except httpx.HTTPStatusError as e:
        return None, f"HTTP {e.response.status_code}"
    except Exception as e:
        return None, str(e)


# ============ Extraction Pipeline ============

def extract_with_fallback(
    url: str,
    schema: dict,
    html_content: Optional[str] = None,
    llm_extractor: Optional[callable] = None,
    use_llm_threshold: float = 0.5
) -> ExtractedData:
    """
    Full extraction pipeline with CSS/Regex first, LLM fallback.

    Args:
        url: URL to extract from
        schema: Dictionary defining fields to extract
        html_content: Pre-fetched HTML (optional, will fetch if None)
        llm_extractor: Callable for LLM extraction (takes url, schema, returns dict)
        use_llm_threshold: Use LLM if confidence below this threshold

    Returns:
        ExtractedData with results and metadata
    """
    # Fetch HTML if not provided
    if html_content is None:
        html_content, error = fetch_html_sync(url)
        if error:
            # Can't fetch HTML, try LLM directly if available
            if llm_extractor:
                try:
                    llm_result = llm_extractor(url, schema)
                    return ExtractedData(
                        data=llm_result,
                        source_url=url,
                        extraction_method='llm',
                        confidence=0.6,
                        fields_extracted=list(llm_result.keys()),
                        fields_missing=[f for f in schema if f not in llm_result],
                        validation_errors=[f"HTML fetch failed: {error}"]
                    )
                except Exception as e:
                    pass

            return ExtractedData(
                data={},
                source_url=url,
                extraction_method='none',
                confidence=0,
                fields_extracted=[],
                fields_missing=list(schema.keys()),
                validation_errors=[f"Failed to fetch URL: {error}"]
            )

    # Try multi-strategy extraction
    extractor = MultiStrategyExtractor(html_content, url)
    result = extractor.extract_all(schema)

    # If confidence is low and LLM is available, use LLM for missing fields
    if result.confidence < use_llm_threshold and llm_extractor and result.fields_missing:
        try:
            # Only extract missing fields with LLM
            missing_schema = {k: schema[k] for k in result.fields_missing}
            llm_result = llm_extractor(url, missing_schema)

            # Merge results
            for field, value in llm_result.items():
                if value is not None and field not in result.data:
                    result.data[field] = value
                    result.fields_extracted.append(field)
                    result.fields_missing.remove(field)

            # Update confidence (weighted average)
            css_weight = len([f for f in result.fields_extracted if f not in llm_result]) / len(schema) if schema else 0
            llm_weight = len(llm_result) / len(schema) if schema else 0
            result.confidence = (result.confidence * css_weight + 0.7 * llm_weight)
            result.extraction_method = 'hybrid'

        except Exception as e:
            result.validation_errors.append(f"LLM extraction failed: {str(e)}")

    # Validate the results
    validation = validate_extracted_data(result.data, schema)
    if not validation.is_valid:
        result.validation_errors.extend(validation.errors)
    result.data = validation.cleaned_data
    result.confidence = min(result.confidence, validation.confidence_score)

    return result


# ============ Utility Functions ============

def get_extraction_stats(results: list[ExtractedData]) -> dict:
    """
    Get statistics about extraction results.
    """
    if not results:
        return {}

    methods = [r.extraction_method for r in results]
    confidences = [r.confidence for r in results]
    completeness = [r.completeness for r in results]

    return {
        'total_extractions': len(results),
        'method_breakdown': {
            'css': methods.count('css'),
            'regex': methods.count('regex'),
            'llm': methods.count('llm'),
            'hybrid': methods.count('hybrid'),
            'none': methods.count('none'),
        },
        'average_confidence': sum(confidences) / len(confidences),
        'average_completeness': sum(completeness) / len(completeness),
        'successful': len([r for r in results if r.confidence > 0.5]),
        'failed': len([r for r in results if r.confidence <= 0.5]),
        'cost_savings_estimate': f"{(methods.count('css') + methods.count('regex')) / len(methods) * 100:.1f}%"
    }
