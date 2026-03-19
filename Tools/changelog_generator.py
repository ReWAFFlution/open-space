#!/usr/bin/env python3

import os
import re
import sys
import yaml
import requests
from datetime import datetime, timezone

CHANGELOG_DIR = os.environ["CHANGELOG_DIR"]
PR_NUMBER = os.environ["PR_NUMBER"]
GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]
GH_PAT = os.environ.get("GH_PAT")

HEADER_REGEX = re.compile(r"^\s*(?::cl:|🆑)\s*([a-z0-9_\- ]+)?\s*$", re.IGNORECASE | re.MULTILINE)
ENTRY_REGEX = re.compile(r"^\s*[-*]?\s*(add|remove|tweak|fix):\s*(.+)$", re.IGNORECASE | re.MULTILINE)
COMMENT_REGEX = re.compile(r"<!--.*?-->", re.DOTALL)

VALID_TYPES = {"add": "Add", "remove": "Remove", "tweak": "Tweak", "fix": "Fix"}


def log(msg):
    print(f"[{datetime.now().isoformat()}] {msg}")


def fetch_pr():
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/pulls/{PR_NUMBER}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GH_PAT:
        headers["Authorization"] = f"Bearer {GH_PAT}"

    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def parse_changelog(body: str, pr_author: str):
    body = COMMENT_REGEX.sub("", body)

    header = HEADER_REGEX.search(body)
    if not header:
        log("No :cl: header found, skipping.")
        return None, None

    author = (header.group(1) or "").strip() or pr_author

    entries = []
    for match in ENTRY_REGEX.finditer(body):
        raw_type = match.group(1).lower()
        message = match.group(2).strip()
        if raw_type in VALID_TYPES and message:
            entries.append({"type": VALID_TYPES[raw_type], "message": message})

    return author, entries


def get_next_id():
    if not os.path.exists(CHANGELOG_DIR):
        return 1

    with open(CHANGELOG_DIR, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    entries = data.get("Entries", [])
    if not entries:
        return 1

    return max(e.get("id", 0) for e in entries) + 1


def write_changelog(entry: dict):
    data = {"Entries": []}

    if os.path.exists(CHANGELOG_DIR):
        with open(CHANGELOG_DIR, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {"Entries": []}

    data["Entries"].append(entry)

    with open(CHANGELOG_DIR, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    log(f"Written entry ID={entry['id']} author={entry['author']} changes={len(entry['changes'])}")


def main():
    log(f"Processing PR #{PR_NUMBER} in {GITHUB_REPOSITORY}")

    pr = fetch_pr()

    if not pr.get("merged_at"):
        log("PR not merged, skipping.")
        return

    body = pr.get("body") or ""
    pr_author = pr["user"]["login"]

    author, entries = parse_changelog(body, pr_author)

    if author is None or not entries:
        log("No valid changelog entries found, skipping.")
        return

    log(f"Author: {author}, entries: {len(entries)}")

    merged_at = pr["merged_at"].replace("Z", ".000000+00:00")

    entry = {
        "author": author,
        "changes": entries,
        "id": get_next_id(),
        "time": merged_at,
        "url": f"https://github.com/{GITHUB_REPOSITORY}/pull/{PR_NUMBER}",
    }

    write_changelog(entry)
    log("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)
