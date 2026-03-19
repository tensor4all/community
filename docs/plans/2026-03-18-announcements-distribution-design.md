# Announcements Distribution Design

## Goal

Use GitHub Discussions as the source of truth for `tensor4all` announcements and forward new announcement posts to:

- Matrix
- Google Groups
- Bluesky

This design intentionally optimizes for simple, reliable one-way distribution rather than full cross-platform synchronization.

## Source Of Truth

- Canonical source: GitHub organization Discussions
- Category: `Announcements`
- Category format: `Announcement`

Using the `Announcement` format is important because GitHub restricts new post creation in that category to users with `maintain` or `admin` permissions on the source repository. This is the only category that needs stricter posting control.

## Desired Behavior

When a new post is created in `Announcements`:

1. A scheduled or manually triggered workflow checks periodically for unsent posts.
2. Eligible unsent posts are forwarded to all enabled downstream destinations.
3. After every enabled delivery succeeds, the post is marked as sent in repository state.

## Delivery Schedule

- Trigger model: scheduled GitHub Actions polling
- Frequency: once per hour
- Manual trigger: `workflow_dispatch`
- Eligibility rule:
  - post is in `Announcements`
  - post has not been sent before

Rationale:

- simpler than event-driven delayed execution
- easy to test by running the workflow manually
- acceptable latency for announcement-style communication

## Distribution Targets

### Matrix

- Destination: existing community room
- Delivery method: direct Matrix Client-Server API call
- Sender: dedicated bot account
- Authentication: Matrix access token stored in GitHub Actions secrets

Required secrets:

- `MATRIX_HOMESERVER_URL`
- `MATRIX_ACCESS_TOKEN`
- `MATRIX_ROOM_ID`
- `MATRIX_BOT_USER_ID`

Expected message style:

- short summary
- original discussion URL

Matrix is treated as a notification channel, not an archive mirror.

### Google Groups

- Destination: target Google Group posting address
- Delivery method: Gmail SMTP
- Sender: `tensor4all.bot@gmail.com`
- Authentication: Gmail App Password stored in GitHub Actions secrets

Required secrets:

- `GOOGLE_GROUPS_SMTP_HOST`
- `GOOGLE_GROUPS_SMTP_PORT`
- `GOOGLE_GROUPS_SMTP_USERNAME`
- `GOOGLE_GROUPS_SMTP_APP_PASSWORD`
- `GOOGLE_GROUPS_TO_ADDRESS`

Assumptions:

- `tensor4all.bot@gmail.com` has 2-Step Verification enabled
- an App Password has been created for SMTP use
- the Google Group allows posts from `tensor4all.bot@gmail.com`

Expected email style:

- plain text
- full body or near-full body
- original discussion URL included explicitly

Plain text is sufficient because the URL is the important payload and most mail clients will auto-link a full `https://...` URL.

### Bluesky

- Destination: `tensor4all.bsky.social`
- Delivery method: direct AT Protocol HTTP calls to the account's PDS
- Sender: dedicated bot account
- Authentication: Bluesky app password stored in GitHub Actions secrets

Required secrets:

- `BLUESKY_IDENTIFIER`
- `BLUESKY_APP_PASSWORD`

Optional configuration:

- `BLUESKY_SERVICE_URL`

Expected post style:

- title
- short summary derived from the discussion body
- original discussion URL

Bluesky is treated as a notification channel, not a full-content mirror. Post text should stay within Bluesky limits, truncating the summary if needed while preserving the discussion URL.

## Message Formatting

### Matrix format

Recommended structure:

- title
- short summary derived from the discussion body
- original GitHub Discussions URL

This should stay concise to fit chat consumption.

### Google Groups format

Recommended structure:

- title as email subject
- author
- created time
- discussion body in plain text
- original GitHub Discussions URL

This should favor readability and link integrity over rich formatting.

### Bluesky format

Recommended structure:

- title
- short summary derived from the discussion body
- original GitHub Discussions URL

This should stay concise like Matrix while respecting Bluesky post length limits.

## State Management

Delivery state is stored in the repository as a JSON file.

Suggested path:

- `state/sent-announcements.json`

Suggested contents:

- sent GitHub Discussion node IDs or stable discussion IDs
- optional metadata such as `sent_at`

Why repository state:

- simple
- visible
- easy to recover
- no external datastore required

## Delivery Semantics

- A post is marked sent only after all enabled destinations succeed.
- If any enabled destination fails, the post remains unsent in state.
- A later scheduled run retries it.

This keeps retry logic simple and avoids partially advanced state.

During rollout, Google Groups or Bluesky delivery may be disabled while another destination is validated. In that mode, enabled destinations remain active and disabled ones are skipped by configuration.

## Permissions Model

Permissions are intentionally strict only for `Announcements`.

- `Announcements`: restricted by using GitHub's `Announcement` category format
- other categories: normal Discussions behavior

This allows broader community use elsewhere without weakening the announcement publishing path.

## Security And Secrets

Secrets should be stored in GitHub Actions secrets.

Sensitive values include:

- Matrix access token
- Gmail App Password
- Bluesky app password
- destination addresses and room identifiers where appropriate

No plaintext credentials should be committed into the repository.

## Operational Notes

- The workflow should fetch current discussion content at send time, not creation time.
- If a post is deleted before it becomes eligible, it should not be sent.
- If a post is moved out of `Announcements` before send time, it should not be sent.
- The original GitHub Discussions URL must always be included in downstream messages.

## Out Of Scope

The following are intentionally not part of the first implementation:

- forwarding comments
- forwarding edits as follow-up updates
- reverse sync from Matrix to GitHub
- reverse sync from Google Groups to GitHub
- reverse sync from Bluesky to GitHub
- HTML email rendering
- per-category fine-grained posting ACL beyond GitHub's built-in `Announcement` behavior
- deletion propagation after a message has already been delivered

## Implementation Sketch

Minimal implementation can be split into:

1. A scheduled GitHub Actions workflow
2. A script that queries GitHub Discussions for eligible posts
3. A Matrix sender
4. A Google Groups SMTP sender
5. A Bluesky sender
6. A state file updater

## Open Follow-Up Items

These items are still implementation details, not design blockers:

- exact GitHub API query shape for organization Discussions
- exact summary generation rule for Matrix messages
- exact summary truncation rule for Bluesky posts
- exact JSON schema for `state/sent-announcements.json`
- commit strategy for state updates from GitHub Actions
