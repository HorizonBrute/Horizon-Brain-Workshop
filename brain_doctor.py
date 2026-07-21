#!/usr/bin/env python3
"""
brain_doctor.py — diagnose and repair a deployed brain's runtime (native Linux)
===============================================================================

The health-and-repair sibling of `linux_deploy_brain.py`. Where the deploy driver
*stands a brain up* (and `teardown` takes it down), the doctor answers the day-two
question: **"is this brain healthy, and if not, bring it back."**

It deliberately does NOT re-implement any of the deploy machinery. It imports
`linux_deploy_brain` as a library and reuses its primitives verbatim:

    identity switch   as_brain / brain_sh   -> sudo -u <brain> -H bash -lc …
    daemon probe      _docker_ready         -> docker info as the brain
    naming            stack_service / seam_mount_unit / MOUNT_POINT
    install-root      resolve_install_root / brain_paths
    config regen      system/brain_sbin/gateway_config.py (same call the gateway stage makes)

So the doctor is a thin *orchestration* over the exact same tools the deployer uses —
`sudo -u`, `systemctl --user`, `loginctl`, `docker compose`, `gateway_config`.

TWO VERBS
    diagnose   read-only. Probe every layer (account → linger → rootless daemon →
               compose config interpolation → stack unit → containers → seam →
               residency) and print a report. Exit 0 if healthy, 1 if any FAIL.

    repair     escalating, idempotent remediation using the tools above:
                 1. enable linger if off            (loginctl enable-linger)
                 2. bring the rootless daemon up     (systemctl --user enable --now docker)
                 3. systemctl --user daemon-reload
                 4. (--regen-config) re-render gateway config  (gateway_config.py)
                 5. (--restart-docker) restart the rootless daemon
                 6. bring the stack up via its residency unit  (systemctl --user
                    restart/enable --now <brain>-docker-stack), falling back to a
                    direct `docker compose up -d [--force-recreate]`
                 7. re-diagnose and report the end state.

    The single commonest failure this fixes: the stack unit is in a stale `failed`
    state (e.g. a first bring-up raced ahead of the rendered ~/docker/.env), the
    config on disk is now valid, and the unit simply needs a daemon-reload + restart.

USAGE
    sudo python3 brain_doctor.py diagnose --brain X [--install-root DIR] [--port N]
    sudo python3 brain_doctor.py repair   --brain X [--install-root DIR] [--port N]
                                          [--restart-docker] [--recreate] [--regen-config]
"""

import argparse
import os
import sys
from pathlib import Path

# The doctor is an orchestration over the deploy driver's primitives — import them
# rather than duplicate. The driver has no import-time side effects (its verbs live
# under `if __name__ == "__main__"`), so this is a clean library import.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import linux_deploy_brain as ldb  # noqa: E402

# Reused verbatim from the deploy driver.
banner   = ldb.banner
info     = ldb.info
run      = ldb.run
run_out  = ldb.run_out
brain_sh = ldb.brain_sh


# ---------------------------------------------------------------------------
# Report model — a check is (level, label, detail). Levels order by severity so
# the overall verdict is just the worst level seen.
# ---------------------------------------------------------------------------

_GLYPH = {"OK": "[OK]  ", "INFO": "[INFO]", "WARN": "[WARN]", "FAIL": "[FAIL]"}
_RANK  = {"OK": 0, "INFO": 0, "WARN": 1, "FAIL": 2}


class Report:
    def __init__(self):
        self.checks = []

    def add(self, level, label, detail=""):
        self.checks.append((level, label, detail))
        return level

    def worst(self):
        return max((_RANK[l] for l, _, _ in self.checks), default=0)

    def healthy(self):
        return self.worst() == 0

    def print(self):
        width = max((len(lbl) for _, lbl, _ in self.checks), default=0)
        for level, label, detail in self.checks:
            line = f"  {_GLYPH[level]} {label.ljust(width)}"
            if detail:
                line += f" : {detail}"
            print(line)


# ---------------------------------------------------------------------------
# Probes — each returns a small structured result the report and the repair
# flow both read. All go through the driver's `brain_sh` (sudo -u <brain>), so
# rootless-Docker env (DOCKER_HOST / XDG_RUNTIME_DIR) resolves from the login shell.
# ---------------------------------------------------------------------------

def _user_unit_state(brain, unit):
    """Return (is_active, is_enabled, raw) for a systemd --user unit as the brain."""
    _, active, _  = brain_sh(brain, f"systemctl --user is-active {unit} 2>/dev/null")
    _, enabled, _ = brain_sh(brain, f"systemctl --user is-enabled {unit} 2>/dev/null")
    return active.strip(), enabled.strip()


