#!/usr/bin/env python3
"""GitHub data collection utility using GraphQL API (v4) for empirical research.

Uses GraphQL as the primary interface for efficient data fetching with precise
field selection and nested queries. Falls back to REST for statistics endpoints
and file trees which are not available in GraphQL.

Usage:
    python github_api_fetch.py --repo owner/repo --output data/ --collect all
    python github_api_fetch.py --repo owner/repo --output data/ --collect commits issues prs
    python github_api_fetch.py --repo owner/repo --output data/ --collect commits --since 2024-01-01
    python github_api_fetch.py --repo owner/repo --output data/ --collect stats tree

    # Batch multiple repos
    python github_api_fetch.py --repos pytorch/pytorch tensorflow/tensorflow --output data/ --collect metadata

Requires GITHUB_TOKEN environment variable (GraphQL API requires authentication).
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library required. Install with: pip install requests")
    sys.exit(1)

# --- Configuration ---
GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
REST_BASE_URL = "https://api.github.com"
API_VERSION = "2022-11-28"
PER_PAGE = 100


# =============================================================================
# GraphQL Queries
# =============================================================================

QUERY_REPO_METADATA = """
query GetRepository($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    nameWithOwner
    description
    url
    homepageUrl
    stargazerCount
    forkCount
    watchers { totalCount }
    isArchived
    isFork
    isPrivate
    createdAt
    updatedAt
    pushedAt
    diskUsage
    primaryLanguage { name color }
    languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
      totalSize
      edges { size node { name color } }
    }
    repositoryTopics(first: 20) {
      nodes { topic { name } }
    }
    licenseInfo { name spdxId url }
    defaultBranchRef { name }
    readme: object(expression: "HEAD:README.md") {
      ... on Blob { text byteSize }
    }
    issues(states: [OPEN, CLOSED]) { totalCount }
    pullRequests(states: [OPEN, CLOSED, MERGED]) { totalCount }
  }
  rateLimit { limit remaining cost resetAt used }
}
"""

QUERY_COMMITS = """
query GetCommits($owner: String!, $name: String!, $cursor: String, $since: GitTimestamp, $until: GitTimestamp) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $cursor, since: $since, until: $until) {
            totalCount
            pageInfo { hasNextPage endCursor }
            nodes {
              oid
              messageHeadline
              message
              committedDate
              additions
              deletions
              changedFilesIfAvailable
              author {
                name
                email
                user { login }
              }
              committer {
                name
                email
                user { login }
              }
              parents(first: 2) { totalCount }
            }
          }
        }
      }
    }
  }
  rateLimit { remaining cost resetAt }
}
"""

QUERY_ISSUES = """
query GetIssues($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(first: 100, after: $cursor, states: [OPEN, CLOSED],
           orderBy: {field: CREATED_AT, direction: ASC}) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body
        state
        createdAt
        updatedAt
        closedAt
        url
        author { login }
        labels(first: 10) { nodes { name color description } }
        assignees(first: 5) { nodes { login } }
        milestone { title number }
        comments(first: 5) {
          totalCount
          nodes {
            body
            createdAt
            author { login }
          }
        }
        reactions { totalCount }
      }
    }
  }
  rateLimit { remaining cost resetAt }
}
"""

QUERY_PULL_REQUESTS = """
query GetPullRequests($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 50, after: $cursor, states: [OPEN, CLOSED, MERGED],
                 orderBy: {field: CREATED_AT, direction: ASC}) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body
        state
        isDraft
        createdAt
        updatedAt
        mergedAt
        closedAt
        url
        author { login }
        mergedBy { login }
        additions
        deletions
        changedFiles
        labels(first: 10) { nodes { name color } }
        reviews(first: 5) {
          totalCount
          nodes {
            state
            author { login }
            submittedAt
          }
        }
        files(first: 50) {
          nodes { path additions deletions }
        }
        comments { totalCount }
        commits { totalCount }
      }
    }
  }
  rateLimit { remaining cost resetAt }
}
"""

QUERY_CONTRIBUTORS = """
query GetContributorCommits($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $cursor) {
            totalCount
            pageInfo { hasNextPage endCursor }
            nodes {
              author {
                name
                email
                user { login avatarUrl }
              }
              committedDate
              additions
              deletions
            }
          }
        }
      }
    }
  }
  rateLimit { remaining cost resetAt }
}
"""

QUERY_SEARCH_REPOS = """
query SearchRepositories($query: String!, $cursor: String) {
  search(query: $query, type: REPOSITORY, first: 100, after: $cursor) {
    repositoryCount
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
        defaultBranchRef { name }
      }
    }
  }
  rateLimit { remaining cost resetAt }
}
"""

# Fragment for batch queries
FRAGMENT_REPO_FIELDS = """
fragment RepoFields on Repository {
  nameWithOwner
  description
  url
  stargazerCount
  forkCount
  createdAt
  updatedAt
  primaryLanguage { name color }
  licenseInfo { name spdxId }
  repositoryTopics(first: 10) { nodes { topic { name } } }
  defaultBranchRef {
    target {
      ... on Commit {
        history(first: 1) { totalCount }
      }
    }
  }
  issues(states: [OPEN, CLOSED]) { totalCount }
  pullRequests(states: [OPEN, CLOSED, MERGED]) { totalCount }
}
"""


# =============================================================================
# Core GraphQL Client
# =============================================================================

def graphql_request(token: str, query: str, variables: dict = None) -> dict:
    """Execute a single GraphQL request.

    Args:
        token: GitHub personal access token
        query: GraphQL query string
        variables: Query variables dict

    Returns:
        Parsed JSON response

    Raises:
        requests.HTTPError: On non-200 responses
        RuntimeError: On GraphQL errors
    """
    headers = {
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    resp = requests.post(GRAPHQL_ENDPOINT, json=payload, headers=headers)

    # Handle rate limiting
    if resp.status_code == 403:
        reset_ts = int(resp.headers.get("X-RateLimit-Reset", 0))
        wait = max(reset_ts - time.time(), 5)
        print(f"  Rate limited. Waiting {wait:.0f}s...")
        time.sleep(wait + 1)
        # Retry once
        resp = requests.post(GRAPHQL_ENDPOINT, json=payload, headers=headers)

    if resp.status_code == 502:
        print("  Server error (502), retrying in 5s...")
        time.sleep(5)
        resp = requests.post(GRAPHQL_ENDPOINT, json=payload, headers=headers)

    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        for err in data["errors"]:
            print(f"  GraphQL error: {err.get('message', err)}")
        if "data" not in data or data["data"] is None:
            raise RuntimeError(f"GraphQL query failed: {data['errors']}")

    return data


def graphql_paginated(token: str, query: str, variables: dict,
                      connection_path: str, max_pages: int = None) -> list:
    """Fetch all pages from a GraphQL connection using cursor pagination.

    Args:
        token: GitHub personal access token
        query: GraphQL query with $cursor variable
        variables: Base variables (cursor will be injected)
        connection_path: Dot-separated path to the connection object
            e.g., "repository.issues" or "repository.defaultBranchRef.target.history"
        max_pages: Optional limit on pages fetched

    Returns:
        List of all nodes across all pages
    """
    all_nodes = []
    cursor = None
    page = 0

    while True:
        if max_pages and page >= max_pages:
            print(f"  Reached max_pages limit ({max_pages})")
            break

        variables["cursor"] = cursor
        data = graphql_request(token, query, variables)
        page += 1

        # Navigate to the connection
        connection = data["data"]
        for key in connection_path.split("."):
            if connection is None:
                print(f"  Warning: null at path segment '{key}' in {connection_path}")
                return all_nodes
            connection = connection[key]

        nodes = connection.get("nodes", [])
        all_nodes.extend(nodes)

        page_info = connection["pageInfo"]
        total = connection.get("totalCount", "?")
        rate = data["data"].get("rateLimit", {})

        print(f"  Page {page}: {len(nodes)} items (total: {len(all_nodes)}/{total}) | "
              f"Rate: {rate.get('remaining', '?')} remaining, cost={rate.get('cost', '?')}")

        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]

        # Safety: if rate limit is low, pause
        remaining = rate.get("remaining", 100)
        if remaining < 50:
            reset_at = rate.get("resetAt", "")
            print(f"  Low rate limit ({remaining}). Waiting 60s... (resets at {reset_at})")
            time.sleep(60)
        else:
            time.sleep(0.1)  # Small delay for politeness

    return all_nodes


# =============================================================================
# REST Client (for stats/tree endpoints not in GraphQL)
# =============================================================================

def rest_get(token: str, url: str, params: dict = None) -> requests.Response:
    """Make a REST API GET request with rate-limit handling."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
    }
    resp = requests.get(url, headers=headers, params=params)

    if resp.status_code in (403, 429):
        reset_ts = int(resp.headers.get("X-RateLimit-Reset", 0))
        wait = max(reset_ts - time.time(), 5)
        print(f"  Rate limited (REST). Waiting {wait:.0f}s...")
        time.sleep(wait + 1)
        resp = requests.get(url, headers=headers, params=params)

    return resp


