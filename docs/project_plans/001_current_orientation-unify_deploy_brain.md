---
type: project_plan
title: "Project 001 — Unify the brain deployer (Current Orientation)"
description: The read-instead-of-a-handoff cold-start orientation for Project 001.
tags: [project-plan, orientation, deployer]
timestamp: 2026-07-21
status: draft
---

# Project 001 — Current Orientation

> Read this instead of a handoff to resume Project 001 cold. Short by design.

## What this project is
Fold Linux parity INTO the already-working `windows_deploy_brain.py` (branch inline only at OS-forced
steps), then rename that consolidated trunk to `deploy_brain.py` and retire `linux_deploy_brain.py`.
One shared build→deploy→verify spine (the Windows script's), with an `if _IS_LINUX` branch only at the
five OS-forced touchpoints. Full detail: `001_detail-unify_deploy_brain.md`. **Read NOTE 001-4 first.**

## The one thing to understand first
The Windows deployer already runs the correct process end-to-end; the Linux one diverged and broke
(gateway TLS cert never generated — a false-green from a bad `gen-cert.sh` call). So this is a **merge
into the Windows trunk**, not a rewrite and not a new file. **PIVOT (NOTE 001-4):** the earlier
clean-room `deploy_brain.py` + `PlatformBackend` ABC is REJECTED and discarded — we edit
`windows_deploy_brain.py` in place. Only five things are genuinely OS-forced (engine host+snapshot,
identity switch, seam mount, residency, firewall); everything else stays the Windows trunk untouched.

## Where the project stands
**Sections 1–7 essentially DONE; the file is now `deploy_brain.py`** (renamed from `windows_deploy_brain.py`).
The Windows path is byte-for-byte untouched (asserted); Linux was folded in as top-level dispatches
(`build_engine`, `cmd_deploy`, `cmd_teardown`, `cmd_verify`, `cmd_status` → `_*_linux`) + a centralized
identity helper (`run_as_brain_argv`). Landed + pushed:
- **S1** platform seam + identity switch (`run_as_brain_argv`), `_deliver_data_seams`/`user_exists` Linux branches.
- **S2/3** `_build_engine_linux` — pull images, **seed ollama models** (net-new), build neurons, no-arg cert bake, snapshot to `system/linux_engine/{images.tar,ollama_models.tar,cert/}`.
- **S4/5/6** full Linux deploy (`_cmd_deploy_linux`: preflight/create/provision/seam/gateway/residency/verify) + engine restore (`docker load` + volume restore → `compose --pull never`); CLI parity; cert contract (server-SAN-all-global-IPv4) in both paths. Ported faithfully from the FIXED `linux_deploy_brain.py` (NOTE 001-8).
- **S7** rename done; `brain_doctor` Windows import repointed; doc sweep done.
Everything compiles and every Linux command sequence is asserted via stubbed-run harnesses.
**Remaining:** (1) **S8 live validation** — DEFERRED to a supervised run (dev_brain user-handled; do NOT
fire an unsupervised live deploy). (2) Delete `linux_deploy_brain.py` — blocked on rewiring
`brain_doctor`'s LinuxBackend to the trunk's primitives (DEBT-001-3b). (3) Neuron bring-up on Linux (DEBT-001-1b).
Recommended next: DEBT-001-3b (doctor LinuxBackend → deploy_brain) then `git rm linux_deploy_brain.py`;
then a supervised Section 8 on a scratch brain.

## What to read, in order
1. This file.
2. `001_status-unify_deploy_brain.md` — per-item status + `NOTE 001-K` decisions.
3. `001_detail-unify_deploy_brain.md` — the full plan, verbatim brief, traced code map.
4. `001_bugs_and_technical_debt-unify_deploy_brain.md` — BUG-001-1 (the cert false-green) + debt.

## Standing rules for keeping THIS project current (do these without being asked)
1. **Keep the status doc live** — update each item's status as work lands; add a `NOTE 001-K` for
   every decision (`grep "NOTE 001-"`).
2. **Archive verified sections** — move `VERIFIED` blocks into
   `001_status_archive-unify_deploy_brain.md`; leave a one-line stub.
3. **Keep this orientation current** — a couple of plain lines when the shape or next step changes.
4. **Log every meaningful action** — append ONE line to `001_action_log-unify_deploy_brain.md`.

The full lifecycle rules live in `PROJECT_PLAN_GUIDE.md` (same folder).

## Related tracking
- Bugs & tech debt: `001_bugs_and_technical_debt-unify_deploy_brain.md`.
- Sibling tool already cross-platform: `brain_doctor.py` (diagnose/repair) — consumes whatever this
  deployer produces; keep its probes in sync (DEBT-001-1).
