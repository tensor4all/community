# Bluesky Announcements Forwarder Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the GitHub Discussions announcements forwarder so eligible announcement posts are also published to `tensor4all.bsky.social`.

**Architecture:** Keep the existing Python standard-library script as the single polling and delivery entry point. Add a Bluesky sender that authenticates with an app password, formats a short notification post, and publishes an `app.bsky.feed.post` record only when all enabled destinations succeed so repository state stays consistent.

**Tech Stack:** GitHub Actions, Python 3 standard library, unittest, Bluesky AT Protocol HTTP APIs

---

### Task 1: Bluesky Formatting And Sender API

**Files:**
- Modify: `tests/test_announcements.py`
- Modify: `scripts/announcements.py`

**Step 1: Write the failing test**

Add tests for:
- Bluesky post text format using title, short summary, and discussion URL
- truncation behavior so the final post stays within Bluesky text limits
- Bluesky sender config gating for dry-run and disabled mode

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL because Bluesky formatting and sender helpers do not exist yet

**Step 3: Write minimal implementation**

Implement:
- `format_bluesky_message(...)`
- Bluesky enable check from environment
- a Bluesky sender factory that logs in with app-password credentials and creates a post record

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_announcements.py scripts/announcements.py
git commit -m "feat: add bluesky announcement delivery"
```

### Task 2: Delivery Orchestration For Three Destinations

**Files:**
- Modify: `tests/test_announcements.py`
- Modify: `scripts/announcements.py`

**Step 1: Write the failing test**

Add tests for:
- marking sent only after Matrix, Google Groups, and Bluesky all succeed
- keeping state unchanged when Bluesky fails after other destinations succeed
- skipping disabled destinations while still requiring enabled ones to succeed

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL because orchestration still assumes only Matrix and Google Groups

**Step 3: Write minimal implementation**

Implement:
- sender selection for enabled destinations
- generalized delivery loop across destination senders
- unchanged state semantics when any enabled sender fails

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_announcements.py scripts/announcements.py
git commit -m "refactor: generalize announcement delivery targets"
```

### Task 3: Workflow And Documentation Wiring

**Files:**
- Modify: `.github/workflows/forward-announcements.yml`
- Modify: `docs/plans/2026-03-18-announcements-distribution-design.md`
- Modify: `tests/test_announcements.py`
- Modify: `scripts/announcements.py`

**Step 1: Write the failing test**

Add tests for:
- CLI dry-run with Bluesky enabled still succeeding against fixtures
- environment parsing for Bluesky credentials and service URL defaults

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest discover -s tests -v`
Expected: FAIL because the CLI and workflow do not wire Bluesky yet

**Step 3: Write minimal implementation**

Implement:
- workflow env wiring for Bluesky secrets
- optional Bluesky service URL env with default `https://bsky.social`
- design doc update to include Bluesky as a distribution target and required secrets

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS

**Step 5: Commit**

```bash
git add .github/workflows/forward-announcements.yml docs/plans/2026-03-18-announcements-distribution-design.md tests/test_announcements.py scripts/announcements.py
git commit -m "docs: wire bluesky announcement forwarding"
```
