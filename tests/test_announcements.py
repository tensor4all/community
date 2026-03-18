import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import ANY

from scripts.announcements import (
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
        "author": {"login": "hiroshi"},
        "category": {"name": category},
    }


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
        self.assertIn("Author: hiroshi", body)
        self.assertIn("Line one.", body)
        self.assertIn("Discussion URL:", body)
        self.assertIn(discussion["url"], body)


class StateTests(unittest.TestCase):
    def test_load_state_returns_empty_sent_ids_for_missing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "missing.json"

            self.assertEqual(load_state(state_path), {"sent_ids": {}})

    def test_process_discussions_marks_sent_only_after_both_deliveries_succeed(self):
        discussion = make_discussion()
        calls = []

        def send_matrix(item, message):
            calls.append(("matrix", item["id"], message))

        def send_email(item, subject, body):
            calls.append(("email", item["id"], subject, body))

        result = process_discussions(
            discussions=[discussion],
            state={"sent_ids": {}},
            now=datetime.now(UTC),
            minimum_age_minutes=10,
            matrix_sender=send_matrix,
            google_groups_sender=send_email,
        )

        self.assertEqual(result["sent_ids"], {"D_discussion_1": ANY})
        self.assertEqual(len(calls), 2)

    def test_process_discussions_leaves_state_unchanged_on_partial_failure(self):
        discussion = make_discussion()

        def send_matrix(item, message):
            return None

        def send_email(item, subject, body):
            raise RuntimeError("smtp failed")

        result = process_discussions(
            discussions=[discussion],
            state={"sent_ids": {}},
            now=datetime.now(UTC),
            minimum_age_minutes=10,
            matrix_sender=send_matrix,
            google_groups_sender=send_email,
        )

        self.assertEqual(result["sent_ids"], {})

    def test_save_state_writes_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "sent-announcements.json"
            state = {"sent_ids": {"D_discussion_1": "2026-03-18T00:00:00Z"}}

            save_state(state_path, state)

            written = json.loads(state_path.read_text())
            self.assertEqual(written, state)


class CliTests(unittest.TestCase):
    def test_cli_dry_run_processes_fixture_discussions(self):
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
                },
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Processed 1 discussion(s); delivered 1.", result.stdout)


if __name__ == "__main__":
    unittest.main()
