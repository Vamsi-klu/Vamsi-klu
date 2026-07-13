#!/usr/bin/env python3
"""
Fetches open-source PR contributions for Vamsi-klu from GitHub API
and updates the contributions section in README.md with a COMPACT, curated view.

Focus: Impact summaries + counts + 3-5 key highlights per major project.
No more dumping every single PR link.
"""

import json
import os
import re
import urllib.request

GITHUB_USERNAME = "Vamsi-klu"
README_PATH = "README.md"
START_MARKER = "<!-- START_SECTION:contributions -->"
END_MARKER = "<!-- END_SECTION:contributions -->"

# Known orgs with nice badges (order matters for display)
ORG_CONFIG = {
    "apache/airflow": {
        "name": "Apache Airflow",
        "badge": "https://img.shields.io/badge/Apache%20Airflow-017CEE?style=for-the-badge&logo=Apache%20Airflow&logoColor=white",
    },
    "dagster-io/dagster": {
        "name": "Dagster",
        "badge": "https://img.shields.io/badge/Dagster-4F43DD?style=for-the-badge&logo=dagster&logoColor=white",
    },
    "apache/spark": {
        "name": "Apache Spark",
        "badge": "https://img.shields.io/badge/Apache%20Spark-E25A1C?style=for-the-badge&logo=apachespark&logoColor=white",
    },
    "airbytehq/airbyte": {
        "name": "Airbyte",
        "badge": "https://img.shields.io/badge/Airbyte-181717?style=for-the-badge&logo=github&logoColor=white",
    },
    "apache/pinot": {
        "name": "Apache Pinot",
        "badge": "https://img.shields.io/badge/Apache%20Pinot-181717?style=for-the-badge&logo=github&logoColor=white",
    },
    "pola-rs/polars": {
        "name": "Polars",
        "badge": "https://img.shields.io/badge/Polars-181717?style=for-the-badge&logo=github&logoColor=white",
    },
    "apache/flink": {
        "name": "Apache Flink",
        "badge": "https://img.shields.io/badge/Apache%20Flink-181717?style=for-the-badge&logo=github&logoColor=white",
    },
}


def github_api(url):
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def fetch_prs():
    # Fetch recent public PRs (search limited but good for recent activity)
    url = (
        "https://api.github.com/search/issues"
        f"?q=type:pr+author:{GITHUB_USERNAME}+is:public+-user:{GITHUB_USERNAME}"
        "&per_page=100&sort=created&order=desc"
    )
    data = github_api(url)
    return data.get("items", [])


def get_pr_merge_status(owner_repo, pr_number):
    url = f"https://api.github.com/repos/{owner_repo}/pulls/{pr_number}"
    try:
        data = github_api(url)
        return data.get("merged", False), data.get("state", "unknown")
    except Exception:
        return False, "unknown"


def extract_repo(api_url):
    return "/".join(api_url.replace("https://api.github.com/repos/", "").split("/")[:2])


