# Pagination and Rate Limit Handling

Comprehensive guide to cursor-based pagination (GraphQL) and offset pagination (REST).

---

## GraphQL Cursor-Based Pagination

### How It Works

GraphQL uses **cursor-based pagination** — each page returns an opaque cursor string that points to the next set of results. This is more reliable than offset pagination (no duplicate/skipped items when data changes).

**Every paginated connection requires:**
1. `first: N` (1-100) — number of items per page
2. `after: $cursor` — cursor from previous page (null for first page)
3. `pageInfo { hasNextPage endCursor }` — **must** be included in query

### Pagination Loop Pattern

```graphql
query GetIssues($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(first: 100, after: $cursor, states: [OPEN, CLOSED]) {
      totalCount
      pageInfo {
        hasNextPage       # false on last page
        endCursor         # pass as $cursor for next page
      }
      nodes {
        number title state createdAt
      }
    }
  }
  rateLimit { remaining cost resetAt }
}
```

**Algorithm:**
1. Set `cursor = null`
2. Execute query with current cursor
3. Collect `nodes` from response
4. Check `pageInfo.hasNextPage`
   - If `true`: set `cursor = pageInfo.endCursor`, goto step 2
   - If `false`: done

### Python Implementation

```python
import requests
import time
import json

ENDPOINT = "https://api.github.com/graphql"

def graphql_paginated(token, query, variables, connection_path, max_pages=None):
    """Fetch all pages from a GraphQL connection.

    Args:
        token: GitHub personal access token
        query: GraphQL query string (must accept $cursor: String)
        variables: Base variables dict (cursor will be injected)
        connection_path: Dot-separated path to the connection object
            e.g., "repository.issues"
            e.g., "repository.defaultBranchRef.target.history"
            e.g., "search"
        max_pages: Optional page limit

    Returns:
        List of all nodes across all pages
    """
    headers = {
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
    }
    all_nodes = []
    cursor = None
    page = 0

    while True:
        if max_pages and page >= max_pages:
            break

        variables["cursor"] = cursor
        resp = requests.post(ENDPOINT,
                             json={"query": query, "variables": variables},
                             headers=headers)

        # Handle rate limiting
        if resp.status_code == 403:
            reset_ts = int(resp.headers.get("X-RateLimit-Reset", 0))
            wait = max(reset_ts - time.time(), 5)
            print(f"Rate limited. Waiting {wait:.0f}s...")
            time.sleep(wait + 1)
            continue

        resp.raise_for_status()
        data = resp.json()

        if "errors" in data:
            print(f"GraphQL errors: {data['errors']}")
            if data.get("data") is None:
                break

        # Navigate to the connection object
        connection = data["data"]
        for key in connection_path.split("."):
            connection = connection[key]

        nodes = connection.get("nodes", [])
        all_nodes.extend(nodes)
        page += 1

        page_info = connection["pageInfo"]
        total = connection.get("totalCount", "?")
        rate = data["data"].get("rateLimit", {})

        print(f"Page {page}: {len(nodes)} items "
              f"(total: {len(all_nodes)}/{total}) | "
              f"rate: {rate.get('remaining', '?')} remaining")

        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]

        # Safety: pause if rate limit is low
        if rate.get("remaining", 100) < 50:
            print(f"Low rate limit ({rate['remaining']}). Waiting 60s...")
            time.sleep(60)

    return all_nodes
```

### Usage Examples

```python
# Fetch all issues
QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(first: 100, after: $cursor, states: [OPEN, CLOSED]) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { number title state createdAt }
    }
  }
  rateLimit { remaining cost resetAt }
}
"""
issues = graphql_paginated(token, QUERY,
    {"owner": "pytorch", "name": "pytorch"},
    "repository.issues")

# Fetch commits with date range
COMMIT_QUERY = """
query($owner: String!, $name: String!, $cursor: String, $since: GitTimestamp) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef { target { ... on Commit {
      history(first: 100, after: $cursor, since: $since) {
        totalCount
        pageInfo { hasNextPage endCursor }
        nodes { oid messageHeadline committedDate author { name user { login } } }
      }
    }}}
  }
  rateLimit { remaining cost resetAt }
}
"""
commits = graphql_paginated(token, COMMIT_QUERY,
    {"owner": "pytorch", "name": "pytorch", "since": "2024-01-01T00:00:00Z"},
    "repository.defaultBranchRef.target.history")

# Search repos
SEARCH_QUERY = """
query($q: String!, $cursor: String) {
  search(query: $q, type: REPOSITORY, first: 100, after: $cursor) {
    repositoryCount
    pageInfo { hasNextPage endCursor }
    nodes { ... on Repository { nameWithOwner stargazerCount } }
  }
  rateLimit { remaining cost resetAt }
}
"""
repos = graphql_paginated(token, SEARCH_QUERY,
    {"q": "topic:deep-learning stars:>=500"},
    "search", max_pages=10)
```

