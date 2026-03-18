#!/usr/bin/env python3

import argparse
import json
import os
import smtplib
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Callable
from urllib import error, parse, request


GraphqlQuery = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    discussions(first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        id
        title
        body
        url
        createdAt
        author {
          login
        }
        category {
          name
        }
      }
    }
  }
}
"""


@dataclass
class DeliveryResult:
    delivered_count: int
    sent_ids: dict[str, str]


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def summarize_body(body: str, summary_line_limit: int = 2) -> str:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return "\n".join(lines[:summary_line_limit])


def is_eligible_discussion(
    discussion: dict, sent_ids: set[str], now: datetime, minimum_age_minutes: int
) -> bool:
    category_name = ((discussion.get("category") or {}).get("name") or "").strip()
    if category_name != "Announcements":
        return False
    if discussion["id"] in sent_ids:
        return False
    created_at = parse_timestamp(discussion["createdAt"])
    return now - created_at >= timedelta(minutes=minimum_age_minutes)


def format_matrix_message(discussion: dict, summary_line_limit: int = 2) -> str:
    summary = summarize_body(discussion.get("body", ""), summary_line_limit=summary_line_limit)
    parts = [discussion["title"]]
    if summary:
        parts.extend(["", summary])
    parts.extend(["", discussion["url"]])
    return "\n".join(parts)


def format_google_groups_message(discussion: dict) -> tuple[str, str]:
    author = ((discussion.get("author") or {}).get("login")) or "unknown"
    body = discussion.get("body", "").strip()
    message = "\n".join(
        [
            f"Author: {author}",
            f"Created: {discussion['createdAt']}",
            "",
            body,
            "",
            "Discussion URL:",
            discussion["url"],
        ]
    ).strip()
    return discussion["title"], message


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"sent_ids": {}}
    data = json.loads(path.read_text())
    data.setdefault("sent_ids", {})
    return data


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def process_discussions(
    discussions: list[dict],
    state: dict,
    now: datetime,
    minimum_age_minutes: int,
    matrix_sender: Callable[[dict, str], None],
    google_groups_sender: Callable[[dict, str, str], None],
) -> dict:
    next_state = deepcopy(state)
    next_state.setdefault("sent_ids", {})

    for discussion in discussions:
        if not is_eligible_discussion(
            discussion=discussion,
            sent_ids=set(next_state["sent_ids"].keys()),
            now=now,
            minimum_age_minutes=minimum_age_minutes,
        ):
            continue

        matrix_message = format_matrix_message(discussion)
        subject, email_body = format_google_groups_message(discussion)
        try:
            matrix_sender(discussion, matrix_message)
            google_groups_sender(discussion, subject, email_body)
        except Exception:
            continue
        next_state["sent_ids"][discussion["id"]] = now.isoformat().replace("+00:00", "Z")

    return next_state


def load_discussions_from_fixture(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    return data.get("discussions", [])


def graphql_request(query: str, variables: dict, token: str) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "tensor4all-announcements-forwarder",
        },
        method="POST",
    )
    with request.urlopen(req) as response:
        return json.loads(response.read())


def load_discussions_from_github(owner: str, name: str, token: str) -> list[dict]:
    discussions = []
    cursor = None

    while True:
        response = graphql_request(GraphqlQuery, {"owner": owner, "name": name, "cursor": cursor}, token)
        if response.get("errors"):
            raise RuntimeError(f"GitHub GraphQL error: {response['errors']}")
        nodes = response["data"]["repository"]["discussions"]["nodes"]
        page_info = response["data"]["repository"]["discussions"]["pageInfo"]
        discussions.extend(nodes)
        if not page_info["hasNextPage"]:
            return discussions
        cursor = page_info["endCursor"]


def matrix_sender_from_env() -> Callable[[dict, str], None]:
    homeserver_url = os.environ["MATRIX_HOMESERVER_URL"].rstrip("/")
    room_id = os.environ["MATRIX_ROOM_ID"]
    access_token = os.environ["MATRIX_ACCESS_TOKEN"]

    def sender(discussion: dict, message: str) -> None:
        txn_id = parse.quote(discussion["id"], safe="")
        room = parse.quote(room_id, safe="")
        endpoint = f"{homeserver_url}/_matrix/client/v3/rooms/{room}/send/m.room.message/{txn_id}"
        payload = json.dumps({"msgtype": "m.text", "body": message}).encode("utf-8")
        req = request.Request(
            endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            method="PUT",
        )
        with request.urlopen(req):
            return None

    return sender


def google_groups_sender_from_env() -> Callable[[dict, str, str], None]:
    smtp_host = os.environ.get("GOOGLE_GROUPS_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("GOOGLE_GROUPS_SMTP_PORT", "587"))
    smtp_username = os.environ["GOOGLE_GROUPS_SMTP_USERNAME"]
    smtp_password = os.environ["GOOGLE_GROUPS_SMTP_APP_PASSWORD"]
    to_address = os.environ["GOOGLE_GROUPS_TO_ADDRESS"]

    def sender(_: dict, subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = smtp_username
        message["To"] = to_address
        message.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)

    return sender


def google_groups_enabled() -> bool:
    return os.environ.get("ENABLE_GOOGLE_GROUPS", "false").lower() == "true"


def dry_run_matrix_sender(_: dict, __: str) -> None:
    return None


def dry_run_google_groups_sender(_: dict, __: str, ___: str) -> None:
    return None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    state_path = Path(os.environ.get("ANNOUNCEMENTS_STATE_PATH", "state/sent-announcements.json"))
    minimum_age_minutes = int(os.environ.get("ANNOUNCEMENTS_MINIMUM_AGE_MINUTES", "10"))

    fixture = os.environ.get("GITHUB_DISCUSSIONS_FIXTURE")
    if fixture:
        discussions = load_discussions_from_fixture(Path(fixture))
    else:
        owner = os.environ["GITHUB_SOURCE_OWNER"]
        repo = os.environ["GITHUB_SOURCE_REPO"]
        token = os.environ["GITHUB_TOKEN"]
        discussions = load_discussions_from_github(owner, repo, token)

    state = load_state(state_path)
    sender_matrix = dry_run_matrix_sender if args.dry_run else matrix_sender_from_env()
    if args.dry_run:
        sender_groups = dry_run_google_groups_sender
    elif google_groups_enabled():
        sender_groups = google_groups_sender_from_env()
    else:
        sender_groups = dry_run_google_groups_sender

    next_state = process_discussions(
        discussions=discussions,
        state=state,
        now=datetime.now(UTC),
        minimum_age_minutes=minimum_age_minutes,
        matrix_sender=sender_matrix,
        google_groups_sender=sender_groups,
    )
    delivered_count = len(next_state["sent_ids"]) - len(state["sent_ids"])

    if not args.dry_run:
        save_state(state_path, next_state)

    print(f"Processed {len(discussions)} discussion(s); delivered {delivered_count}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except error.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:  # pragma: no cover - CLI safeguard
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
