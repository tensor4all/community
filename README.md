# tensor4all community announcements

This repository forwards GitHub Discussions announcements to the tensor4all community channels.

## Overview

GitHub Discussions in the `Announcements` category are treated as the source of truth.
A GitHub Actions workflow polls for unsent announcements and forwards them to:

- Matrix
- Google Groups
- Bluesky (`tensor4all.bsky.social`)

After all enabled deliveries succeed, the workflow updates [`state/sent-announcements.json`](state/sent-announcements.json).

## How It Works

1. Create a post in GitHub Discussions under `Announcements`.
2. GitHub Actions runs on schedule or via `workflow_dispatch`.
3. Eligible unsent announcements are forwarded to downstream channels.
4. The sent-state file is committed back to this repository.

## Repository Layout

- [`scripts/announcements.py`](scripts/announcements.py): polling, filtering, formatting, and delivery logic
- [`.github/workflows/forward-announcements.yml`](.github/workflows/forward-announcements.yml): scheduled/manual workflow
- [`state/sent-announcements.json`](state/sent-announcements.json): sent-state tracked in git
- [`tests/test_announcements.py`](tests/test_announcements.py): regression tests for eligibility, formatting, and orchestration

## Required GitHub Secrets

### Matrix

- `MATRIX_HOMESERVER_URL`
- `MATRIX_ACCESS_TOKEN`
- `MATRIX_ROOM_ID`

### Google Groups

- `GOOGLE_GROUPS_SMTP_HOST`
- `GOOGLE_GROUPS_SMTP_PORT`
- `GOOGLE_GROUPS_SMTP_USERNAME`
- `GOOGLE_GROUPS_SMTP_APP_PASSWORD`
- `GOOGLE_GROUPS_TO_ADDRESS`

### Bluesky

- `BLUESKY_IDENTIFIER`
- `BLUESKY_APP_PASSWORD`

Optional:

- `BLUESKY_SERVICE_URL`

## Local Verification

Run the test suite:

```bash
python3 -m unittest discover -s tests -v
```

Run the forwarder in dry-run mode:

```bash
python3 scripts/announcements.py --dry-run
```

You can also point the script at fixture data with `GITHUB_DISCUSSIONS_FIXTURE=/path/to/discussions.json`.

## Operational Notes

- Only posts in the `Announcements` category are forwarded.
- A post is marked as sent only after all enabled destinations succeed.
- If any enabled destination fails, the post remains pending and will be retried later.
- Downstream messages always include the original GitHub Discussions URL.
- Secret values must not be committed to the repository.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