### `gh` CLI Auto-Pagination

The `gh api graphql --paginate` flag handles cursor pagination automatically.

**Requirements:**
1. Cursor variable **must** be named `$endCursor` (not `$cursor`)
2. Query **must** include `pageInfo { hasNextPage endCursor }`
3. Use `--slurp` to merge all pages into one JSON array

```bash
# Paginate all issues
gh api graphql --paginate --slurp -f query='
  query($endCursor: String) {
    repository(owner: "pytorch", name: "pytorch") {
      issues(first: 100, after: $endCursor, states: [OPEN, CLOSED]) {
        pageInfo { hasNextPage endCursor }
        nodes { number title state createdAt }
      }
    }
  }
' > all_issues.json

# Paginate commits
gh api graphql --paginate --slurp -f query='
  query($endCursor: String) {
    repository(owner: "pytorch", name: "pytorch") {
      defaultBranchRef { target { ... on Commit {
        history(first: 100, after: $endCursor) {
          pageInfo { hasNextPage endCursor }
          nodes { oid messageHeadline committedDate author { name } }
        }
      }}}
    }
  }
' > all_commits.json

# Paginate search with TSV output
gh api graphql --paginate -f query='
  query($endCursor: String) {
    search(query: "topic:ml stars:>=100", type: REPOSITORY,
           first: 100, after: $endCursor) {
      pageInfo { hasNextPage endCursor }
      nodes { ... on Repository { nameWithOwner stargazerCount } }
    }
  }
' --jq '.data.search.nodes[] | [.nameWithOwner, .stargazerCount] | @tsv'
```

### Nested Pagination

When a connection inside a paginated connection needs its own pagination (e.g., comments inside issues), handle it in two passes:

**Pass 1**: Fetch all issues with `comments(first: 5)` inline
**Pass 2**: For issues where `comments.totalCount > 5`, fetch remaining comments:

```graphql
query GetIssueComments($owner: String!, $name: String!,
                       $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
      comments(first: 100, after: $cursor) {
        totalCount
        pageInfo { hasNextPage endCursor }
        nodes {
          body
          createdAt
          author { login }
        }
      }
    }
  }
  rateLimit { remaining cost resetAt }
}
```

---

## REST Offset Pagination (for REST-Only Endpoints)

### How It Works

REST endpoints use `page` and `per_page` parameters. The `Link` header provides URLs for next/previous pages.

**Key parameters:**
- `per_page` — 1-100 (default: 30). Always use 100 to minimize requests.
- `page` — Page number (default: 1)

### Link Header

```
Link: <https://api.github.com/repos/o/r/issues?page=2&per_page=100>; rel="next",
      <https://api.github.com/repos/o/r/issues?page=14&per_page=100>; rel="last"
```

| rel | Meaning |
|-----|---------|
| `next` | Next page URL |
| `prev` | Previous page URL |
| `first` | First page URL |
| `last` | Last page URL |

Stop when `rel="next"` is absent.

### Python Implementation (REST)

```python
def rest_paginated(token, url, params=None):
    """Paginate through a REST endpoint using Link headers."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params = dict(params or {})
    params["per_page"] = 100
    all_items = []

    while url:
        resp = requests.get(url, headers=headers, params=params)

        if resp.status_code in (403, 429):
            reset_ts = int(resp.headers.get("X-RateLimit-Reset", 0))
            wait = max(reset_ts - time.time(), 5)
            print(f"Rate limited. Waiting {wait:.0f}s...")
            time.sleep(wait + 1)
            continue

        if resp.status_code == 202:
            print("Stats computing, retrying in 3s...")
            time.sleep(3)
            continue

        if resp.status_code == 204 or resp.status_code != 200:
            break

        data = resp.json()
        if isinstance(data, list):
            if not data:
                break
            all_items.extend(data)
        else:
            all_items.append(data)

        # Follow Link header
        url = None
        params = {}  # Link URLs include params
        for part in resp.headers.get("Link", "").split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
                break

    return all_items
```

---

## Rate Limits

### GraphQL Rate Limits

