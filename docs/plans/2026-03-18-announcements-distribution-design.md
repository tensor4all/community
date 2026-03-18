# Announcements Distribution Design

## Goal

Use GitHub Discussions as the source of truth for `tensor4all` announcements and forward new announcement posts to:

- Matrix
- Google Groups

This design intentionally optimizes for simple, reliable one-way distribution rather than full cross-platform synchronization.

## Source Of Truth

- Canonical source: GitHub organization Discussions
- Category: `Announcements`
- Category format: `Announcement`

Using the `Announcement` format is important because GitHub restricts new post creation in that category to users with `maintain` or `admin` permissions on the source repository. This is the only category that needs stricter posting control.

## Desired Behavior

When a new post is created in `Announcements`:

1. It is not sent immediately.
2. A scheduled workflow checks periodically for unsent posts.
3. A post becomes eligible for forwarding only after at least 10 minutes have passed since creation.
4. Eligible unsent posts are forwarded to Matrix and Google Groups.
5. After both deliveries succeed, the post is marked as sent in repository state.

This gives a short correction window for typo fixes or link fixes without introducing a manual review flow.

## Delivery Schedule

- Trigger model: scheduled GitHub Actions polling
- Frequency: once per hour
- Eligibility rule:
  - post is in `Announcements`
  - post has not been sent before
  - post was created at least 10 minutes earlier

Rationale:

- simpler than event-driven delayed execution
- fewer workflow runs than 5-minute polling
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

- A post is marked sent only after both Matrix and Google Groups delivery succeed.
- If either destination fails, the post remains unsent in state.
- A later scheduled run retries it.

This keeps retry logic simple and avoids partially advanced state.

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
- HTML email rendering
- per-category fine-grained posting ACL beyond GitHub's built-in `Announcement` behavior
- deletion propagation after a message has already been delivered

## Implementation Sketch

Minimal implementation can be split into:

1. A scheduled GitHub Actions workflow
2. A script that queries GitHub Discussions for eligible posts
3. A Matrix sender
4. A Google Groups SMTP sender
5. A state file updater

## Open Follow-Up Items

These items are still implementation details, not design blockers:

- exact GitHub API query shape for organization Discussions
- exact summary generation rule for Matrix messages
- exact JSON schema for `state/sent-announcements.json`
- commit strategy for state updates from GitHub Actions
