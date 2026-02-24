# GitHub API Reference — GraphQL (Primary) + REST (Fallback)

Complete reference for all GitHub API queries used in repository mining.

**GraphQL Endpoint**: `POST https://api.github.com/graphql`
**REST Base URL**: `https://api.github.com`
**Authentication**: `Authorization: bearer {GITHUB_TOKEN}` (required for GraphQL)

---

## GraphQL Queries

### Repository Metadata

Fetches comprehensive repo info in a single query (replaces 4+ REST calls).

```graphql
query GetRepository($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    nameWithOwner       # "owner/repo"
    description
    url                 # HTML URL
    homepageUrl
    stargazerCount
    forkCount
    watchers { totalCount }
    isArchived
    isFork
    isPrivate
    createdAt           # ISO 8601
    updatedAt
    pushedAt
    diskUsage           # KB
    primaryLanguage { name color }
    languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
      totalSize         # Total bytes across all languages
      edges {
        size            # Bytes for this language
        node { name color }
      }
    }
    repositoryTopics(first: 20) {
      nodes { topic { name } }
    }
    licenseInfo { name spdxId url }
    defaultBranchRef { name }
    # Inline README content
    readme: object(expression: "HEAD:README.md") {
      ... on Blob { text byteSize }
    }
    # Quick counts (no pagination needed)
    issues(states: [OPEN, CLOSED]) { totalCount }
    pullRequests(states: [OPEN, CLOSED, MERGED]) { totalCount }
    # Open vs closed breakdown
    openIssues: issues(states: OPEN) { totalCount }
    closedIssues: issues(states: CLOSED) { totalCount }
    openPRs: pullRequests(states: OPEN) { totalCount }
    mergedPRs: pullRequests(states: MERGED) { totalCount }
  }
  rateLimit { limit remaining cost resetAt used }
}
```

**Variables**: `{"owner": "pytorch", "name": "pytorch"}`

**Key fields**:
- `stargazerCount`, `forkCount` — popularity metrics
- `languages.edges[].size` — byte count per language (compute percentages from `totalSize`)
- `repositoryTopics.nodes[].topic.name` — topic tags
- `diskUsage` — repo size in KB
- `readme` — full README text inline (use `object(expression: "HEAD:filename")` for any file)

---

### Commit History

Paginated commit history with inline diff stats.

```graphql
query GetCommits($owner: String!, $name: String!, $cursor: String,
                 $since: GitTimestamp, $until: GitTimestamp) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $cursor, since: $since, until: $until) {
            totalCount
            pageInfo { hasNextPage endCursor }
            nodes {
              oid                          # Full SHA
              messageHeadline              # First line of message
              message                      # Full commit message
              committedDate                # ISO 8601
              authoredDate
              additions                    # Lines added (inline!)
              deletions                    # Lines deleted (inline!)
              changedFilesIfAvailable      # Number of files changed
              author {
                name
                email
                date
                user { login avatarUrl url }
              }
              committer {
                name
                email
                user { login }
              }
              parents(first: 2) {
                totalCount                 # >1 means merge commit
              }
            }
          }
        }
      }
    }
  }
  rateLimit { remaining cost resetAt }
}
```

**Variables**:
```json
{
  "owner": "pytorch", "name": "pytorch",
  "cursor": null,
  "since": "2024-01-01T00:00:00Z",
  "until": "2024-12-31T23:59:59Z"
}
```

**Pagination path**: `repository.defaultBranchRef.target.history`

**Notes**:
- `since`/`until` use `GitTimestamp` type (ISO 8601 string)
- `additions`/`deletions` are available directly — REST requires a separate GET per commit
- `parents.totalCount > 1` indicates a merge commit
- `changedFilesIfAvailable` may be null for very large commits
- To filter by author: add `author: {id: "MDQ6..."}` parameter (requires user node ID)
- To filter by path: use the `path: String` argument on `history(path: "src/models/")` — available in GraphQL

---

### Issues

Paginated issues with inline labels, assignees, and first N comments.

```graphql
query GetIssues($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(first: 100, after: $cursor,
           states: [OPEN, CLOSED],
           orderBy: {field: CREATED_AT, direction: ASC},
           filterBy: {labels: null, assignee: null, createdBy: null}) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body                  # Markdown content
        bodyText              # Plain text (no markdown)
        state                 # OPEN or CLOSED
        stateReason           # COMPLETED, NOT_PLANNED, REOPENED, null
        createdAt
        updatedAt
        closedAt
        url
        author { login url }
        editor { login }      # Last editor of body
        labels(first: 10) {
          nodes { name color description }
        }
        assignees(first: 5) {
          nodes { login }
        }
        milestone {
          title
          number
          state               # OPEN or CLOSED
        }
        # Inline comments (first 5 per issue)
        comments(first: 5) {
          totalCount
          nodes {
            body
            createdAt
            author { login }
          }
        }
        reactions { totalCount }
        # Timeline items count
        timelineItems { totalCount }
      }
    }
  }
  rateLimit { remaining cost resetAt }
}
```