| Category | Limit |
|----------|-------|
| Authenticated user (PAT/OAuth) | 5,000 points/hour |
| GitHub Enterprise Cloud | 10,000 points/hour |
| GitHub App installation | 5,000 (bonus up to 12,500) |
| GitHub Actions | 1,000 per repo |
| Burst limit | 2,000 points/minute |
| Max concurrent requests | 100 (REST + GraphQL combined) |
| Query timeout | 10 seconds |

**Point costs:**
- Query (no mutation): **1 point**
- Mutation: **5 points**
- Complex queries: server estimates total nested API calls / 100 (minimum 1)

### REST Rate Limits

| Category | Limit |
|----------|-------|
| Authenticated (Core API) | 5,000 requests/hour |
| Unauthenticated | 60 requests/hour |
| Search | 30 requests/minute |
| Code search | 10 requests/minute |

### Checking Rate Limit

**GraphQL** (include in every query):
```graphql
rateLimit {
  limit         # Max points per hour
  remaining     # Points left
  cost          # Points this query consumed
  resetAt       # ISO 8601 reset time
  used          # Points used so far
  nodeCount     # Nodes returned
}
```

**Standalone check:**
```graphql
query { rateLimit { limit remaining resetAt used } }
```

**REST** (does not count against limit):
```bash
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
  "https://api.github.com/rate_limit"
```

### REST Response Headers (on every request)

- `X-RateLimit-Limit` — Max requests for this category
- `X-RateLimit-Remaining` — Requests remaining
- `X-RateLimit-Reset` — Unix timestamp when limit resets
- `X-RateLimit-Used` — Requests used in current window
- `X-RateLimit-Resource` — Category (`core`, `search`, `graphql`)

### Budget Planning: GraphQL vs REST

| Operation | REST Requests | GraphQL Points | Savings |
|-----------|--------------|----------------|---------|
| Repo metadata + topics + langs + README | 4 | **1** | 75% |
| 1,000 issues (pagination only) | 10 | **10** | Same |
| 1,000 issues + 5 comments each | 1,010 | **10** | **99%** |
| 500 PRs + files + reviews | 1,500 | **50** | **97%** |
| 10-repo comparison | 40 | **1** | **97.5%** |
| Full repo mining (metadata + 5k commits + 2k issues + 1k PRs) | ~300 | **~90** | **70%** |

### Best Practices

1. **Always authenticate** — GraphQL requires it; REST gets 5,000/hr vs 60
2. **Include `rateLimit` in every GraphQL query** — monitor budget in real time
3. **Request only needed fields** — smaller responses, lower point cost
4. **Use aliases for batch queries** — 10 repos = 1 point, not 10
5. **Use `gh --paginate`** for CLI scripts — automatic cursor handling
6. **Cache to disk** — save raw JSON; avoid re-fetching unchanged data
7. **Use conditional requests (REST)** — `If-None-Match` with ETags for 304 responses
8. **Respect burst limits** — max 2,000 points/minute; add small delays in loops
9. **Date-partition searches** — search cap is 1,000 results; split by `created:` ranges
10. **Start with small `first:` for nested connections** — `comments(first: 5)` inline, paginate separately if needed

### Handling Rate Limit Errors

**GraphQL**: Returns `200 OK` with error in response body:
```json
{
  "errors": [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}]
}
```

**REST**: Returns `403 Forbidden` with body:
```json
{"message": "API rate limit exceeded for user ID ..."}
```

**Recovery pattern:**
```python
def handle_rate_limit(response_or_data):
    """Wait for rate limit reset."""
    # For REST
    if hasattr(response_or_data, 'headers'):
        reset_ts = int(response_or_data.headers.get("X-RateLimit-Reset", 0))
        wait = max(reset_ts - time.time(), 5)
    # For GraphQL
    elif "rateLimit" in response_or_data.get("data", {}):
        reset_at = response_or_data["data"]["rateLimit"]["resetAt"]
        # Parse ISO 8601 and compute wait
        from datetime import datetime, timezone
        reset_dt = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
        wait = max((reset_dt - datetime.now(timezone.utc)).total_seconds(), 5)
    else:
        wait = 60

    print(f"Rate limited. Waiting {wait:.0f}s...")
    time.sleep(wait + 1)
```

### Overcoming the 1,000-Result Search Limit

Search endpoints (both GraphQL and REST) cap at 1,000 results. Strategies:

1. **Date partitioning** — split by `created:` ranges:
   ```
   created:2024-01-01..2024-03-31
   created:2024-04-01..2024-06-30
   created:2024-07-01..2024-09-30
   created:2024-10-01..2024-12-31
   ```

2. **Label partitioning** — separate queries per label

3. **Use list endpoints instead** — for single-repo data, `repository.issues` and `repository.pullRequests` paginate without limit (unlike `search`)
