---
type: project_plan
title: "Project 001 — Unify the brain deployer (Plan Detail)"
description: Fold Linux parity INTO the working windows_deploy_brain.py, branching only at OS-forced steps, then rename that consolidated trunk to deploy_brain.py; retire linux_deploy_brain.py.
tags: [project-plan, deployer, cross-platform, build-engine]
timestamp: 2026-07-21
status: draft
---

# Project 001 — Unify the brain deployer

> **PIVOT (2026-07-21, NOTE 001-4).** This plan previously called for a clean-room `deploy_brain.py`
> with a `PlatformBackend` ABC re-implementing the deploy lifecycle. **That architecture is rejected.**
> The user's directive: take the **already-working `windows_deploy_brain.py`** as the trunk, fold
> **Linux parity into it** (branch inline only where a step is OS-forced), and **rename the consolidated
> file to `deploy_brain.py`** once done. The rejected foundation file (`deploy_brain.py`, Sections 1+6)
> is discarded; its one good idea — the no-false-green cert guard — is applied when folding Linux in.

## Headline
Take `windows_deploy_brain.py` (3247 ln, works end-to-end) as the trunk, fold `linux_deploy_brain.py`'s
Linux-specific realizations INTO it as inline branches at the OS-forced steps, then rename the trunk to
`deploy_brain.py` and retire `linux_deploy_brain.py`.

## Executive summary
`windows_deploy_brain.py` already runs the correct build→deploy→verify process end-to-end. The Linux
driver diverged and broke — the gateway TLS cert was never generated, a **gratuitous transcription bug**,
not an OS constraint: `linux_deploy_brain.py:576` calls `gen-cert.sh personal`, but that script reads
positional args as SubjectAltName entries, so openssl rejects the SAN, `set -euo pipefail` aborts before
writing `cert.pem`, and the un-checked return code is reported as success (a false-green). The Windows
trunk runs the identical script correctly (no arg, at build time). So we **stop maintaining two flows**:
keep the Windows script as the single spine and add Linux behavior *inside it* — where a step is
OS-forced (identity switch, engine host + snapshot, seam mount, residency, firewall) we branch on the
platform right there; everything else stays exactly as the Windows script already has it. Linux gains a
build step it lacks today (Section 3 decides the Linux engine artifact). The Linux realizations to fold
in already exist and are traced in `linux_deploy_brain.py` — this is a **merge into the trunk**, not a
rewrite. **Load-bearing sequencing:** the cert is baked at BUILD time via a no-arg `gen-cert.sh` with an
rc check (already correct on the Windows path), so the false-green class cannot recur.

## Dependencies
1. **Upstream (this project depends on):** none.
2. **Downstream (projects that depend on this one):** `brain_doctor.py` (already cross-platform via a
   backend pattern) diagnoses/repairs whatever the deployer produces; its probes must track the
   unified deployer's residency/seam/stack outputs. No separate project yet — tracked as DEBT here.

## Relevant files
Confirmed by trace on branch `main` (2026-07-21) across two investigation agents. Real symbols; the
Linux-engine artifact is (DESIGN-OPEN).

- `windows_deploy_brain.py` — the WORKING template. `build_engine:1566`, `_obtain_base:1466`,
  `ensure_engine:1275`, `deploy_engine:1730`, `cmd_deploy:2504` (10 stages), deploy-time stages
  `seam:1859` / `gateway:2174` / `ollama_models:2254` / `neuron_bundles:2083` / `verify:2292`.
- `linux_deploy_brain.py` — the driver with the gap. `provision_runtime:496` (buggy `gen-cert` at
  `:576`, no rc check at `:578`), `gateway:742` (no cert gen at all), `residency:854`, `verify:889`,
  `cmd_deploy:949` (8 stages; NO build, NO ollama_models, NO neuron_bundles).
- `factory/source/system/brain_bin/provision/*.sh` — the 12 in-distro stage scripts Windows runs to
  build the engine: `provision_stage2.sh` (brain user + **docker-ce install** :61-64),
  `stage2b_root.sh`, `stage3_brain.sh` (rootless setup + slirp4netns pin), `stage4_brain.sh`
  (**lays stack + bakes cert, no-arg gen-cert :99**), `stage5_root.sh`, `stage6_root.sh`,
  `stage6_brain.sh`, `stage7_harden.sh` (posture + `/opt/brain_truths` mount unit), `cleanup_brain.sh`,
  `prefetch_images.sh`, `prefetch_models.sh`, `prefetch_neurons.sh`.
- `factory/source/system/brain_bin/gateway/gen-cert.sh` — args are treated as **extra SAN entries**
  (`:26-30`); correct call is zero-arg (personal SAN) or typed `DNS:… IP:…` for server. Root of the bug.
- `brain_doctor.py` — the backend-dispatch pattern to generalize (LinuxBackend / WindowsBackend).

