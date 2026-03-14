"""
Fetches open-source PR contributions for Vamsi-klu from GitHub API
and updates the contributions section in README.md.
"""

import json
import os
import re
import urllib.request

GITHUB_USERNAME = "Vamsi-klu"
README_PATH = "README.md"
START_MARKER = "<!-- START_SECTION:contributions -->"
END_MARKER = "<!-- END_SECTION:contributions -->"

# Organization display config: repo_owner -> (badge_url, description_prefix)
ORG_CONFIG = {
    "apache/airflow": {
        "badge": "https://img.shields.io/badge/Apache%20Airflow-017CEE?style=for-the-badge&logo=Apache%20Airflow&logoColor=white",
    },
    "dagster-io/dagster": {
        "badge": "https://img.shields.io/badge/Dagster-4F43DD?style=for-the-badge&logo=dagster&logoColor=white",
    },
    "apache/spark": {
        "badge": "https://img.shields.io/badge/Apache%20Spark-E25A1C?style=for-the-badge&logo=apachespark&logoColor=white",
    },
    "openedx/openedx-platform": {
        "badge": "https://img.shields.io/badge/OpenEdX-02262B?style=for-the-badge&logo=edx&logoColor=white",
    },
    "cryxnet/DeepMCPAgent": {
        "badge": "https://img.shields.io/badge/DeepMCPAgent-181717?style=for-the-badge&logo=github&logoColor=white",
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
    # https://api.github.com/repos/apache/airflow -> apache/airflow
    return "/".join(api_url.replace("https://api.github.com/repos/", "").split("/")[:2])


def build_table(prs):
    # Group PRs by repo
    grouped = {}
    for pr in prs:
        repo = extract_repo(pr["repository_url"])
        if repo not in grouped:
            grouped[repo] = []
        grouped[repo].append(pr)

    # Get merge status for each PR
    for repo, pr_list in grouped.items():
        for pr in pr_list:
            pr["merged"], pr["current_state"] = get_pr_merge_status(repo, pr["number"])

    # Build markdown table rows (known orgs first, then others)
    rows = []
    processed = set()

    # Process known orgs first (in defined order)
    for repo_key, config in ORG_CONFIG.items():
        if repo_key in grouped:
            processed.add(repo_key)
            pr_list = grouped[repo_key]
            badge = f'<img src="{config["badge"]}" />'
            pr_links = build_pr_links(pr_list, repo_key)
            description = summarize_contributions(pr_list)
            rows.append(f"| {badge} | {description} | {pr_links} |")

    # Process any new repos not in ORG_CONFIG
    for repo_key, pr_list in grouped.items():
        if repo_key in processed:
            continue
        org_name = repo_key.split("/")[1]
        badge = f'<img src="https://img.shields.io/badge/{org_name}-181717?style=for-the-badge&logo=github&logoColor=white" />'
        pr_links = build_pr_links(pr_list, repo_key)
        description = summarize_contributions(pr_list)
        rows.append(f"| {badge} | {description} | {pr_links} |")

    return rows


def build_pr_links(pr_list, repo):
    links = []
    # Sort: merged first, then open, then closed-unmerged
    def sort_key(pr):
        if pr["merged"]:
            return 0
        if pr["current_state"] == "open":
            return 1
        return 2

    pr_list.sort(key=sort_key)

    for pr in pr_list:
        status = ""
        if pr["merged"]:
            status = " (merged)"
        link = f'[PR #{pr["number"]}]({pr["html_url"]}){status}'
        links.append(link)
    return " · ".join(links)


def summarize_contributions(pr_list):
    titles = [pr["title"] for pr in pr_list]
    # Create a brief summary from PR titles
    keywords = set()
    for title in titles:
        lower = title.lower()
        if "fix" in lower or "bug" in lower:
            keywords.add("Bug fixes")
        if "doc" in lower:
            keywords.add("Documentation")
        if "feat" in lower or "add" in lower:
            keywords.add("New features")
        if "refactor" in lower or "migrat" in lower:
            keywords.add("Refactoring")
        if "test" in lower:
            keywords.add("Testing")
        if "perf" in lower or "optim" in lower:
            keywords.add("Performance")
        if "chore" in lower or "improv" in lower:
            keywords.add("Improvements")

    if not keywords:
        keywords.add("Contributions")

    return ", ".join(sorted(keywords))


def update_readme(rows):
    with open(README_PATH, "r") as f:
        content = f.read()

    table_header = "| Organization | Contribution | Pull Requests |\n|:------------:|:-----------:|:-------------:|"
    table_body = "\n".join(rows)

    new_section = f"""{START_MARKER}
<div align="center">

{table_header}
{table_body}

</div>
{END_MARKER}"""

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    new_content = pattern.sub(new_section, content)

    if new_content != content:
        with open(README_PATH, "w") as f:
            f.write(new_content)
        print("README.md updated with latest PR statuses.")
        return True
    else:
        print("No changes needed.")
        return False


def main():
    print(f"Fetching PRs for {GITHUB_USERNAME}...")
    prs = fetch_prs()
    print(f"Found {len(prs)} PRs to external repos.")

    print("Building contributions table...")
    rows = build_table(prs)

    print("Updating README.md...")
    changed = update_readme(rows)
    # Set output for GitHub Actions
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")


if __name__ == "__main__":
    main()
