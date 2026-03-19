import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import ANY, patch

from scripts.announcements import (
    bluesky_enabled,
    bluesky_sender_from_env,
    format_bluesky_message,
    format_google_groups_message,
    format_matrix_message,
    is_eligible_discussion,
    load_state,
    process_discussions,
    save_state,
)


def make_discussion(*, discussion_id="D_discussion_1", created_at=None, category="Announcements"):
    if created_at is None:
        created_at = datetime.now(UTC) - timedelta(hours=2)
    return {
        "id": discussion_id,
        "title": "Launch update",
        "body": "Line one.\n\nLine two.\n\nhttps://tensor4all.org/update",
        "url": "https://github.com/orgs/tensor4all/discussions/1",
        "createdAt": created_at.isoformat().replace("+00:00", "Z"),
        "author": {"login": "hiroshi", "name": "Hiroshi Shinaoka"},
        "category": {"name": category},
    }


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class EligibilityTests(unittest.TestCase):
    def test_eligible_when_announcement_old_enough_and_unsent(self):
        discussion = make_discussion()
        now = datetime.now(UTC)

        self.assertTrue(
            is_eligible_discussion(discussion=discussion, sent_ids=set(), now=now, minimum_age_minutes=10)
        )

    def test_ineligible_when_not_in_announcements(self):
        discussion = make_discussion(category="Q&A")

        self.assertFalse(
            is_eligible_discussion(
                discussion=discussion,
                sent_ids=set(),
                now=datetime.now(UTC),
                minimum_age_minutes=10,
            )
        )

    def test_ineligible_when_too_new_or_already_sent(self):
        recent = make_discussion(created_at=datetime.now(UTC) - timedelta(minutes=5))
        sent = make_discussion(discussion_id="D_discussion_2")

        self.assertFalse(
            is_eligible_discussion(
                discussion=recent,
                sent_ids=set(),
                now=datetime.now(UTC),
                minimum_age_minutes=10,
            )
        )
        self.assertFalse(
            is_eligible_discussion(
                discussion=sent,
                sent_ids={"D_discussion_2"},
                now=datetime.now(UTC),
                minimum_age_minutes=10,
            )
        )


class FormattingTests(unittest.TestCase):
    def test_matrix_message_contains_title_summary_and_url(self):
        discussion = make_discussion()

        message = format_matrix_message(discussion, summary_line_limit=2)

        self.assertIn("Launch update", message)
        self.assertIn("Line one.", message)
        self.assertIn("Line two.", message)
        self.assertIn(discussion["url"], message)

    def test_google_groups_message_contains_metadata_body_and_url(self):
        discussion = make_discussion()

        subject, body = format_google_groups_message(discussion)

        self.assertEqual(subject, "Launch update")
        self.assertIn("Author: Hiroshi Shinaoka", body)
        self.assertIn("Line one.", body)
        self.assertIn("Discussion URL:", body)
        self.assertIn(discussion["url"], body)

    def test_google_groups_message_falls_back_to_login_when_name_missing(self):
        discussion = make_discussion()
        discussion["author"] = {"login": "hiroshi"}

        _, body = format_google_groups_message(discussion)

        self.assertIn("Author: hiroshi", body)

    def test_bluesky_message_contains_title_summary_and_url(self):
        discussion = make_discussion()

        message = format_bluesky_message(discussion)

        self.assertIn("Launch update", message)
        self.assertIn("Line one.", message)
        self.assertIn("Line two.", message)
        self.assertIn(discussion["url"], message)

    def test_bluesky_message_truncates_summary_to_fit_post_limit(self):
        discussion = make_discussion()
        discussion["body"] = "\n".join(["A" * 120, "B" * 120, "C" * 120])

        message = format_bluesky_message(discussion, max_length=120)

        self.assertLessEqual(len(message), 120)
        self.assertIn(discussion["url"], message)
        self.assertIn("...", message)