def rest_paginated(token: str, url: str, params: dict = None) -> list:
    """Paginate through a REST API endpoint using Link headers."""
    params = dict(params or {})
    params["per_page"] = PER_PAGE
    all_items = []

    while url:
        resp = rest_get(token, url, params)

        if resp.status_code == 202:
            print("  Stats being computed, retrying in 3s...")
            time.sleep(3)
            continue
        if resp.status_code == 204:
            break
        if resp.status_code != 200:
            print(f"  Warning: HTTP {resp.status_code} for {url}")
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
        params = {}
        link_header = resp.headers.get("Link", "")
        for part in link_header.split(","):
            if 'rel="next"' in part:
                url = part.split(";")[0].strip().strip("<>")
                break

        if url:
            time.sleep(0.1)

    return all_items


# =============================================================================
# Data Collection Functions
# =============================================================================

def save_json(data, filepath: Path):
    """Save data as JSON with pretty formatting."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    count = len(data) if isinstance(data, list) else 1
    print(f"  Saved: {filepath} ({count} items)")


def fetch_repo_metadata(owner: str, repo: str, token: str, output_dir: Path):
    """Fetch repository metadata via GraphQL (replaces 4+ REST calls)."""
    print("\n[1/7] Fetching repository metadata (GraphQL)...")
    data = graphql_request(token, QUERY_REPO_METADATA,
                           {"owner": owner, "name": repo})
    repo_data = data["data"]["repository"]
    save_json(repo_data, output_dir / "repo_metadata.json")
    rate = data["data"]["rateLimit"]
    print(f"  Rate limit: {rate['remaining']}/{rate['limit']} (cost: {rate['cost']})")
    return repo_data


def fetch_file_tree(owner: str, repo: str, token: str, output_dir: Path,
                    branch: str = None):
    """Fetch complete recursive file tree (REST only)."""
    print("\n[2/7] Fetching file tree (REST)...")
    if branch is None:
        # Get default branch from a quick GraphQL call
        data = graphql_request(token, """
            query($owner: String!, $name: String!) {
              repository(owner: $owner, name: $name) {
                defaultBranchRef { name }
              }
            }
        """, {"owner": owner, "name": repo})
        branch = data["data"]["repository"]["defaultBranchRef"]["name"]

    url = f"{REST_BASE_URL}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    resp = rest_get(token, url)

    if resp.status_code == 404:
        print(f"  Branch '{branch}' not found, trying 'main'...")
        url = f"{REST_BASE_URL}/repos/{owner}/{repo}/git/trees/main?recursive=1"
        resp = rest_get(token, url)
        if resp.status_code == 404:
            print("  Trying 'master'...")
            url = f"{REST_BASE_URL}/repos/{owner}/{repo}/git/trees/master?recursive=1"
            resp = rest_get(token, url)

    resp.raise_for_status()
    data = resp.json()

    if data.get("truncated"):
        print("  WARNING: Tree is truncated (>100,000 entries). Some files may be missing.")

    tree_entries = data.get("tree", [])
    save_json(tree_entries, output_dir / "file_tree.json")
    print(f"  Total entries: {len(tree_entries)}, truncated: {data.get('truncated', False)}")
    return tree_entries


def fetch_contributors(owner: str, repo: str, token: str, output_dir: Path):
    """Fetch contributor data from commit history (GraphQL) + weekly stats (REST)."""
    print("\n[3/7] Fetching contributors (GraphQL + REST)...")

    # Extract unique contributors from commit history via GraphQL
    print("  Extracting contributors from commit history...")
    commit_nodes = graphql_paginated(
        token, QUERY_CONTRIBUTORS,
        {"owner": owner, "name": repo},
        "repository.defaultBranchRef.target.history"
    )

    # Aggregate contributor stats
    contributors = {}
    for node in commit_nodes:
        author = node.get("author", {})
        if not author:
            continue
        user = author.get("user") or {}
        login = user.get("login", author.get("email", "unknown"))
        if login not in contributors:
            contributors[login] = {
                "login": login,
                "name": author.get("name", ""),
                "email": author.get("email", ""),
                "avatar_url": user.get("avatarUrl", ""),
                "commits": 0,
                "additions": 0,
                "deletions": 0,
                "first_commit": node["committedDate"],
                "last_commit": node["committedDate"],
            }
        c = contributors[login]
        c["commits"] += 1
        c["additions"] += node.get("additions", 0)
        c["deletions"] += node.get("deletions", 0)
        if node["committedDate"] < c["first_commit"]:
            c["first_commit"] = node["committedDate"]
        if node["committedDate"] > c["last_commit"]:
            c["last_commit"] = node["committedDate"]

    contributor_list = sorted(contributors.values(), key=lambda x: -x["commits"])
    save_json(contributor_list, output_dir / "contributors.json")
    print(f"  Found {len(contributor_list)} unique contributors")

    # Also fetch detailed weekly stats via REST (not available in GraphQL)
    print("  Fetching detailed weekly stats (REST)...")
    url = f"{REST_BASE_URL}/repos/{owner}/{repo}/stats/contributors"
    retries = 0
    while retries < 5:
        resp = rest_get(token, url)
        if resp.status_code == 202:
            retries += 1
            print(f"    Computing... retry {retries}/5")
            time.sleep(3)
            continue
        if resp.status_code == 200:
            save_json(resp.json(), output_dir / "contributor_weekly_stats.json")
        else:
            print(f"    Warning: HTTP {resp.status_code} for weekly stats")
        break

    return contributor_list


def fetch_commits(owner: str, repo: str, token: str, output_dir: Path,
                  since: str = None, until: str = None):
    """Fetch commit history via GraphQL with inline diff stats."""
    print("\n[4/7] Fetching commits (GraphQL)...")
    variables = {"owner": owner, "name": repo}
    if since:
        variables["since"] = f"{since}T00:00:00Z"
    if until:
        variables["until"] = f"{until}T23:59:59Z"

    commits = graphql_paginated(
        token, QUERY_COMMITS, variables,
        "repository.defaultBranchRef.target.history"
    )
    save_json(commits, output_dir / "commits.json")
    return commits


def fetch_issues(owner: str, repo: str, token: str, output_dir: Path):
    """Fetch all issues with inline comments via GraphQL."""
    print("\n[5/7] Fetching issues (GraphQL, with inline comments)...")
    issues = graphql_paginated(
        token, QUERY_ISSUES,
        {"owner": owner, "name": repo},
        "repository.issues"
    )
    save_json(issues, output_dir / "issues.json")
    print(f"  Total issues collected: {len(issues)}")
    return issues


def fetch_pull_requests(owner: str, repo: str, token: str, output_dir: Path):
    """Fetch all PRs with inline files and reviews via GraphQL."""
    print("\n[6/7] Fetching pull requests (GraphQL, with files + reviews)...")
    prs = graphql_paginated(
        token, QUERY_PULL_REQUESTS,
        {"owner": owner, "name": repo},
        "repository.pullRequests"
    )
    save_json(prs, output_dir / "pull_requests.json")
    print(f"  Total PRs collected: {len(prs)}")
    return prs


def fetch_stats(owner: str, repo: str, token: str, output_dir: Path):
    """Fetch repository activity statistics (REST only)."""
    print("\n[7/7] Fetching repository statistics (REST)...")
    stats_dir = output_dir / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)

    endpoints = {
        "commit_activity": f"{REST_BASE_URL}/repos/{owner}/{repo}/stats/commit_activity",
        "code_frequency": f"{REST_BASE_URL}/repos/{owner}/{repo}/stats/code_frequency",
        "participation": f"{REST_BASE_URL}/repos/{owner}/{repo}/stats/participation",
        "punch_card": f"{REST_BASE_URL}/repos/{owner}/{repo}/stats/punch_card",
    }

    for name, url in endpoints.items():
        print(f"  Fetching {name}...")
        retries = 0
        while retries < 5:
            resp = rest_get(token, url)
            if resp.status_code == 202:
                retries += 1
                print(f"    Computing... retry {retries}/5")
                time.sleep(3)
                continue
            if resp.status_code == 204:
                print(f"    No data available for {name}")
                break
            if resp.status_code == 422:
                print(f"    Repo too large for {name} (10,000+ commits)")
                break
            if resp.status_code != 200:
                print(f"    Warning: HTTP {resp.status_code}")
                break
            save_json(resp.json(), stats_dir / f"{name}.json")
            break
        time.sleep(0.5)


def fetch_batch_metadata(repos: list, token: str, output_dir: Path):
    """Fetch metadata for multiple repos in a single GraphQL query using aliases."""
    print(f"\nBatch fetching metadata for {len(repos)} repos (GraphQL aliases)...")

    # Build aliased query
    alias_parts = []
    for i, repo_str in enumerate(repos):
        owner, name = repo_str.split("/")
        alias = f"repo{i}"
        alias_parts.append(
            f'  {alias}: repository(owner: "{owner}", name: "{name}") {{ ...RepoFields }}'
        )

    query = FRAGMENT_REPO_FIELDS + "\nquery BatchRepos {\n"
    query += "\n".join(alias_parts)
    query += "\n  rateLimit { remaining cost resetAt }\n}"

    data = graphql_request(token, query)
    rate = data["data"].get("rateLimit", {})
    print(f"  Rate limit: {rate.get('remaining', '?')} remaining, cost={rate.get('cost', '?')}")

    # Save each repo's data
    for i, repo_str in enumerate(repos):
        alias = f"repo{i}"
        repo_data = data["data"][alias]
        safe_name = repo_str.replace("/", "_")
        save_json(repo_data, output_dir / f"{safe_name}_metadata.json")

    # Also save combined
    combined = {repo_str: data["data"][f"repo{i}"] for i, repo_str in enumerate(repos)}
    save_json(combined, output_dir / "batch_metadata.json")
    return combined


def search_repositories(query_str: str, token: str, output_dir: Path,
                        max_pages: int = 10):
    """Search GitHub repositories via GraphQL."""
    print(f"\nSearching repositories: {query_str}")
    repos = graphql_paginated(
        token, QUERY_SEARCH_REPOS,
        {"query": query_str},
        "search",
        max_pages=max_pages
    )
    save_json(repos, output_dir / "search_results.json")
    print(f"  Found {len(repos)} repositories")
    return repos


def check_rate_limit(token: str):
    """Print current rate limit status via GraphQL."""
    data = graphql_request(token, "query { rateLimit { limit remaining resetAt used } }")
    rate = data["data"]["rateLimit"]
    print(f"Rate limit — GraphQL: {rate['remaining']}/{rate['limit']} "
          f"(used: {rate['used']}, resets: {rate['resetAt']})")

    # Also check REST limits
    resp = rest_get(token, f"{REST_BASE_URL}/rate_limit")
    if resp.status_code == 200:
        rest_data = resp.json()
        core = rest_data["resources"]["core"]
        search = rest_data["resources"]["search"]
        graphql = rest_data["resources"].get("graphql", {})
        print(f"Rate limit — REST Core: {core['remaining']}/{core['limit']} | "
              f"Search: {search['remaining']}/{search['limit']} | "
              f"GraphQL: {graphql.get('remaining', 'N/A')}/{graphql.get('limit', 'N/A')}")


# =============================================================================
# Main CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="GitHub data collection via GraphQL + REST for empirical research",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect all data for a single repo
  python github_api_fetch.py --repo pytorch/pytorch --output data/ --collect all

  # Collect only commits from 2024
  python github_api_fetch.py --repo owner/repo -o data/ -c commits --since 2024-01-01

  # Batch metadata for multiple repos (single GraphQL query)
  python github_api_fetch.py --repos pytorch/pytorch tensorflow/tensorflow -o data/ -c metadata

  # Search repositories by topic
  python github_api_fetch.py --search "topic:machine-learning language:python stars:>=500" -o data/
        """,
    )
    parser.add_argument("--repo", "-r",
                        help="Repository in owner/repo format")
    parser.add_argument("--repos", nargs="+",
                        help="Multiple repositories for batch queries (owner/repo format)")
    parser.add_argument("--search", "-s",
                        help="Search query string (GitHub search syntax)")
    parser.add_argument("--output", "-o", default="github_data",
                        help="Output directory (default: github_data/)")
    parser.add_argument("--collect", "-c", nargs="+",
                        choices=["all", "metadata", "tree", "contributors",
                                 "commits", "issues", "prs", "stats"],
                        default=["all"],
                        help="What data to collect (default: all)")
    parser.add_argument("--since", help="Start date for commits (YYYY-MM-DD)")
    parser.add_argument("--until", help="End date for commits (YYYY-MM-DD)")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Max pages to fetch per collection (for testing)")

    args = parser.parse_args()

    # Validate arguments
    if not args.repo and not args.repos and not args.search:
        parser.error("Provide --repo, --repos, or --search")

    # Get token (required for GraphQL)
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("ERROR: GITHUB_TOKEN is required (GraphQL API requires authentication)")
        print("Set it with: export GITHUB_TOKEN=your_token_here")
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("GitHub Data Collection (GraphQL + REST)")
    print("=" * 50)

    start_time = time.time()

    # Handle search mode
    if args.search:
        check_rate_limit(token)
        search_repositories(args.search, token, output_dir,
                            max_pages=args.max_pages or 10)
        elapsed = time.time() - start_time
        print(f"\nDone! Elapsed: {elapsed:.1f}s")
        check_rate_limit(token)
        return

    # Handle batch mode
    if args.repos:
        check_rate_limit(token)
        fetch_batch_metadata(args.repos, token, output_dir)
        elapsed = time.time() - start_time
        print(f"\nDone! Elapsed: {elapsed:.1f}s")
        check_rate_limit(token)
        return

    # Single repo mode
    parts = args.repo.split("/")
    if len(parts) != 2:
        print("ERROR: --repo must be in owner/repo format")
        sys.exit(1)
    owner, repo = parts

    repo_output = output_dir / f"{owner}_{repo}"
    repo_output.mkdir(parents=True, exist_ok=True)

    collect = set(args.collect)
    if "all" in collect:
        collect = {"metadata", "tree", "contributors", "commits", "issues", "prs", "stats"}

    print(f"Repository: {owner}/{repo}")
    print(f"Output: {repo_output}")
    print(f"Collecting: {', '.join(sorted(collect))}")
    print(f"API: GraphQL (primary) + REST (stats/tree)")
    check_rate_limit(token)
    print("=" * 50)

    if "metadata" in collect:
        fetch_repo_metadata(owner, repo, token, repo_output)

    if "tree" in collect:
        fetch_file_tree(owner, repo, token, repo_output)

    if "contributors" in collect:
        fetch_contributors(owner, repo, token, repo_output)

    if "commits" in collect:
        fetch_commits(owner, repo, token, repo_output,
                      since=args.since, until=args.until)

    if "issues" in collect:
        fetch_issues(owner, repo, token, repo_output)

    if "prs" in collect:
        fetch_pull_requests(owner, repo, token, repo_output)

    if "stats" in collect:
        fetch_stats(owner, repo, token, repo_output)

    elapsed = time.time() - start_time
    print(f"\nDone! Elapsed: {elapsed:.1f}s")
    print(f"Data saved to: {repo_output}")
    check_rate_limit(token)


if __name__ == "__main__":
    main()
