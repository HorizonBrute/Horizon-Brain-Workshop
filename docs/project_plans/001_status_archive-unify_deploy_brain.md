---
type: project_plan
title: "Project 001 — Unify the brain deployer (Status Archive)"
description: Archive of completed/verified work-item blocks retired out of the live status doc.
tags: [project-plan, status, archive, deployer]
timestamp: 2026-07-21
status: closed
---

# Project 001 — Status Archive

Archived blocks below. See the live status doc's closeout `NOTE 001-11` for the project outcome.

<!-- Archived blocks go below, newest first. -->

## Archived 2026-07-24 — Project close (all Sections terminal, all decisions settled)

### Section 1 — Platform switch inside the trunk
**Status:** VERIFIED (live-validated at Section 8, 2026-07-23) · Platform seam foundation (`_IS_WINDOWS`/`_IS_LINUX`, `require_supported_os()` incl. honest macOS refusal, `require_admin()`→Linux `os.geteuid()==0`) + centralized identity-switch helper `run_as_brain_argv(path, brain, cmd, *, wsl, root)` (Windows argv byte-for-byte; Linux `sudo -u <brain> -H bash -lc`; `root=True` refused on Linux). All pure "run-as-brain" identity sites converted; `_deliver_data_seams` + `user_exists` Linux branches landed.

### Section 2 — Fold Linux path into trunk `build_engine`
**Status:** VERIFIED (live-validated at Section 8, 2026-07-23) · `build_engine()` dispatches to `_build_engine_linux` on Linux: ensure rootless-docker runtime → pull images → seed ollama models (net-new) → build neuron images → bake cert (no-arg gen-cert) → snapshot to `system/linux_engine/`. Windows `wsl --export` path untouched.

### Section 3 — Linux engine artifact
**Status:** VERIFIED (live-validated at Section 8, 2026-07-23) · Layout (NOTE 001-7): `system/linux_engine/{images.tar, ollama_models.tar, cert/{cert.pem,cert.key}}` + `linux_engine_dir()`. Produce in `_build_engine_linux`; consume (`docker load` + volume restore + cert place) in Section 4's deploy stages.

### Section 4 — Fold Linux branches into trunk `cmd_deploy`
**Status:** VERIFIED (Section 8) · `cmd_deploy/teardown/verify/status` dispatch to `_*_linux`. Full Linux deploy (`_preflight/_create_brain/_provision_runtime/_seam/_gateway/_residency/_verify` + `_ensure_engine`/`_deploy_engine` = `docker load` + volume restore → `compose --pull never`). Faithful port of the fixed `linux_deploy_brain.py` (NOTE 001-8).

### Section 5 — CLI parity on the trunk
**Status:** VERIFIED · Windows argparse was already a superset; added `teardown --port` (Linux ufw close).

### Section 6 — gen-cert hardening (BUG-001-1)
**Status:** VERIFIED (e2e at Section 8) · Correct cert contract in both Linux paths: build bakes no-arg gen-cert (personal); deploy gens with server-posture typed-SAN-all-global-IPv4 + hard rc-check. Posture word never reaches gen-cert.

### Section 7 — Migrate, retire, document
**Status:** VERIFIED (2026-07-23) · `git mv windows_deploy_brain.py → deploy_brain.py`; doc sweep; `brain_doctor.py` both backends repointed to `deploy_brain` (LinuxBackend rewire = DEBT-001-3b, NOTE 001-9); `linux_deploy_brain.py` deleted.

### Section 8 — Validation: rebuild dev_brain via unified path
**Status:** VERIFIED (PASSED 2026-07-23, supervised; extended through 2026-07-24) · Live `teardown --purge` + `deploy --from-scratch` of dev_brain → all stages VERIFY PASSED (mode C: no-token 403 / reader 200 / reset 403); rewired `brain_doctor diagnose` = HEALTHY. First-live surfaced + fixed **8 defects** (BUG-001-1…8). Neuron bring-up later added (DEBT-001-1b) so the final validated brain runs base stack + neurons; the real-client-IP assertion (DEBT-001-2) and seam hardening (BUG-001-8) also landed + live-validated. See NOTE 001-10 and the closeout NOTE 001-11.