class BlueskyConfigTests(unittest.TestCase):
    def test_bluesky_enabled_reads_env_flag(self):
        with patch.dict(os.environ, {"ENABLE_BLUESKY": "true"}, clear=False):
            self.assertTrue(bluesky_enabled())

        with patch.dict(os.environ, {"ENABLE_BLUESKY": "false"}, clear=False):
            self.assertFalse(bluesky_enabled())

    def test_bluesky_sender_creates_session_and_post_record(self):
        discussion = make_discussion()

        with patch.dict(
            os.environ,
            {
                "BLUESKY_IDENTIFIER": "tensor4all.bsky.social",
                "BLUESKY_APP_PASSWORD": "app-password",
            },
            clear=True,
        ):
            with patch(
                "scripts.announcements.request.urlopen",
                side_effect=[
                    FakeResponse({"accessJwt": "access-token", "did": "did:plc:tensor4all"}),
                    FakeResponse({"uri": "at://did/app.bsky.feed.post/123", "cid": "bafy-test"}),
                ],
            ) as mock_urlopen:
                sender = bluesky_sender_from_env()
                sender(discussion)

        session_request = mock_urlopen.call_args_list[0].args[0]
        create_request = mock_urlopen.call_args_list[1].args[0]
        session_payload = json.loads(session_request.data.decode("utf-8"))
        create_payload = json.loads(create_request.data.decode("utf-8"))

        self.assertEqual(
            session_request.full_url,
            "https://bsky.social/xrpc/com.atproto.server.createSession",
        )
        self.assertEqual(
            create_request.full_url,
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
        )
        self.assertEqual(
            session_payload,
            {"identifier": "tensor4all.bsky.social", "password": "app-password"},
        )
        self.assertEqual(create_payload["repo"], "did:plc:tensor4all")
        self.assertEqual(create_payload["collection"], "app.bsky.feed.post")
        self.assertEqual(create_payload["record"]["$type"], "app.bsky.feed.post")
        self.assertEqual(
            create_payload["record"]["text"],
            format_bluesky_message(discussion),
        )
        self.assertIn(("Authorization", "Bearer access-token"), create_request.header_items())

    def test_bluesky_sender_defers_authentication_until_delivery(self):
        with patch.dict(
            os.environ,
            {
                "BLUESKY_IDENTIFIER": "tensor4all.bsky.social",
                "BLUESKY_APP_PASSWORD": "app-password",
            },
            clear=True,
        ):
            with patch("scripts.announcements.request.urlopen") as mock_urlopen:
                bluesky_sender_from_env()

        self.assertEqual(mock_urlopen.call_count, 0)


class StateTests(unittest.TestCase):
    def test_load_state_returns_empty_sent_ids_for_missing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "missing.json"

            self.assertEqual(load_state(state_path), {"sent_ids": {}})

    def test_process_discussions_marks_sent_only_after_all_enabled_deliveries_succeed(self):
        discussion = make_discussion()
        calls = []

        def send_matrix(item):
            calls.append(("matrix", item["id"]))

        def send_email(item):
            calls.append(("email", item["id"]))

        def send_bluesky(item):
            calls.append(("bluesky", item["id"]))

        result = process_discussions(
            discussions=[discussion],
            state={"sent_ids": {}},
            now=datetime.now(UTC),
            minimum_age_minutes=10,
            senders=[send_matrix, send_email, send_bluesky],
        )

        self.assertEqual(result["sent_ids"], {"D_discussion_1": ANY})
        self.assertEqual(len(calls), 3)

    def test_process_discussions_leaves_state_unchanged_on_partial_failure(self):
        discussion = make_discussion()
        calls = []

        def send_matrix(item):
            calls.append(("matrix", item["id"]))
            return None

        def send_email(item):
            calls.append(("email", item["id"]))
            return None

        def send_bluesky(item):
            calls.append(("bluesky", item["id"]))
            raise RuntimeError("bsky failed")

        result = process_discussions(
            discussions=[discussion],
            state={"sent_ids": {}},
            now=datetime.now(UTC),
            minimum_age_minutes=10,
            senders=[send_matrix, send_email, send_bluesky],
        )

        self.assertEqual(result["sent_ids"], {})
        self.assertEqual(
            calls,
            [("matrix", "D_discussion_1"), ("email", "D_discussion_1"), ("bluesky", "D_discussion_1")],
        )

    def test_process_discussions_skips_disabled_destinations_by_omitting_senders(self):
        discussion = make_discussion()
        calls = []

        def send_matrix(item):
            calls.append(("matrix", item["id"]))

        def send_bluesky(item):
            calls.append(("bluesky", item["id"]))

        result = process_discussions(
            discussions=[discussion],
            state={"sent_ids": {}},
            now=datetime.now(UTC),
            minimum_age_minutes=10,
            senders=[send_matrix, send_bluesky],
        )

        self.assertEqual(result["sent_ids"], {"D_discussion_1": ANY})
        self.assertEqual(calls, [("matrix", "D_discussion_1"), ("bluesky", "D_discussion_1")])

    def test_save_state_writes_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "sent-announcements.json"
            state = {"sent_ids": {"D_discussion_1": "2026-03-18T00:00:00Z"}}

            save_state(state_path, state)

            written = json.loads(state_path.read_text())
            self.assertEqual(written, state)


class CliTests(unittest.TestCase):
    def test_cli_dry_run_processes_fixture_discussions_with_bluesky_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fixture_path = temp_path / "discussions.json"
            state_path = temp_path / "state.json"
            fixture_path.write_text(json.dumps({"discussions": [make_discussion()]}))
            state_path.write_text(json.dumps({"sent_ids": {}}))

            result = subprocess.run(
                [sys.executable, "scripts/announcements.py", "--dry-run"],
                cwd=Path(__file__).resolve().parents[1],
                env={
                    **os.environ,
                    "GITHUB_DISCUSSIONS_FIXTURE": str(fixture_path),
                    "ANNOUNCEMENTS_STATE_PATH": str(state_path),
                    "ANNOUNCEMENTS_MINIMUM_AGE_MINUTES": "10",
                    "ENABLE_BLUESKY": "true",
                },
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Processed 1 discussion(s); delivered 1.", result.stdout)


if __name__ == "__main__":
    unittest.main()