def _compose_config_ok(brain):
    """`docker compose config -q` from ~/docker (the exact interpolation the stack
    unit performs). Returns (ok, err_text). This is what catches a missing BRAIN_NAME
    or an un-rendered per-neuron token before the unit fails on it."""
    rc, out, err = brain_sh(brain, "cd ~/docker && docker compose config -q 2>&1")
    return rc == 0, (out + err).strip()


def _compose_ps(brain):
    """List active-profile services and their state. Returns a list of
    (service, state, status) tuples; empty means the stack is down."""
    rc, out, _ = brain_sh(
        brain, "cd ~/docker && docker compose ps -a --format '{{.Service}}|{{.State}}|{{.Status}}' 2>/dev/null")
    rows = []
    for line in (out or "").splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3 and parts[0]:
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def _gateway_heartbeat(brain, brain_dir, port):
    """Best-effort no-token heartbeat. mode-C posture answers 403 (gate closed) —
    that means the gateway is up and correctly sealed. Never fatal; purely a signal."""
    cert = "~/gateway/gateway_out/cert.pem"
    hb = (f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 5 --cacert {cert} "
          f"https://127.0.0.1:{port}/api/v2/heartbeat 2>/dev/null")
    rc, out, _ = brain_sh(brain, hb)
    return ldb._http_code(out)


# ---------------------------------------------------------------------------
# diagnose — read-only health report
# ---------------------------------------------------------------------------

def diagnose(args, quiet_banner=False):
    brain = args.brain
    _, brain_dir = ldb.brain_paths(args)
    rep = Report()

    if not quiet_banner:
        banner(f"Brain doctor — diagnose: {brain}")

    # 1. Account + folder — hard prerequisites; nothing else is meaningful without them.
    if not ldb.user_exists(brain):
        rep.add("FAIL", "account", f"OS user '{brain}' does not exist")
        rep.print()
        print(f"\n  verdict: UNHEALTHY — brain '{brain}' is not provisioned on this host.")
        return 1
    rep.add("OK", "account", f"OS user '{brain}' exists")

    if brain_dir.is_dir():
        rep.add("OK", "brain folder", str(brain_dir))
    else:
        rep.add("FAIL", "brain folder", f"{brain_dir} MISSING")

    # 2. Linger — without it the user manager (and the rootless daemon) won't survive a reboot.
    if ldb.linger_enabled(brain):
        rep.add("OK", "linger", "enabled (user services persist headless)")
    else:
        rep.add("WARN", "linger", "DISABLED — stack will not come up after reboot")

    # 3. Rootless Docker daemon — the engine everything else rides on.
    daemon_up = ldb._docker_ready(brain)
    d_active, d_enabled = _user_unit_state(brain, "docker")
    if daemon_up:
        rep.add("OK", "rootless docker", f"daemon answering (unit {d_active}/{d_enabled})")
    else:
        rep.add("FAIL", "rootless docker", f"daemon not answering (unit {d_active}/{d_enabled})")

    # 4. Compose config interpolation — the class of failure behind the classic
    #    'missing per-neuron token' / unset BRAIN_NAME stack crash.
    if daemon_up:
        cfg_ok, cfg_err = _compose_config_ok(brain)
        if cfg_ok:
            rep.add("OK", "compose config", "interpolates cleanly")
        else:
            first = cfg_err.splitlines()[0] if cfg_err else "unknown error"
            rep.add("FAIL", "compose config", first)
    else:
        rep.add("INFO", "compose config", "skipped (daemon down)")

    # 5. Residency stack unit — the systemd --user unit that runs `docker compose up -d`.
    stack = f"{ldb.stack_service(brain)}.service"
    s_active, s_enabled = _user_unit_state(brain, stack)
    if s_active == "active":
        rep.add("OK", "stack unit", f"{stack} active/{s_enabled}")
    elif s_active == "failed":
        rep.add("FAIL", "stack unit", f"{stack} FAILED/{s_enabled}")
    else:
        rep.add("WARN", "stack unit", f"{stack} {s_active or 'absent'}/{s_enabled}")
    if s_enabled != "enabled":
        rep.add("WARN", "residency", f"{stack} not enabled — no boot autostart")

    # 6. Containers — the ground truth: are the services actually up?
    if daemon_up:
        rows = _compose_ps(brain)
        if not rows:
            rep.add("FAIL", "containers", "none running (stack is down)")
        else:
            running = [s for s, st, _ in rows if st == "running"]
            down    = [(s, st) for s, st, _ in rows if st != "running"]
            if not down:
                rep.add("OK", "containers", f"{len(running)}/{len(rows)} running: {', '.join(running)}")
            else:
                rep.add("WARN", "containers",
                        f"{len(running)}/{len(rows)} running; down: "
                        + ", ".join(f"{s}({st})" for s, st in down))
    else:
        rep.add("INFO", "containers", "skipped (daemon down)")

    # 7. Config-exposure seam (read-only bind mount).
    rc, out, _ = run_out(["findmnt", "-no", "OPTIONS", ldb.MOUNT_POINT])
    if out.strip():
        rep.add("OK", "seam mount", f"{ldb.MOUNT_POINT} ({out.strip()})")
    else:
        rep.add("WARN", "seam mount", f"{ldb.MOUNT_POINT} not mounted")

    # 8. Gateway heartbeat (best-effort, informational).
    if daemon_up and getattr(args, "port", None):
        code = _gateway_heartbeat(brain, brain_dir, args.port)
        if code == "403":
            rep.add("OK", "gateway", f":{args.port} heartbeat 403 (mode C — up + sealed)")
        elif code == "200":
            rep.add("WARN", "gateway", f":{args.port} heartbeat 200 (up but read-open, not mode C)")
        elif code:
            rep.add("WARN", "gateway", f":{args.port} heartbeat {code}")
        else:
            rep.add("INFO", "gateway", f":{args.port} no response (stack likely down)")

    rep.print()
    verdict = "HEALTHY" if rep.healthy() else "UNHEALTHY"
    print(f"\n  verdict: {verdict}")
    return 0 if rep.healthy() else 1