---

## Archived decision log (NOTE 001-1 … 001-10)

## NOTE 001-1 | 2026-07-21 | Linux engine artifact = docker save + config bundle (CONFIRMED)
- Status: RESOLVED (user-confirmed 2026-07-21)
- Decision: `docker save` the pinned image list + a rendered config/cert bundle + an ollama-volume tar as the Linux engine artifact (portable analog of baking images into a rootfs tar; avoids rootless data-root UID/overlay fragility).

## NOTE 001-2 | 2026-07-21 | gen-cert hardening can land first
- Status: RESOLVED (2026-07-23) — realized: BUG-001-1 FIXED, cert contract correct in both Linux paths, e2e-proven at Section 8.

## NOTE 001-3 | 2026-07-21 | dev_brain stays down by design until the unified path exists
- Status: RESOLVED (2026-07-23) — condition over: Section 8 rebuilt dev_brain through `deploy_brain.py`; now UP + HEALTHY.

## NOTE 001-4 | 2026-07-21 | PIVOT — extend the Windows trunk, do not build a new file (CONFIRMED)
- Status: RESOLVED (user-confirmed 2026-07-21)
- Decision: base everything on `windows_deploy_brain.py`, branch inline only at OS-forced touchpoints, rename to `deploy_brain.py` at Section 7, discard the rejected clean-room file, retire `linux_deploy_brain.py`.

## NOTE 001-5 | 2026-07-21 | Centralize OS-forced concepts behind helpers, not scattered inline `if`s
- Status: RESOLVED — realized each OS-forced concept behind one internally-branching helper (e.g. `run_as_brain_argv`); Windows path stays the untouched `else`; Windows-only subsystems get a single `if _IS_LINUX: return`/skip guard.

## NOTE 001-6 | 2026-07-22 | Linux build identity = the real brain account (v1); throwaway build-user is debt
- Status: RESOLVED — v1 builds the Linux engine as the real brain account (reuses provision's rootless setup); throwaway build-user isolation tracked as DEBT-001-4 (later CLOSED won't-do).

## NOTE 001-7 | 2026-07-22 | Linux engine artifact layout = system/linux_engine/{images.tar, ollama_models.tar, cert/}
- Status: RESOLVED — `linux_engine_dir(brain_dir)` holds `images.tar` (docker save of runtime + neuron images), `ollama_models.tar` (volume tar), `cert/{cert.pem,cert.key}`. Build vs deploy split defined.

## NOTE 001-8 | 2026-07-23 | Rogue session hand-patched linux_deploy_brain.py (against instructions)
- Status: RESOLVED (user-confirmed 2026-07-23) — three rogue commits to the retired driver (cert SAN, chroma port, server SAN) were unwanted but correct; left in place (superseded when `linux_deploy_brain.py` was deleted at Section 7); their logic folded into the trunk's Linux path.

## NOTE 001-9 | 2026-07-23 | DEBT-001-3b done — brain_doctor LinuxBackend rewired, old driver deleted
- Status: DONE — LinuxBackend → `import deploy_brain as ldb`; renamed primitives mapped (`brain_sh`→`_brain_sh`, `_docker_ready`→`_linux_docker_ready`, `require_root`→`require_admin`); `linux_deploy_brain.py` `git rm`'d; smoke-tested.

## NOTE 001-10 | 2026-07-23 | Section 8 PASSED — supervised dev_brain teardown+from-scratch redeploy
- Status: DONE — all deploy stages → VERIFY PASSED; `brain_doctor` = HEALTHY. First live contact surfaced 7 defects (BUG-001-2…7 at the time), each fixed + pushed; BUG-001-8 + DEBT-001-1b/2 followed. (Full narrative retained in git history and the action log.)
