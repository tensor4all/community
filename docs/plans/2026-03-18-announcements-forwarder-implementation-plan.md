# Announcements Forwarder Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a minimal GitHub Actions based forwarder that polls GitHub Discussions announcements and forwards eligible new posts to Matrix and Google Groups.

**Architecture:** A scheduled workflow runs a Python script that loads sent-state from a JSON file, fetches announcement discussions from GitHub, filters unsent items older than 10 minutes, formats destination-specific messages, sends them to Matrix and Gmail SMTP, then updates repository state only after both deliveries succeed.

**Tech Stack:** GitHub Actions, Python 3 standard library, unittest

---

### Task 1: Core Eligibility And Formatting

**Files:**
- Create: `tests/test_announcements.py`
- Create: `scripts/announcements.py`

**Step 1: Write the failing test**

Write tests for:
- eligibility based on category, age, and sent-state
- Matrix summary formatting
- Google Groups plain-text formatting

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest -v`
Expected: FAIL because `scripts.announcements` does not exist yet

**Step 3: Write minimal implementation**

Implement only the functions needed by the tests:
- `is_eligible_discussion(...)`
- `format_matrix_message(...)`
- `format_google_groups_message(...)`

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_announcements.py scripts/announcements.py
git commit -m "feat: add announcement eligibility and formatting"
```

### Task 2: State Management And Send Orchestration

**Files:**
- Modify: `tests/test_announcements.py`
- Modify: `scripts/announcements.py`
- Create: `state/sent-announcements.json`

**Step 1: Write the failing test**

Add tests for:
- loading empty state
- updating state after success
- leaving state unchanged on partial delivery failure

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest -v`
Expected: FAIL because orchestration/state functions are missing

**Step 3: Write minimal implementation**

Implement:
- state file loaders/savers
- delivery orchestration that only records success after both sends succeed

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_announcements.py scripts/announcements.py state/sent-announcements.json
git commit -m "feat: add delivery state management"
```

### Task 3: CLI Entry Point And Workflow Integration

**Files:**
- Modify: `tests/test_announcements.py`
- Modify: `scripts/announcements.py`
- Create: `.github/workflows/forward-announcements.yml`
- Create: `.gitignore`

**Step 1: Write the failing test**

Add tests for:
- CLI using fixture discussions JSON
- selecting eligible items only
- returning success when nothing is pending

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest -v`
Expected: FAIL because CLI entry point is incomplete

**Step 3: Write minimal implementation**

Implement:
- environment-driven CLI
- dry-run support for local verification
- scheduled workflow wiring

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_announcements.py scripts/announcements.py .github/workflows/forward-announcements.yml .gitignore
git commit -m "feat: add announcement forwarder workflow"
```