**Pagination path**: `repository.issues`

**`filterBy` options** (all optional):
- `labels: ["bug", "enhancement"]` — filter by label names
- `assignee: "username"` — filter by assignee
- `createdBy: "username"` — filter by creator
- `states: [OPEN]` or `[CLOSED]` or `[OPEN, CLOSED]`
- `since: "2024-01-01T00:00:00Z"` — issues updated since this date

**`orderBy` options**:
- `field`: `CREATED_AT`, `UPDATED_AT`, `COMMENTS`
- `direction`: `ASC`, `DESC`

**Notes**:
- Unlike REST, GraphQL issues endpoint returns **only** issues (not PRs)
- `stateReason` distinguishes issues closed as COMPLETED vs NOT_PLANNED
- For full comment threads, paginate `comments` separately per issue

---

### Pull Requests

Paginated PRs with inline files, reviews, and labels.

```graphql
query GetPullRequests($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 50, after: $cursor,
                 states: [OPEN, CLOSED, MERGED],
                 orderBy: {field: CREATED_AT, direction: ASC}) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body
        state                 # OPEN, CLOSED, or MERGED
        isDraft
        createdAt
        updatedAt
        mergedAt
        closedAt
        url
        author { login }
        mergedBy { login }
        baseRefName           # Target branch
        headRefName           # Source branch
        additions             # Total lines added
        deletions             # Total lines deleted
        changedFiles           # Number of files changed
        labels(first: 10) {
          nodes { name color }
        }
        # Review data inline
        reviews(first: 10) {
          totalCount
          nodes {
            state             # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED
            author { login }
            submittedAt
            body
          }
        }
        # Changed files inline
        files(first: 50) {
          totalCount
          nodes {
            path
            additions
            deletions
            changeType        # ADDED, DELETED, MODIFIED, RENAMED, COPIED
          }
        }
        comments { totalCount }
        commits { totalCount }
        # Reviewers requested
        reviewRequests(first: 5) {
          nodes {
            requestedReviewer {
              ... on User { login }
              ... on Team { name }
            }
          }
        }
      }
    }
  }
  rateLimit { remaining cost resetAt }
}
```

**Pagination path**: `repository.pullRequests`

**Notes**:
- Use `first: 50` (not 100) for PRs since nested `files` and `reviews` increase query cost
- `state: MERGED` is a distinct state in GraphQL (REST uses `merged_at != null`)
- `files(first: 50)` may need separate pagination for PRs with 50+ files
- `changeType` on files: `ADDED`, `DELETED`, `MODIFIED`, `RENAMED`, `COPIED`

---

### Repository Search

Search across all of GitHub using the full search syntax.

```graphql
query SearchRepositories($query: String!, $cursor: String) {
  search(query: $query, type: REPOSITORY, first: 100, after: $cursor) {
    repositoryCount         # Total matches (may exceed 1,000)
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on Repository {
        nameWithOwner
        description
        url
        stargazerCount
        forkCount
        createdAt
        updatedAt
        pushedAt
        isArchived
        isFork
        primaryLanguage { name color }
        licenseInfo { name spdxId }
        repositoryTopics(first: 10) {
          nodes { topic { name } }
        }
        owner {
          login
          __typename          # "User" or "Organization"
        }
      }
    }
  }
  rateLimit { remaining cost resetAt }
}
```

**Search query syntax** (passed as `$query` string):
```
topic:machine-learning language:python stars:>=500 sort:stars-desc
language:rust stars:500..5000 pushed:>2024-01-01
topic:bioinformatics forks:>=50 archived:false
org:leanprover-community language:lean
"formal verification" in:description stars:>10
```

**Constraint**: Maximum 1,000 results regardless of pagination. Use date partitioning for more.

---

### Issue/PR Search

