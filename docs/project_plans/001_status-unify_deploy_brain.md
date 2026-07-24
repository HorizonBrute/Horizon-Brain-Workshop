---
type: project_plan
title: "Project 001 — Unify the brain deployer (Status)"
description: Live per-item status for Project 001. CLOSED 2026-07-24 — see the closeout NOTE 001-11.
tags: [project-plan, status, deployer]
timestamp: 2026-07-21
status: closed
---

# Project 001 — Status  ·  ✅ CLOSED 2026-07-24

Plan detail: `001_detail-unify_deploy_brain.md`.
Orientation (read this instead of a handoff): `001_current_orientation-unify_deploy_brain.md`.
**Archived work-item blocks + full decision log (NOTE 001-1…10):** `001_status_archive-unify_deploy_brain.md`.
**Bugs & tech debt (BUG-001-1…8, DEBT-001-1…5):** `001_bugs_and_technical_debt-unify_deploy_brain.md`.

**Status legend:** `NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `DONE` · `VERIFIED` · `DROPPED`.

All eight Sections reached `VERIFIED`/`DONE` and their blocks are in the archive. This live doc now
holds only the closeout note.

---

# Objective Notes & Mini-Decisions (serialized)

NOTE 001-1 … 001-10 are archived in `001_status_archive-unify_deploy_brain.md`. The closeout note follows.

## NOTE 001-11 | 2026-07-24 | Project close
- Status: RESOLVED (project CLOSED)
- **Outcome:** Shipped exactly what was planned and more. `windows_deploy_brain.py` was extended in
  place with full native-Linux parity and renamed to **`deploy_brain.py`** — one cross-platform
  deployer (Windows/WSL2 + native Linux rootless-docker), Windows path proven byte-for-byte untouched.
  Sections 1–7 landed; Section 8 was a **supervised live teardown + from-scratch redeploy of dev_brain**
  that PASSED end-to-end (VERIFY PASSED, `brain_doctor diagnose` = HEALTHY) and, being first-live,
  surfaced **8 real defects the compile+stubbed-harness checks structurally could not catch**
  (BUG-001-1…8) — all FIXED, live-validated, and pushed. Neuron bring-up on Linux (DEBT-001-1b) and the
  real-client-IP requirement (DEBT-001-2) were also implemented and live-validated, so the final
  dev_brain runs the base RAG stack **and** its neuron bundle, with the config-exposure seam scoped to
  root + the owning brain and rootless networking that provably preserves the client source IP.
- **Dropped/deferred:** `DEBT-001-4` (throwaway build-user isolation) — **CLOSED won't-do**: the
  real-account build already yields a correct, account-independent engine artifact; the isolation is
  optional purity Linux doesn't need. `DEBT-001-5` (fail2ban `ignoreip` hard-codes the slirp4netns
  `10.0.2.0/24` range vs pasta) — **DEFERRED** with destination: revisit at the first server-posture
  Linux brain (LOW; inert under pasta/personal). Nothing else outstanding; every BUG FIXED and every
  DEBT closed or deferred-with-destination.
- **Final state:** `origin/main` — the deployer work through the debt sweep and this close. Key commits:
  `3d6b505` (DEBT-001-3b + driver deletion), `8dcf322`/`f6ba4a3`/`fd0bb5a`/`f03448d`/`8c2e8c6`/`d5a5769`
  (BUG-001-2…7), `ad3026c` (BUG-001-8 seam hardening), `ee04b8c` (DEBT-001-1b neuron bring-up),
  `a9a0b54` (DEBT-001-2 real-IP assertion + DEBT-001-4/5), plus this close.
- **Successors:** none scaffolded. `DEBT-001-5` is the only carried thread; pick it up ad hoc when a
  server-posture Linux brain is first deployed (no dependent project waits on it).
