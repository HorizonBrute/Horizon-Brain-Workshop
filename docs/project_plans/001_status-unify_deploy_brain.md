---
type: project_plan
title: "Project 001 — Unify the brain deployer (Status)"
description: Live per-item status for Project 001, plus serialized objective notes and mini-decisions.
tags: [project-plan, status, deployer]
timestamp: 2026-07-21
status: draft
---

# Project 001 — Status

Plan detail: `001_detail-unify_deploy_brain.md`.
Orientation (read this instead of a handoff): `001_current_orientation-unify_deploy_brain.md`.

**Status legend:** `NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `DONE` · `VERIFIED`.
When a whole Section reaches `VERIFIED`, move its block into
`001_status_archive-unify_deploy_brain.md` and leave a one-line stub.

---

## Section 1 — Platform backend interface
**Status:** NOT STARTED

## Section 2 — Shared build-engine
**Status:** NOT STARTED · **Depends:** 1, 3

## Section 3 — Linux engine artifact (DESIGN-OPEN)
**Status:** BLOCKED · **Gate:** user confirmation of the `docker save` + config-bundle recommendation (NOTE 001-1)

## Section 4 — Shared deploy
**Status:** NOT STARTED · **Depends:** 1, 2

## Section 5 — Unified CLI + entry point
**Status:** NOT STARTED · **Depends:** 4

## Section 6 — gen-cert hardening (BUG-001-1)
**Status:** NOT STARTED
_Note: portable, low-risk; can land independently as the first product change since it is the bug's origin._

## Section 7 — Migrate, retire, document
**Status:** NOT STARTED · **Depends:** 5

## Section 8 — Validation: rebuild dev_brain via unified path
**Status:** NOT STARTED · **Depends:** 4, 6

---

# Objective Notes & Mini-Decisions (serialized)

Append-only, newest at the bottom. One `NOTE 001-K` per decision/update. Grep-able: `grep "NOTE 001-"`.

## NOTE 001-1 | 2026-07-21 | Linux engine artifact = docker save + config bundle (recommended, pending confirm)
- Status: OPEN
- ADR: none (self-contained; repo keeps no ADRs)
- Sections: 3, 2
- Context: Windows exports a WSL rootfs via `wsl --export`; Linux has no distro to export. The user
  chose "build-an-engine on both", so provisioning live (candidate c) is ruled out.
- Decision/Update: RECOMMEND candidate (b): `docker save` the pinned image list + a rendered
  config/cert bundle + an ollama-volume tar as the Linux engine artifact. Rationale: `docker save`/
  `load` is the portable analog of baking images into the rootfs tar; avoids the UID/overlay-store
  fragility of tarring the rootless data-root (candidate a). Awaiting user confirm before §2's Linux
  path is built. Section 3 stays BLOCKED until then.

## NOTE 001-2 | 2026-07-21 | gen-cert hardening can land first
- Status: OPEN
- ADR: none (self-contained)
- Sections: 6
- Context: BUG-001-1 (the cert false-green) is one small, portable change and is the origin of this
  whole project. It does not depend on the backend refactor.
- Decision/Update: Section 6 may land as the first product change (no-arg gen-cert + rc check),
  independent of the larger unification, so the shared cert contract is correct before §2 wires it in.

## NOTE 001-3 | 2026-07-21 | dev_brain stays down by design until the unified path exists
- Status: OPEN
- ADR: none (self-contained)
- Sections: 8
- Context: The live dev_brain gateway is crash-looping on the missing cert. Per the user, we are NOT
  hand-patching `linux_deploy_brain.py:576`; the fix arrives via the unified deployer.
- Decision/Update: dev_brain remains down until Section 8 rebuilds it through `deploy_brain.py`.
  Accepted tradeoff — recorded so a fresh agent does not "helpfully" patch the old line.