# ---------------------------------------------------------------------------
# repair — escalating remediation, all through existing tooling
# ---------------------------------------------------------------------------

def repair(args):
    brain = args.brain
    _, brain_dir = ldb.brain_paths(args)
    ldb.require_root()  # loginctl / sudo -u need root; mirror the deploy driver.

    if not ldb.user_exists(brain):
        ldb.die(f"cannot repair: OS user '{brain}' does not exist (deploy it first).")

    banner(f"Brain doctor — repair: {brain}")

    # 1. Linger — the foundation for a headless user manager.
    if not ldb.linger_enabled(brain):
        info("linger off — enabling (loginctl enable-linger)")
        run(["loginctl", "enable-linger", brain])
        ldb.ok("linger enabled")
    else:
        ldb.ok("linger already enabled")

    # 2. Rootless Docker daemon — enable + start the user unit if it isn't answering.
    if ldb._docker_ready(brain):
        ldb.ok("rootless docker already up")
    else:
        info("rootless docker not answering — systemctl --user enable --now docker")
        brain_sh(brain, "systemctl --user enable --now docker")
        if not ldb._docker_ready(brain):
            ldb.die("rootless docker still not answering after enable --now.\n"
                    "    Inspect as the brain: systemctl --user status docker\n"
                    "    (common causes: unprivileged userns disabled, /run/user/<uid> absent).")
        ldb.ok("rootless docker up")

    # 3. Reload user units so any edited/regenerated unit file is picked up.
    brain_sh(brain, "systemctl --user daemon-reload")
    ldb.ok("systemd --user daemon-reload")

    # 4. Optional: restart the rootless daemon itself (a deeper reset).
    if args.restart_docker:
        info("--restart-docker — restarting the rootless daemon")
        brain_sh(brain, "systemctl --user restart docker")
        if not ldb._docker_ready(brain):
            ldb.die("rootless docker did not come back after restart — see systemctl --user status docker.")
        ldb.ok("rootless docker restarted")

    # 5. Config health. Regenerate only if asked OR if config is currently broken and we can.
    cfg_ok, cfg_err = _compose_config_ok(brain)
    if not cfg_ok:
        ldb.warn("compose config does NOT interpolate:")
        info((cfg_err.splitlines() or ["unknown"])[0])
    if args.regen_config or (not cfg_ok):
        _regen_gateway_config(brain, brain_dir)
        cfg_ok, cfg_err = _compose_config_ok(brain)
        if cfg_ok:
            ldb.ok("compose config interpolates after regen")
        else:
            ldb.warn("compose config STILL broken after regen — manual attention needed:")
            info((cfg_err.splitlines() or ["unknown"])[0])
    elif cfg_ok:
        ldb.ok("compose config interpolates")

    # 6. Bring the stack up — prefer the residency unit (the same path boot uses), so a
    #    successful repair leaves the brain in its normal steady state, not a hand-run stack.
    stack = f"{ldb.stack_service(brain)}.service"
    _, enabled = _user_unit_state(brain, stack)
    up_cmd = "cd ~/docker && docker compose up -d" + (" --force-recreate" if args.recreate else "")
    if enabled == "enabled" and not args.recreate:
        info(f"restarting residency unit ({stack})")
        rc, out, e = brain_sh(brain, f"systemctl --user restart {stack}")
        if rc != 0:
            ldb.warn(f"unit restart returned {rc}; falling back to a direct compose up.\n{out}{e}")
            rc, out, e = brain_sh(brain, up_cmd)
    else:
        # Not enabled (or an explicit recreate): enable+start it, or run compose directly.
        if enabled != "enabled":
            info(f"stack unit not enabled — enabling + starting ({stack})")
            rc, out, e = brain_sh(brain, f"systemctl --user enable --now {stack}")
            if rc != 0:
                ldb.warn(f"enable --now returned {rc}; falling back to compose up.\n{out}{e}")
                rc, out, e = brain_sh(brain, up_cmd)
        else:
            info(f"bringing stack up ({'force-recreate' if args.recreate else 'up -d'})")
            rc, out, e = brain_sh(brain, up_cmd)
    if rc != 0:
        ldb.die(f"stack bring-up FAILED (rc={rc}).\n{out}{e}")
    ldb.ok("stack bring-up issued")

    # 7. Re-diagnose and report the end state.
    print()
    banner(f"Post-repair state: {brain}")
    code = diagnose(args, quiet_banner=True)
    if code == 0:
        ldb.ok("REPAIR COMPLETE — brain is healthy")
    else:
        ldb.warn("repair ran but the brain is not fully healthy — see the report above.")
    return code


