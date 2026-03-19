#!/usr/bin/env python3

import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import requests
import yaml

GITHUB_API_URL = os.environ.get("GITHUB_API_URL", "https://api.github.com")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

role_id_raw = os.environ.get("DISCORD_CHANGELOG_ROLE_ID", "").strip()
DISCORD_CHANGELOG_ROLE_ID = int(role_id_raw) if role_id_raw and role_id_raw.lower() != "none" else 0

CHANGELOG_FILE = "Resources/Changelog/ChangelogOpenspace.yml"

TYPES_TO_EMOJI = {"Fix": "🐛", "Add": "🆕", "Remove": "❌", "Tweak": "⚒️"}

EMBED_DESCRIPTION_LIMIT = 4096
EMBED_TITLE_LIMIT = 256

ChangelogEntry = dict[str, Any]

DEBUG = False
DEBUG_CHANGELOG_FILE_OLD = Path("Resources/Changelog/Old.yml")


def main():
    if not DISCORD_WEBHOOK_URL:
        print("No webhook URL; skipping send")
        return

    if DEBUG:
        last_changelog_stream = DEBUG_CHANGELOG_FILE_OLD.read_text()
    else:
        try:
            last_changelog_stream = get_last_changelog()
        except RuntimeError as e:
            print(f"No previous run found ({e}), treating as first run — sending all entries.")
            last_changelog_stream = "Entries: []"

    last_changelog = yaml.safe_load(last_changelog_stream) or {}
    with open(CHANGELOG_FILE, "r") as f:
        cur_changelog = yaml.safe_load(f) or {}

    new_entries = list(diff_changelog(last_changelog, cur_changelog))
    if not new_entries:
        print("No new entries to report.")
        return

    if DISCORD_CHANGELOG_ROLE_ID:
        ping_role_once(str(DISCORD_CHANGELOG_ROLE_ID))

    pr_groups = group_entries_by_pr(new_entries)
    for pr_id, entries in pr_groups.items():
        embed = build_embed_for_pr(pr_id, entries)
        send_embed(embed)


def get_current_run(sess: requests.Session, github_repository: str, github_run: str) -> Any:
    resp = sess.get(f"{GITHUB_API_URL}/repos/{github_repository}/actions/runs/{github_run}")
    resp.raise_for_status()
    return resp.json()


def get_past_runs(sess: requests.Session, current_run: Any) -> Any:
    params = {"status": "success", "created": f"<={current_run['created_at']}"}
    resp = sess.get(f"{current_run['workflow_url']}/runs", params=params)
    resp.raise_for_status()
    return resp.json()


def get_most_recent_workflow(sess: requests.Session, github_repository: str, github_run: str) -> Any:
    current = get_current_run(sess, github_repository, github_run)
    past = get_past_runs(sess, current)
    runs = sorted(past.get("workflow_runs", []), key=lambda r: r["created_at"], reverse=True)
    for run in runs:
        if run["id"] == current["id"]:
            continue
        return run
    raise RuntimeError("No previous successful workflow run found")


def get_last_changelog_by_sha(sess: requests.Session, sha: str, github_repository: str) -> str:
    resp = sess.get(
        f"{GITHUB_API_URL}/repos/{github_repository}/contents/{CHANGELOG_FILE}",
        headers={"Accept": "application/vnd.github.raw"},
        params={"ref": sha},
    )
    resp.raise_for_status()
    return resp.text


def get_last_changelog() -> str:
    github_repository = os.environ["GITHUB_REPOSITORY"]
    github_run = os.environ["GITHUB_RUN_ID"]
    github_token = os.environ["GITHUB_TOKEN"]

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {github_token}"
    session.headers["Accept"] = "application/vnd.github+json"
    session.headers["X-GitHub-Api-Version"] = "2022-11-28"

    most_recent = get_most_recent_workflow(session, github_repository, github_run)
    last_sha = most_recent["head_commit"]["id"]
    print(f"Last successful publish job was {most_recent['id']}: {last_sha}")
    return get_last_changelog_by_sha(session, last_sha, github_repository)


def diff_changelog(old: dict[str, Any], cur: dict[str, Any]) -> Iterable[ChangelogEntry]:
    old_ids = {e["id"] for e in old.get("Entries", [])}
    return (e for e in cur.get("Entries", []) if e["id"] not in old_ids)


def group_entries_by_pr(entries: Iterable[ChangelogEntry]) -> dict[str, list[ChangelogEntry]]:
    groups: dict[str, list[ChangelogEntry]] = {}
    for entry in entries:
        url = entry.get("url", "").strip()
        pr_id = url.rstrip("/").split("/")[-1] if url else "no-pr"
        groups.setdefault(pr_id, []).append(entry)
    return groups


def build_embed_for_pr(pr_id: str, entries: list[ChangelogEntry]) -> dict[str, Any]:
    authors = set()
    description_lines = []

    for entry in entries:
        authors.add(entry.get("author", "Unknown"))
        url = entry.get("url", "").strip() or None
        for change in entry.get("changes", []):
            emoji = TYPES_TO_EMOJI.get(change.get("type", ""), "❓")
            message = change.get("message", "").strip()
            if len(message) > 300:
                message = message[:297].rstrip() + "..."
            line = f"{emoji} {message}"
            if url and pr_id != "no-pr":
                line += f" ([#{pr_id}]({url}))"
            description_lines.append(line)

    description = "\n".join(description_lines)
    if len(description) > EMBED_DESCRIPTION_LIMIT:
        description = description[:EMBED_DESCRIPTION_LIMIT - 50].rstrip() + "\n*...truncated...*"

    sorted_authors = sorted(authors)
    title = ", ".join(sorted_authors)
    if len(title) > EMBED_TITLE_LIMIT:
        title = title[:EMBED_TITLE_LIMIT - 3].rsplit(",", 1)[0].rstrip() + "..."

    embed: dict[str, Any] = {
        "title": title,
        "description": description,
        "footer": {"text": "OpenSpace Changelog"},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if pr_id != "no-pr":
        embed["url"] = entries[0].get("url", "")
    return embed


def send_embed(embed: dict[str, Any]):
    payload = {
        "embeds": [embed],
        "allowed_mentions": {"parse": []},
    }
    post_with_retries(payload)


def ping_role_once(role_id: str):
    payload = {
        "content": f"<@&{role_id}> Новый чейнджлог!",
        "allowed_mentions": {"roles": [int(role_id)]},
    }
    post_with_retries(payload)


def post_with_retries(payload: dict[str, Any]):
    attempt = 0
    while True:
        try:
            resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            if resp.status_code == 429:
                attempt += 1
                if attempt > 20:
                    print("Too many rate limit retries; giving up", file=sys.stderr)
                    sys.exit(1)
                retry_after = resp.json().get("retry_after", 5)
                print(f"Rate limited; sleeping {retry_after}s (attempt {attempt})")
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return
        except requests.exceptions.RequestException as e:
            attempt += 1
            if attempt > 5:
                print(f"Failed after retries: {e}", file=sys.stderr)
                return
            backoff = 2 ** attempt
            print(f"Request failed ({e}), retrying in {backoff}s")
            time.sleep(backoff)


if __name__ == "__main__":
    main()