def build_curated_section(prs):
    """Build a clean, meaningful contributions section."""
    grouped = {}
    for pr in prs:
        repo = extract_repo(pr["repository_url"])
        if repo not in grouped:
            grouped[repo] = []
        grouped[repo].append(pr)

    # Enrich with merge status
    for repo, pr_list in grouped.items():
        for pr in pr_list:
            pr["merged"], pr["current_state"] = get_pr_merge_status(repo, pr["number"])

    # Compute totals and highlights
    lines = []
    total_prs = 0
    total_merged = 0

    # Major known orgs first
    for repo_key, config in ORG_CONFIG.items():
        if repo_key not in grouped:
            continue
        pr_list = grouped[repo_key]
        total_prs += len(pr_list)
        merged_list = [p for p in pr_list if p.get("merged")]
        total_merged += len(merged_list)

        name = config["name"]
        badge = f'<img src="{config["badge"]}" alt="{name}" />'

        # Keywords from titles
        keywords = summarize_keywords(pr_list)
        count_str = f"{len(pr_list)} PRs"
        if merged_list:
            count_str += f" ({len(merged_list)} merged)"

        # Top 4 highlights (prefer merged, then recent)
        highlights = select_highlights(pr_list, max_n=4)
        highlights_str = " · ".join(highlights) if highlights else "Contributions"

        lines.append(f"| {badge} | **{count_str}** — {keywords}<br>{highlights_str} |")

    # Other orgs (lumped)
    other_prs = []
    for repo_key, pr_list in grouped.items():
        if repo_key in ORG_CONFIG:
            continue
        other_prs.extend(pr_list)
        total_prs += len(pr_list)
        total_merged += len([p for p in pr_list if p.get("merged")])

    if other_prs:
        other_count = len(other_prs)
        other_merged = len([p for p in other_prs if p.get("merged")])
        other_kw = summarize_keywords(other_prs)
        lines.append(f'| <img src="https://img.shields.io/badge/Other%20Projects-181717?style=for-the-badge&logo=github&logoColor=white" /> | **{other_count} PRs** ({other_merged} merged) — {other_kw} |')

    # Header
    header = f"**{total_prs}+ PRs • {total_merged}+ merged** across major open source data projects."

    table = "| Project | Impact & Highlights |\n|:-------:|:--------------------|\n" + "\n".join(lines)

    section = f"""{START_MARKER}
<div align="center">

{header}

{table}

[View all contributions on GitHub](https://github.com/search?q=author%3AVamsi-klu+is%3Apr&type=pullrequests)

</div>
{END_MARKER}"""
    return section, total_prs, total_merged


def summarize_keywords(pr_list):
    keywords = set()
    for pr in pr_list:
        title = pr.get("title", "").lower()
        if "fix" in title or "bug" in title:
            keywords.add("bug fixes")
        if "doc" in title:
            keywords.add("docs")
        if any(k in title for k in ["feat", "add", "implement", "new"]):
            keywords.add("features")
        if "refactor" in title:
            keywords.add("refactoring")
        if "test" in title:
            keywords.add("tests")
        if "perf" in title or "optim" in title:
            keywords.add("performance")
        if "improv" in title or "chore" in title:
            keywords.add("improvements")
    if not keywords:
        keywords.add("contributions")
    return ", ".join(sorted(keywords))


def select_highlights(pr_list, max_n=4):
    """Pick a few standout/recent PR links. Prefer merged."""
    def key(p):
        return (0 if p.get("merged") else 1, -p.get("number", 0))  # merged first, higher num recent
    sorted_prs = sorted(pr_list, key=key)[:max_n]
    out = []
    for p in sorted_prs:
        status = " (merged)" if p.get("merged") else ""
        out.append(f"[#{p['number']}]({p['html_url']}){status}")
    return out


def update_readme(new_section):
    with open(README_PATH, "r") as f:
        content = f.read()

    if "Beautiful curated version" in content:
        print("Curated profile README protected (static beautiful version, no auto markers). Skipping update to prevent bloat.")
        github_output = os.environ.get("GITHUB_OUTPUT", "")
        if github_output:
            with open(github_output, "a") as f:
                f.write("changed=false\n")
        return False

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    new_content = pattern.sub(new_section, content)

    if new_content != content:
        with open(README_PATH, "w") as f:
            f.write(new_content)
        print("README.md updated with curated contributions section.")
        return True
    else:
        print("No changes needed.")
        return False


def main():
    print(f"Fetching PRs for {GITHUB_USERNAME}...")
    prs = fetch_prs()
    print(f"Found {len(prs)} recent external PRs.")

    print("Building curated contributions section...")
    new_section, total, merged = build_curated_section(prs)

    print("Updating README.md...")
    changed = update_readme(new_section)

    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")


if __name__ == "__main__":
    main()