## Relevant vocabulary / concepts
- **Engine** — the pre-provisioned, cert-and-image-complete runtime snapshot deployed into a brain.
  Windows: a WSL2 distro exported via `wsl --export` to `<brain>_engine.tar`. Linux: (DESIGN-OPEN, §3).
- **Seam** — the config-exposure read-only mount of the host `brain_etc` at `/opt/brain_truths`
  (Windows drvfs+ACL; Linux bind+POSIX).
- **Residency** — keep the stack up headless/at boot (Windows Task Scheduler keepalive; Linux
  `systemd --user` unit + `loginctl` linger).
- **Mode C / posture** — the sealed gateway posture verify asserts (no-token 403, reader 200, reset
  403); posture = `personal` (bind 127.0.0.1) | `server` (bind 0.0.0.0 + firewall).
- **Neuron** — an input/action bundle image (`<brain>-{input,action}_neurons`) fronted by the gateway.

---

## My Initial Brief
> Verbatim, as given by the user at project kickoff (2026-07-21). Not edited for grammar.

"because... rather than fix the linux deployer I would actually prefer to unify.. and not have any
platform-specific deployer.. just deploy_brain.py"

"Linux and windows, outside of WSL should be the same process -- the goal is eventually to move to
one.. and since Windows installer currently works.. one wonders why we can't just use that."

[Engine-model decision, selecting "Also unify Linux onto build-an-engine":] "Both OSes: build_engine
→ (cert baked at build); deploy: import/activate engine; gateway/verify shared. Linux gains a build
step it doesn't currently have."

"The windows orchestration should already do the gencert well.."

---

## Your Initial Understanding From That Brief
> My reading after tracing the current code across two investigation agents.

1. **The divergence is a bug, not an OS constraint.** Cert gen, token minting, `gateway_config`
   render, seam apply, and the verify gates are portable host-side Python/bash that Windows already
   runs correctly; Linux either mis-calls (`gen-cert.sh posture`) or omits them (no `ollama_models`,
   no `neuron_bundles`). Converging onto the Windows process is therefore subtraction, not a merge.
2. **Only five things are genuinely OS-forced** and get an inline branch in the trunk: engine host +
   snapshot (WSL VM + `wsl --export/--import` vs a native mechanism), identity switch
   (`run_as_brain --wsl` vs `sudo -u`), seam mount (drvfs+ACL vs bind+POSIX), residency (schtasks vs
   systemd+linger), firewall (Defender vs ufw). Everything else stays the Windows trunk's shared code,
   untouched.
3. **The one real open design question is the Linux engine artifact** (§3): Linux has no distro to
   `wsl --export`. This is the only place the "build-an-engine on both" decision needs a concrete new
   mechanism rather than a port.
4. **Never re-introduce a false-green.** The bug survived because a failed cert step returned nonzero
   and nobody checked. Every side-effecting sub-step in the unified path must gate on rc (invariant).

---

## Plan

Each `### Section` is a unit of work; status tracked in `001_status-unify_deploy_brain.md`.

### Section 1 — Platform switch inside the trunk (the OS-forced branch points)
- Work in `windows_deploy_brain.py` directly. Add a runtime platform detection and, at each OS-forced
  touchpoint, an inline branch (`if _IS_LINUX: … else: <existing Windows code unchanged>`). The
  OS-forced touchpoints are exactly: identity switch (`run_as_brain --wsl` vs `sudo -u <brain> -H`),
  engine host + snapshot (`wsl --export/--import` vs the §3 Linux artifact), seam mount (drvfs+icacls
  RX vs bind+POSIX RO), residency (schtasks keepalive vs `systemd --user` + linger), firewall
  (Defender vs ufw).
- Do **not** introduce a `PlatformBackend` ABC or a second file. The Windows script's existing
  functions ARE the shared spine; only these touchpoints branch. Keep the branch surface small and
  co-located with the step it guards so the Windows path stays byte-for-byte what works today.
- Context: this replaces the rejected clean-room-orchestrator design. Refuse unsupported OS with the
  same honest macOS message `brain_doctor` uses.

### Section 2 — Fold the Linux path into the trunk's `build_engine`
- The Windows `build_engine:1566` already runs the 12 `provision/*.sh` stage scripts in the throwaway
  `brain-build-<brain>` distro and bakes the cert (no-arg `gen-cert.sh` at `stage4_brain.sh:99`).
  Add a Linux branch that runs the same OS-portable stage scripts in the §3 Linux engine host and
  produces the §3 Linux engine artifact; everything else in `build_engine` stays shared.
- The stage scripts are already OS-portable bash/docker; only the host they run in and the snapshot
  mechanism are OS-forced (branch there, per §1).
- Context: Cert + images are BAKED here (same as Windows) so deploy is offline-capable. Linux gains a
  build step it lacks today.