```graphql
query SearchIssues($query: String!, $cursor: String) {
  search(query: $query, type: ISSUE, first: 100, after: $cursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on Issue {
        number title state createdAt closedAt
        author { login }
        labels(first: 5) { nodes { name } }
        repository { nameWithOwner }
        comments { totalCount }
      }
      ... on PullRequest {
        number title state mergedAt createdAt
        author { login }
        additions deletions changedFiles
        repository { nameWithOwner }
      }
    }
  }
  rateLimit { remaining cost resetAt }
}
```

**Search query examples**:
```
repo:pytorch/pytorch is:issue is:closed label:bug
repo:pytorch/pytorch is:pr is:merged author:username
is:issue language:python topic:deep-learning comments:>20
```

---

### Batch Queries with Aliases

Query multiple repositories in a single request:

```graphql
fragment RepoFields on Repository {
  nameWithOwner
  stargazerCount
  forkCount
  description
  primaryLanguage { name }
  licenseInfo { spdxId }
  repositoryTopics(first: 10) { nodes { topic { name } } }
  defaultBranchRef {
    target {
      ... on Commit { history(first: 1) { totalCount } }
    }
  }
  issues(states: [OPEN, CLOSED]) { totalCount }
  pullRequests(states: [OPEN, CLOSED, MERGED]) { totalCount }
}

query BatchRepos {
  pytorch: repository(owner: "pytorch", name: "pytorch") { ...RepoFields }
  tensorflow: repository(owner: "tensorflow", name: "tensorflow") { ...RepoFields }
  jax: repository(owner: "google", name: "jax") { ...RepoFields }
  rateLimit { remaining cost resetAt }
}
```

**Notes**:
- Aliases must be valid GraphQL identifiers (alphanumeric + underscore)
- Use fragments to avoid repeating field selections
- 10+ repos in one query still costs ~1 point

---

### User/Organization Info

```graphql
query GetUser($login: String!) {
  user(login: $login) {
    login
    name
    bio
    company
    location
    email
    websiteUrl
    createdAt
    followers { totalCount }
    following { totalCount }
    repositories(first: 10, orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes { nameWithOwner stargazerCount primaryLanguage { name } }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
    }
  }
}
```

```graphql
query GetOrg($login: String!) {
  organization(login: $login) {
    login
    name
    description
    websiteUrl
    createdAt
    membersWithRole { totalCount }
    repositories(first: 20, orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes { nameWithOwner stargazerCount primaryLanguage { name } }
    }
  }
}
```

---

## REST-Only Endpoints

These endpoints have no GraphQL equivalent and must use REST.

### File Tree (Recursive)
```
GET /repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1
```
Use `tree_sha` = branch name (e.g., `main`).

**Response fields per entry**: `path`, `mode`, `type` (blob/tree), `sha`, `size`.
**Limits**: Max 100,000 entries, 7 MB response. Check `truncated: true`.

### Statistics Endpoints

All return `202 Accepted` while computing (retry after 2-3s). All exclude merge commits.

| Endpoint | Returns |
|----------|---------|
| `GET /repos/{o}/{r}/stats/contributors` | Per-contributor weekly `{w, a, d, c}` |
| `GET /repos/{o}/{r}/stats/commit_activity` | 52 weeks of `{days, total, week}` |
| `GET /repos/{o}/{r}/stats/code_frequency` | Weekly `[timestamp, additions, deletions]` |
| `GET /repos/{o}/{r}/stats/participation` | Two arrays of 52 weekly counts: `all` and `owner` |
| `GET /repos/{o}/{r}/stats/punch_card` | Array of `[day, hour, commit_count]` |

**Notes**:
- Code frequency limited to repos with <10,000 commits
- Contributor stats may return 0 for additions/deletions in large repos
- All stats exclude merge commits by design

### REST Search (when GraphQL search is insufficient)

| Endpoint | Rate Limit |
|----------|------------|
| `GET /search/repositories?q=...` | 30/min |
| `GET /search/issues?q=...` | 30/min |
| `GET /search/commits?q=...` | 30/min |
| `GET /search/code?q=...` | 10/min |
| `GET /search/users?q=...` | 30/min |
| `GET /search/topics?q=...` | 30/min |

All: max 1,000 results, max 100 per page, 256-char query limit.

### Commit Path Filtering

Available in **both** GraphQL and REST:

**GraphQL** — use the `path` argument on `history`:
```graphql
repository(owner: $owner, name: $name) {
  defaultBranchRef {
    target {
      ... on Commit {
        history(first: 100, path: "src/models/transformer.py") {
          nodes { oid messageHeadline committedDate }
        }
      }
    }
  }
}
```

**REST**:
```
GET /repos/{owner}/{repo}/commits?path=src/models/transformer.py&per_page=100
```
