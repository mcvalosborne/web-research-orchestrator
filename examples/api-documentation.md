# Example: Technical Documentation Crawl

**Goal:** Extract all API endpoints from a documentation site

---

## Phase 1: Sitemap Discovery

**Initial Checks:**

```
CHECK ROBOTS.TXT:
https://docs.example.com/robots.txt

Response:
User-agent: *
Allow: /
Sitemap: https://docs.example.com/sitemap.xml

CHECK SITEMAP:
https://docs.example.com/sitemap.xml

IDENTIFIED URL PATTERNS:
- /api/v1/* - 45 pages
- /guides/* - 12 pages
- /reference/* - 30 pages
- /changelog/* - 20 pages (exclude)
```

---

## Phase 2: Crawl Strategy

**Option A: Firecrawl (if available)**

```
FIRECRAWL TOOL:
- action: "crawl"
- url: "https://docs.example.com/api"
- options:
  - maxPages: 100
  - includePaths: ["/api/*", "/reference/*"]
  - excludePaths: ["/changelog/*"]
```

**Option B: Parallel Haiku Workers**

```
Batch URLs into 5 workers:
- Worker 1: /api/v1/users, /api/v1/auth, /api/v1/teams (9 pages)
- Worker 2: /api/v1/projects, /api/v1/tasks (9 pages)
- Worker 3: /api/v1/files, /api/v1/comments (9 pages)
- Worker 4: /api/v1/webhooks, /api/v1/events (9 pages)
- Worker 5: /api/v1/billing, /api/v1/admin (9 pages)
```

---

## Phase 3: Worker Output (per endpoint page)

**Worker 1 Sample Output:**

```json
{
  "endpoints": [
    {
      "path": "/api/v1/users",
      "methods": ["GET", "POST"],
      "description": "List and create users",
      "authentication": "Bearer token required",
      "parameters": {
        "GET": {
          "query": [
            {"name": "limit", "type": "integer", "required": false, "default": 20},
            {"name": "offset", "type": "integer", "required": false, "default": 0},
            {"name": "status", "type": "string", "required": false, "enum": ["active", "inactive"]}
          ]
        },
        "POST": {
          "body": [
            {"name": "email", "type": "string", "required": true},
            {"name": "name", "type": "string", "required": true},
            {"name": "role", "type": "string", "required": false, "default": "member"}
          ]
        }
      },
      "responses": {
        "200": "Success - returns user list or created user",
        "401": "Unauthorized",
        "422": "Validation error"
      },
      "rate_limit": "100 requests/minute"
    },
    {
      "path": "/api/v1/users/{id}",
      "methods": ["GET", "PUT", "DELETE"],
      "description": "Get, update, or delete a specific user",
      "authentication": "Bearer token required",
      "parameters": {
        "path": [
          {"name": "id", "type": "string", "required": true, "description": "User ID"}
        ],
        "PUT": {
          "body": [
            {"name": "email", "type": "string", "required": false},
            {"name": "name", "type": "string", "required": false},
            {"name": "role", "type": "string", "required": false}
          ]
        }
      }
    }
  ]
}
```

---

## Phase 4: Aggregated Output

```json
{
  "api_name": "Example API",
  "version": "v1",
  "base_url": "https://api.example.com/v1",
  "documentation_url": "https://docs.example.com/api",
  "extracted_at": "2024-01-15T14:30:00Z",

  "authentication": {
    "type": "Bearer token",
    "header": "Authorization",
    "format": "Bearer {token}",
    "obtain_token": "/api/v1/auth/token"
  },

  "global_rate_limits": {
    "requests_per_minute": 100,
    "requests_per_day": 10000
  },

  "endpoints": [
    {
      "category": "Users",
      "endpoints": [
        {
          "path": "/users",
          "methods": ["GET", "POST"],
          "description": "User management"
        },
        {
          "path": "/users/{id}",
          "methods": ["GET", "PUT", "DELETE"],
          "description": "Single user operations"
        }
      ]
    },
    {
      "category": "Authentication",
      "endpoints": [
        {
          "path": "/auth/token",
          "methods": ["POST"],
          "description": "Obtain access token"
        },
        {
          "path": "/auth/refresh",
          "methods": ["POST"],
          "description": "Refresh access token"
        }
      ]
    },
    {
      "category": "Projects",
      "endpoints": [
        {
          "path": "/projects",
          "methods": ["GET", "POST"],
          "description": "Project management"
        },
        {
          "path": "/projects/{id}",
          "methods": ["GET", "PUT", "DELETE"],
          "description": "Single project operations"
        },
        {
          "path": "/projects/{id}/members",
          "methods": ["GET", "POST", "DELETE"],
          "description": "Project membership"
        }
      ]
    }
  ],

  "total_endpoints": 45,
  "categories": 8,

  "summary": {
    "crud_endpoints": 32,
    "action_endpoints": 8,
    "webhook_endpoints": 5,
    "auth_required": 43,
    "public_endpoints": 2
  }
}
```

---

## Phase 5: Generated SDK Outline

Based on the extracted endpoints, generate SDK method signatures:

```typescript
// Auto-generated from API documentation crawl

interface ExampleAPIClient {
  // Users
  users: {
    list(params?: { limit?: number; offset?: number; status?: string }): Promise<User[]>;
    create(data: { email: string; name: string; role?: string }): Promise<User>;
    get(id: string): Promise<User>;
    update(id: string, data: Partial<User>): Promise<User>;
    delete(id: string): Promise<void>;
  };

  // Projects
  projects: {
    list(params?: { limit?: number; offset?: number }): Promise<Project[]>;
    create(data: CreateProjectInput): Promise<Project>;
    get(id: string): Promise<Project>;
    update(id: string, data: Partial<Project>): Promise<Project>;
    delete(id: string): Promise<void>;
    members: {
      list(projectId: string): Promise<Member[]>;
      add(projectId: string, userId: string): Promise<Member>;
      remove(projectId: string, userId: string): Promise<void>;
    };
  };

  // ... etc
}
```

---

## Execution Stats

- **Pages Crawled:** 45
- **Endpoints Extracted:** 45
- **Workers Used:** 5 Haiku agents
- **Total Time:** ~120 seconds
- **Estimated Cost:** $0.015