### Section 3 — Linux engine artifact (DESIGN-OPEN — see NOTE 001-1)
- Decide what a Linux "engine" IS and how `engine_snapshot`/`engine_restore` realize it.
- Candidates (from the build-engine investigation): (a) tar the brain runtime dirs + rootless image
  store + ollama volume; (b) `docker save` the pinned images + a rendered-config/cert bundle + a
  volume tar; (c) provision live, skip export. The user chose "build-an-engine", so (c) is out.
- **Recommendation: (b)** — `docker save`/`load` is the OS-portable analog of "images baked into the
  rootfs tar"; images are already a clean pinned list (`_runtime_image_refs`), the config/cert bundle
  reuses host-side tooling, and it avoids the UID/overlay-store fragility of tarring the rootless
  data-root (a). Confirm before building §2's Linux path.
- Context: this is the ONLY novel mechanism; everything else is a port. See NOTE 001-1.

### Section 4 — Fold Linux branches into the trunk's `cmd_deploy` stages
- The Windows `cmd_deploy:2504` already sequences the 10 deploy stages (ensure_engine → deploy_engine
  → seam:1859 → gateway:2174 → ollama_models:2254 → neuron_bundles:2083 → verify:2292). Add the
  Linux realization at each OS-forced stage only: `deploy_engine` (restore the §3 artifact vs
  `wsl --import`), `seam` (bind+POSIX RO at `/opt/brain_truths` via `opt-brain_truths.mount` vs
  drvfs+icacls), and the residency+firewall steps (systemd user unit + linger + ufw vs schtasks +
  Defender). Gateway/models/neurons/verify are host-side Python and stay shared.
- Context: this is the merge of `linux_deploy_brain.py`'s `provision_runtime`/`seam`/`residency`/
  `verify` realizations INTO the Windows stages. Tokens/rendered-config stay DEPLOY-time (host seam),
  never baked, or the residency seam-sync reverts them. Apply the §6 rc-checked cert contract here.

### Section 5 — CLI parity on the trunk's argparse
- Keep the Windows script's existing argparse surface as the base; ensure every flag `linux_deploy_brain.py`
  exposes is present (verbs `build-engine | deploy | teardown | verify | status`, `--brain`,
  `--posture`, `--port`, `--install-root`, `--skip-*`). Platform detected at runtime.
- Context: preserve every flag both drivers expose so no caller breaks. The Windows CLI is already the
  superset for most; reconcile any Linux-only flag names.

### Section 6 — gen-cert hardening (the bug that started this)
- Shared cert stage calls `gen-cert.sh` with NO posture arg (personal SAN); for `server` posture map
  to typed SAN entries (`DNS:<host> IP:<addr>`), never the bare word. **Check the rc — a cert failure
  is fatal, not a warning.**
- Context: closes BUG-001-1 permanently and enforces the no-false-green invariant at its origin.

### Section 7 — Rename the trunk, retire the Linux driver, document
- Once Linux parity is folded in and validated (§8), **rename** the consolidated
  `windows_deploy_brain.py` → `deploy_brain.py` (`git mv`). Delete `linux_deploy_brain.py`; leave a thin
  shim or deprecation error at both old names for one release. Retarget `brain_doctor.py` if any probe
  assumed a driver-specific artifact.
- Delete the rejected clean-room `deploy_brain.py` foundation BEFORE the rename so the target name is
  free (its only good idea, the cert rc-guard, is carried by §6). Update `README.md` / `docs/` and
  `aios/install/*` context pointers to name the one deployer.
- Context: the package installer and README currently name both `windows_deploy_brain.py` /
  `linux_deploy_brain.py`; keep them consistent (AIOS consistency-check discipline).

### Section 8 — Validation: rebuild dev_brain via the unified path on Linux
- `teardown` then `build-engine` + `deploy` `dev_brain` through `deploy_brain.py` on this live Linux
  host; assert `brain_doctor diagnose` returns HEALTHY (gateway cert present, nginx + fail2ban up,
  verify gates pass).
- Context: this is the end-to-end proof; it also finally clears the live dev_brain outage.

## Cross-cutting invariants (do not violate)
- **No false-greens.** Every side-effecting sub-step checks its return code; success is never printed
  unconditionally. (This bug's root cause.)
- **Only OS-forced steps branch.** Anything outside the five OS-forced touchpoints stays the Windows
  trunk's shared code — no parallel re-implementation, no ABC.
- **The Windows path stays what works today.** Every branch is `if _IS_LINUX: … else: <unchanged>`;
  the `else` is the existing Windows code, byte-for-byte, so consolidation never regresses Windows.
- **Idempotent + re-runnable.** Every stage may run twice without harm (both drivers already aim for
  this).
- **Posture parity.** Linux and Windows must reach the same mode-C verify posture from the same
  process.