def _regen_gateway_config(brain, brain_dir):
    """Re-render the gateway/token/nginx config from the seeded knobs, using the brain's
    OWN system/brain_sbin/gateway_config.py — the identical call the deploy gateway stage
    makes. This fixes the 'un-rendered ~/docker/.env / missing per-neuron token' class."""
    gcfg = brain_dir / "system" / "brain_sbin" / "gateway_config.py"
    if not gcfg.is_file():
        ldb.warn(f"gateway_config.py not present at {gcfg}; cannot regenerate config.")
        return
    info("regenerating gateway config (gateway_config.py --brain-dir …)")
    rc, out, e = run_out([sys.executable, str(gcfg), "--brain-dir", str(brain_dir)])
    (ldb.ok if rc == 0 else ldb.warn)(
        f"gateway_config generate {'done' if rc == 0 else f'rc={rc}'}"
        + (f"\n{out}{e}".rstrip() if rc != 0 else ""))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    ap = argparse.ArgumentParser(
        description="Diagnose and repair a deployed brain's runtime (native Linux).",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    dg = sub.add_parser("diagnose", help="read-only health report (exit 0 healthy, 1 unhealthy)")
    dg.add_argument("--brain", required=True)
    dg.add_argument("--install-root", default=None,
                    help="dir containing brains/<brain>/ (default: $AIOS_INSTALL_ROOT / $HORIZON_ROOT)")
    dg.add_argument("--port", type=int, default=8443, help="gateway port for the heartbeat probe")
    dg.set_defaults(func=lambda a: sys.exit(diagnose(a)))

    rp = sub.add_parser("repair", help="bring an unhealthy brain back using existing tooling")
    rp.add_argument("--brain", required=True)
    rp.add_argument("--install-root", default=None)
    rp.add_argument("--port", type=int, default=8443)
    rp.add_argument("--restart-docker", action="store_true",
                    help="restart the rootless docker daemon before bringing the stack up")
    rp.add_argument("--recreate", action="store_true",
                    help="docker compose up -d --force-recreate (recreate all containers)")
    rp.add_argument("--regen-config", action="store_true",
                    help="re-render gateway/token config (gateway_config.py) before bring-up")
    rp.set_defaults(func=lambda a: sys.exit(repair(a)))

    return ap.parse_args()


def main():
    args = parse_args()
    if not sys.platform.startswith("linux"):
        ldb.die("brain_doctor.py targets native Linux (systemd + rootless Docker), like "
                "linux_deploy_brain.py. On Windows use the Windows deploy path.")
    args.brain and ldb.validate_brain_name(args.brain)
    args.func(args)


if __name__ == "__main__":
    main()
