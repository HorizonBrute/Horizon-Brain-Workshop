---
type: project_plan
title: "Project 001 — Unify the brain deployer (Bugs & Technical Debt)"
description: Running list of open bugs and technical debt for Project 001; every item cleared or deferred-with-reason before close.
tags: [project-plan, bugs, technical-debt, deployer]
timestamp: 2026-07-21
status: draft
---

# Project 001 — Bugs & Technical Debt

Every item must be **FIXED** or **explicitly DEFERRED with rationale and a destination** before the
project closes. Ids are stable: `BUG-001-K` / `DEBT-001-K`.

## BUG-001-1 — Linux gateway TLS cert never generated (false-green)
1. **Observed:** 2026-07-21. Live `dev_brain` gateway nginx crash-loops (`9+` restarts):
   `nginx: [emerg] cannot load certificate "/etc/nginx/certs/cert.pem": No such file or directory`;
   `~dev_brain/gateway/gateway_out/` empty. fail2ban stuck `Created` (shares nginx netns).
2. **Root cause:** `linux_deploy_brain.py:576` calls `gen-cert.sh <posture>` (e.g. `personal`), but
   `gen-cert.sh:26-30` treats positional args as extra SubjectAltName entries → malformed SAN
   (`...,personal`) → openssl exits nonzero → `set -euo pipefail` aborts before writing `cert.pem`.
   `provision_runtime:578` then prints "TLS cert generated" **without checking rc** (false-green).
   Windows calls the same script correctly with no arg (`stage4_brain.sh:99`).
3. **Severity/priority:** HIGH — takes the whole gateway down; must be cleared before close.
4. **Status:** FIXED in the trunk's Linux build (`windows_deploy_brain.py:_build_engine_linux`, Section
   2/3): the cert is baked by running `gen-cert.sh` with **no posture arg** (personal SAN), matching the
   Windows `stage4_brain.sh:99` call, and copied into the engine artifact `linux_engine/cert/`. The
   command sequence is asserted (compile + stubbed-run harness); end-to-end cert bake proven at Section 8.
   server-posture typed SANs land with the deploy-side cert placement (Section 4/6). Old
   `linux_deploy_brain.py:576` deliberately left unpatched (NOTE 001-3) — that driver is being retired.
   (Supersedes the earlier fix in the discarded clean-room `deploy_brain.py`, per NOTE 001-4.)

## DEBT-001-1 — Linux deploy is missing the ollama_models and neuron_bundles stages
1. **Decision/context:** `linux_deploy_brain.py cmd_deploy` (8 stages) has no `ollama_models` and no
   `neuron_bundles` stage; Windows has both (stages 8–9). A Linux brain never syncs its model roster
   or starts neuron bundles.
2. **Action needed:** the unified `deploy()` (Section 4) must include both stages for both OSes.
3. **Impact:** MEDIUM — a Linux brain's `/ask` 404s until models are pulled; neurons never run.
4. **Status:** OPEN → absorbed by Section 4.

## DEBT-001-2 — Several Windows engine-build steps have no Linux equivalent
1. **Decision/context:** unattended-upgrades policy (`stage5_root.sh`), maintenance tools + timers
   (`stage6_root.sh`/`stage6_brain.sh`), the slir4netns port-driver pin (`stage3_brain.sh`), and the
   full harden posture (`stage7_harden.sh`) are absent from the current Linux path.
2. **Action needed:** the shared build-engine (Section 2) runs these portable stage scripts on both
   OSes, closing the gap for free.
3. **Impact:** MEDIUM — Linux brains lack auto-updates, maintenance timers, and full hardening.
4. **Status:** OPEN → absorbed by Section 2.

## DEBT-001-3 — brain_doctor probes must track the unified deployer's outputs
1. **Decision/context:** `brain_doctor.py` already dispatches per-OS, but its residency/seam/stack
   probes assume the current per-driver artifact names. If unification changes any (unit name, seam
   path, engine layout), the doctor's checks drift.
2. **Action needed:** re-verify `brain_doctor diagnose` against a brain deployed by `deploy_brain.py`
   (Section 8) and adjust probes if needed.
3. **Impact:** LOW-MEDIUM — stale probes mis-report health, not a runtime break.
4. **Status:** OPEN → cleared at Section 8 validation.

## DEBT-001-4 — Linux engine build runs as the real brain account, not an isolated build user
1. **Decision/context:** Windows `build_engine` runs in a throwaway scratch distro, so the build never
   touches the real brain account and the engine tar is fully portable/account-independent. The v1 Linux
   build (`_build_engine_linux`, NOTE 001-6) runs as the **real brain account** against its rootless
   docker — simpler (reuses `provision_runtime`'s setup) but gives Linux `build-engine` an account
   side-effect Windows lacks, and (v1) REQUIRES the brain account to pre-exist.
2. **Action needed:** optionally add a throwaway build user (`brain-build-<brain>`: own subuid/subgid +
   linger + rootless daemon + teardown) to match Windows' isolation, once Linux `create-brain` (Section
   4) exists to factor the account/rootless setup out.
3. **Impact:** LOW — a functional artifact is produced either way; this is isolation purity + parity.
4. **Status:** OPEN → revisit after Section 4 (Linux create-brain) lands.
