#!/usr/bin/env python3
"""
brain_doctor.py — diagnose and repair a deployed brain's runtime (cross-platform)
=================================================================================

The health-and-repair sibling of the deploy drivers. Where a deploy driver *stands a
brain up* (and `teardown` takes it down), the doctor answers the day-two question:
**"is this brain healthy, and if not, bring it back."**

It is OS-aware and dispatches to a platform backend, each of which reuses that
platform's deploy driver as a library rather than re-implementing any deploy
machinery:

    Linux    -> deploy_brain.py   (systemd --user + rootless Docker)
                reuses _brain_sh (sudo -u), _linux_docker_ready, stack_service,
                seam naming, resolve_install_root, gateway_config.py
    Windows  -> deploy_brain.py  (WSL2 per-user distro + Task Scheduler)
                reuses distro_exists/distro_imported_as_brain, residency_task*,
                brain_paths, and the staged run_as_brain.py (--wsl) to exec in-distro
    macOS    -> not yet a runtime target (deploy is objective 009); the doctor says so
                honestly instead of pretending to probe something that was never built.

WINDOWS ↔ LINUX MAPPING (why the checks differ per OS, mirroring the deploy drivers)
    ┌────────────────┬──────────────────────────────┬──────────────────────────────┐
    │ concern        │ Linux                        │ Windows                       │
    ├────────────────┼──────────────────────────────┼──────────────────────────────┤
    │ engine         │ rootless dockerd (user unit) │ WSL2 distro brain-<brain>     │
    │ identity switch│ sudo -u <brain> -H (brain_sh)│ run_as_brain.py --wsl -- …    │
    │ residency      │ systemd --user stack unit     │ schtasks keepalive task       │
    │ bring stack up │ systemctl --user restart /    │ (task /run holds distro) +    │
    │                │ docker compose up -d          │ in-distro docker compose up -d│
    │ seam           │ bind mount /opt/brain_truths  │ drvfs mount inside the distro │
    └────────────────┴──────────────────────────────┴──────────────────────────────┘

TWO VERBS (identical surface on every OS)
    diagnose   read-only. Probe every layer and print a report. Exit 0 healthy, 1 not.
    repair     escalating, idempotent remediation using existing platform tooling only.

STATUS
    The Linux backend is exercised live. The Windows backend is static-validated only
    (py_compile) and mirrors deploy_brain.py's own primitives — treat it as
    first-live until run on a real WSL2 host, exactly as the Linux path once was.

USAGE
    python3 brain_doctor.py diagnose --brain X [--install-root DIR] [--port N]
    python3 brain_doctor.py repair   --brain X [--install-root DIR] [--port N]
                                     [--restart-docker] [--recreate] [--regen-config]
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Same brain-name grammar the deploy drivers enforce — kept local so OS dispatch does
# not import a platform driver just to validate an argument.
BRAIN_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,19}$")


# ---------------------------------------------------------------------------
# Output helpers (same vocabulary as both deploy drivers; local so the Linux and
# Windows backends print identically and dispatch pulls in neither driver early).
# ---------------------------------------------------------------------------

def banner(text):
    line = "=" * (len(text) + 6)
    print(f"\n{line}\n=== {text} ===\n{line}")

def info(m): print(f"  {m}")
def ok(m):   print(f"  [OK]   {m}")
def warn(m): print(f"  [WARN] {m}")
def err(m):  print(f"  [ERROR] {m}", file=sys.stderr)

def die(m, code=1):
    err(m)
    sys.exit(code)

def run(cmd, check=True):
    return subprocess.run(cmd, check=check, text=True)

def run_out(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, (p.stdout or ""), (p.stderr or "")

def _http_code(out):
    toks = [t for t in (out or "").split() if t.isdigit()]
    return toks[-1] if toks else ""

def validate_brain_name(name):
    if not BRAIN_NAME_RE.match(name):
        die(f'invalid brain name "{name}" — must match ^[a-z][a-z0-9_]{{1,19}}$ '
            "(lowercase start, then 1-19 lowercase letters/digits/underscores).")


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


# ===========================================================================
# Linux backend — systemd --user + rootless Docker, via deploy_brain.py
# ===========================================================================

class LinuxBackend:
    label = "systemd --user + rootless Docker"

    def __init__(self):
        # Lazy import: only the platform we run on loads its (large) driver.
        import deploy_brain as ldb  # noqa: E402
        self.ldb = ldb

    # -- probes (all via sudo -u <brain> so rootless-Docker env resolves) ----

    def _unit_state(self, brain, unit):
        _, active, _  = self.ldb._brain_sh(brain, f"systemctl --user is-active {unit} 2>/dev/null")
        _, enabled, _ = self.ldb._brain_sh(brain, f"systemctl --user is-enabled {unit} 2>/dev/null")
        return active.strip(), enabled.strip()

    def _compose_config_ok(self, brain):
        rc, out, e = self.ldb._brain_sh(brain, "cd ~/docker && docker compose config -q 2>&1")
        return rc == 0, (out + e).strip()

    def _compose_ps(self, brain):
        rc, out, _ = self.ldb._brain_sh(
            brain, "cd ~/docker && docker compose ps -a "
                   "--format '{{.Service}}|{{.State}}|{{.Status}}' 2>/dev/null")
        rows = []
        for line in (out or "").splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3 and parts[0]:
                rows.append((parts[0], parts[1], parts[2]))
        return rows

    def _heartbeat(self, brain, port):
        hb = (f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 5 "
              f"--cacert ~/gateway/gateway_out/cert.pem "
              f"https://127.0.0.1:{port}/api/v2/heartbeat 2>/dev/null")
        _, out, _ = self.ldb._brain_sh(brain, hb)
        return _http_code(out)

    # -- diagnose -----------------------------------------------------------

    def diagnose(self, args):
        ldb = self.ldb
        brain = args.brain
        _, brain_dir = ldb.brain_paths(args)
        rep = Report()

        if not ldb.user_exists(brain):
            rep.add("FAIL", "account", f"OS user '{brain}' does not exist")
            return rep
        rep.add("OK", "account", f"OS user '{brain}' exists")
        rep.add("OK" if brain_dir.is_dir() else "FAIL", "brain folder",
                str(brain_dir) + ("" if brain_dir.is_dir() else "  MISSING"))

        if ldb.linger_enabled(brain):
            rep.add("OK", "linger", "enabled (user services persist headless)")
        else:
            rep.add("WARN", "linger", "DISABLED — stack will not come up after reboot")

        daemon_up = ldb._linux_docker_ready(brain)
        d_active, d_enabled = self._unit_state(brain, "docker")
        rep.add("OK" if daemon_up else "FAIL", "rootless docker",
                f"daemon {'answering' if daemon_up else 'NOT answering'} (unit {d_active}/{d_enabled})")

        if daemon_up:
            cfg_ok, cfg_err = self._compose_config_ok(brain)
            if cfg_ok:
                rep.add("OK", "compose config", "interpolates cleanly")
            else:
                rep.add("FAIL", "compose config", (cfg_err.splitlines() or ["unknown error"])[0])
        else:
            rep.add("INFO", "compose config", "skipped (daemon down)")

        stack = f"{ldb.stack_service(brain)}.service"
        s_active, s_enabled = self._unit_state(brain, stack)
        if s_active == "active":
            rep.add("OK", "stack unit", f"{stack} active/{s_enabled}")
        elif s_active == "failed":
            rep.add("FAIL", "stack unit", f"{stack} FAILED/{s_enabled}")
        else:
            rep.add("WARN", "stack unit", f"{stack} {s_active or 'absent'}/{s_enabled}")
        if s_enabled != "enabled":
            rep.add("WARN", "residency", f"{stack} not enabled — no boot autostart")

        if daemon_up:
            rows = self._compose_ps(brain)
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

        rc, out, _ = run_out(["findmnt", "-no", "OPTIONS", ldb.MOUNT_POINT])
        if out.strip():
            rep.add("OK", "seam mount", f"{ldb.MOUNT_POINT} ({out.strip()})")
        else:
            rep.add("WARN", "seam mount", f"{ldb.MOUNT_POINT} not mounted")

        if daemon_up and getattr(args, "port", None):
            code = self._heartbeat(brain, args.port)
            self._add_heartbeat(rep, args.port, code)
        return rep

    @staticmethod
    def _add_heartbeat(rep, port, code):
        if code == "403":
            rep.add("OK", "gateway", f":{port} heartbeat 403 (up + sealed, mode C)")
        elif code == "200":
            rep.add("WARN", "gateway", f":{port} heartbeat 200 (up but read-open, not mode C)")
        elif code:
            rep.add("WARN", "gateway", f":{port} heartbeat {code}")
        else:
            rep.add("INFO", "gateway", f":{port} no response (stack likely down)")

    # -- repair -------------------------------------------------------------

    def repair(self, args):
        ldb = self.ldb
        brain = args.brain
        _, brain_dir = ldb.brain_paths(args)
        ldb.require_admin()
        if not ldb.user_exists(brain):
            die(f"cannot repair: OS user '{brain}' does not exist (deploy it first).")

        if not ldb.linger_enabled(brain):
            info("linger off — enabling (loginctl enable-linger)")
            run(["loginctl", "enable-linger", brain]); ok("linger enabled")
        else:
            ok("linger already enabled")

        if ldb._linux_docker_ready(brain):
            ok("rootless docker already up")
        else:
            info("rootless docker not answering — systemctl --user enable --now docker")
            ldb._brain_sh(brain, "systemctl --user enable --now docker")
            if not ldb._linux_docker_ready(brain):
                die("rootless docker still not answering — inspect: systemctl --user status docker\n"
                    "    (common: unprivileged userns disabled, /run/user/<uid> absent).")
            ok("rootless docker up")

        ldb._brain_sh(brain, "systemctl --user daemon-reload"); ok("systemd --user daemon-reload")

        if args.restart_docker:
            info("--restart-docker — restarting the rootless daemon")
            ldb._brain_sh(brain, "systemctl --user restart docker")
            if not ldb._linux_docker_ready(brain):
                die("rootless docker did not come back after restart.")
            ok("rootless docker restarted")

        cfg_ok, cfg_err = self._compose_config_ok(brain)
        if not cfg_ok:
            warn("compose config does NOT interpolate:"); info((cfg_err.splitlines() or ["unknown"])[0])
        if args.regen_config or not cfg_ok:
            self._regen_config(brain_dir)
            cfg_ok, cfg_err = self._compose_config_ok(brain)
            (ok if cfg_ok else warn)(
                "compose config interpolates after regen" if cfg_ok
                else "compose config STILL broken after regen — manual attention needed")
            if not cfg_ok:
                info((cfg_err.splitlines() or ["unknown"])[0])
        elif cfg_ok:
            ok("compose config interpolates")

        stack = f"{ldb.stack_service(brain)}.service"
        _, enabled = self._unit_state(brain, stack)
        up = "cd ~/docker && docker compose up -d" + (" --force-recreate" if args.recreate else "")
        if enabled == "enabled" and not args.recreate:
            info(f"restarting residency unit ({stack})")
            rc, out, e = ldb._brain_sh(brain, f"systemctl --user restart {stack}")
            if rc != 0:
                warn(f"unit restart rc={rc}; falling back to compose up.\n{out}{e}")
                rc, out, e = ldb._brain_sh(brain, up)
        elif enabled != "enabled":
            info(f"stack unit not enabled — enabling + starting ({stack})")
            rc, out, e = ldb._brain_sh(brain, f"systemctl --user enable --now {stack}")
            if rc != 0:
                warn(f"enable --now rc={rc}; falling back to compose up.\n{out}{e}")
                rc, out, e = ldb._brain_sh(brain, up)
        else:
            info(f"bringing stack up ({'force-recreate' if args.recreate else 'up -d'})")
            rc, out, e = ldb._brain_sh(brain, up)
        if rc != 0:
            die(f"stack bring-up FAILED (rc={rc}).\n{out}{e}")
        ok("stack bring-up issued")
        return 0

    def _compose_config_ok(self, brain):  # noqa: F811 (repair reuses the probe)
        rc, out, e = self.ldb._brain_sh(brain, "cd ~/docker && docker compose config -q 2>&1")
        return rc == 0, (out + e).strip()

    def _regen_config(self, brain_dir):
        gcfg = brain_dir / "system" / "brain_sbin" / "gateway_config.py"
        if not gcfg.is_file():
            warn(f"gateway_config.py not present at {gcfg}; cannot regenerate."); return
        info("regenerating gateway config (gateway_config.py --brain-dir …)")
        rc, out, e = run_out([sys.executable, str(gcfg), "--brain-dir", str(brain_dir)])
        (ok if rc == 0 else warn)(
            f"gateway_config generate {'done' if rc == 0 else f'rc={rc}'}"
            + (f"\n{out}{e}".rstrip() if rc != 0 else ""))


# ===========================================================================
# Windows backend — WSL2 per-user distro + Task Scheduler, via
# deploy_brain.py. STATIC-VALIDATED ONLY (see module STATUS note).
# ===========================================================================

class WindowsBackend:
    label = "WSL2 distro + Task Scheduler (STATIC-VALIDATED — first-live on a real host)"

    def __init__(self):
        import deploy_brain as wdb  # noqa: E402
        self.wdb = wdb

    def _wsl(self, brain, brain_dir, script):
        """Run a shell script inside the brain's WSL2 distro AS THE BRAIN, via the
        staged run_as_brain.py --wsl — the Windows analogue of Linux brain_sh."""
        rab = brain_dir / "system" / "brain_sbin" / "run_as_brain.py"
        if not rab.is_file():
            return 127, "", f"run_as_brain.py not staged at {rab}"
        return run_out([sys.executable, str(rab), "--brain", brain, "--wsl", "--", "bash", "-lc", script])

    def diagnose(self, args):
        wdb = self.wdb
        brain = args.brain
        _, brain_dir = wdb.brain_paths(args)
        rep = Report()

        if not wdb.user_exists(brain):
            rep.add("FAIL", "account", f"Windows user '{brain}' does not exist")
            return rep
        rep.add("OK", "account", f"Windows user '{brain}' exists")
        rep.add("OK" if brain_dir.is_dir() else "FAIL", "brain folder",
                str(brain_dir) + ("" if brain_dir.is_dir() else "  MISSING"))

        # Engine = the per-user WSL2 distro, probed IN THE BRAIN'S CONTEXT (an elevated
        # `wsl -l -q` would not see a per-user distro — false-negative). distro_imported_as_brain
        # runs run_as_brain -> `wsl -d brain-<brain> -- true`: rc 0 iff it exists AND boots.
        distro_up = wdb.distro_imported_as_brain(args)
        rep.add("OK" if distro_up else "FAIL", "wsl distro",
                f"brain-{brain} {'imported + boots' if distro_up else 'NOT launchable'}")

        if distro_up:
            rc, out, e = self._wsl(brain, brain_dir, "cd ~/docker && docker compose config -q 2>&1")
            if rc == 0:
                rep.add("OK", "compose config", "interpolates cleanly")
            else:
                rep.add("FAIL", "compose config", ((out + e).strip().splitlines() or ["unknown error"])[0])
        else:
            rep.add("INFO", "compose config", "skipped (distro down)")

        # Residency = the schtasks keepalive that holds the distro resident across idle/boot.
        exists, running, last = wdb.residency_task_running(brain)
        if not exists:
            rep.add("WARN", "residency task", f"{wdb.residency_task(brain)} absent — no boot/idle hold")
        elif running:
            rep.add("OK", "residency task", f"{wdb.residency_task(brain)} running (last={last})")
        else:
            rep.add("FAIL", "residency task",
                    f"{wdb.residency_task(brain)} exists but NOT running (last={last}) — distro will idle down")

        if distro_up:
            rc, out, _ = self._wsl(brain, brain_dir,
                                   "cd ~/docker && docker compose ps -a "
                                   "--format '{{.Service}}|{{.State}}|{{.Status}}' 2>/dev/null")
            rows = [tuple(p.split("|", 2)) for p in (out or "").splitlines()
                    if len(p.split("|", 2)) == 3 and p.split("|", 2)[0]]
            if not rows:
                rep.add("FAIL", "containers", "none running (stack is down)")
            else:
                running_c = [s for s, st, _ in rows if st == "running"]
                down = [(s, st) for s, st, _ in rows if st != "running"]
                rep.add("OK" if not down else "WARN", "containers",
                        f"{len(running_c)}/{len(rows)} running"
                        + ("" if not down else "; down: " + ", ".join(f"{s}({st})" for s, st in down)))
            # Seam is a drvfs mount inside the distro (parity with the Linux bind mount check).
            rc, out, _ = self._wsl(brain, brain_dir, f"findmnt -no OPTIONS {wdb.MOUNT_POINT} 2>/dev/null"
                                   if hasattr(wdb, "MOUNT_POINT") else "findmnt -no OPTIONS /opt/brain_truths 2>/dev/null")
            rep.add("OK" if out.strip() else "WARN", "seam mount",
                    (out.strip() or "not mounted inside the distro"))
        else:
            rep.add("INFO", "containers", "skipped (distro down)")

        if distro_up and getattr(args, "port", None):
            hb = (f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 5 "
                  f"--cacert ~/gateway/gateway_out/cert.pem "
                  f"https://127.0.0.1:{args.port}/api/v2/heartbeat 2>/dev/null")
            _, out, _ = self._wsl(brain, brain_dir, hb)
            LinuxBackend._add_heartbeat(rep, args.port, _http_code(out))
        return rep

    def repair(self, args):
        wdb = self.wdb
        brain = args.brain
        _, brain_dir = wdb.brain_paths(args)
        wdb.require_admin()
        if not wdb.user_exists(brain):
            die(f"cannot repair: Windows user '{brain}' does not exist (deploy it first).")

        # 1. Distro must boot (the engine). run_as_brain --wsl -- true boots it if idle.
        if wdb.distro_imported_as_brain(args):
            ok(f"wsl distro brain-{brain} boots")
        else:
            die(f"wsl distro brain-{brain} is not launchable — cannot repair the runtime.\n"
                "    Re-deploy with deploy_brain.py (the distro import is a deploy stage).")

        # 2. Optional deep reset of the engine (bounce the distro).
        if args.restart_docker:
            info("--restart-docker — terminating the distro so it cold-boots on next use")
            wdb.run_out(["wsl", "--terminate", wdb.distro_name(brain)])
            if not wdb.distro_imported_as_brain(args):
                die("distro did not boot back after terminate.")
            ok("distro bounced")

        # 3. Config regen (best-effort, in-distro), on request or when broken.
        rc, out, e = self._wsl(brain, brain_dir, "cd ~/docker && docker compose config -q 2>&1")
        cfg_ok = rc == 0
        if not cfg_ok:
            warn("compose config does NOT interpolate:"); info(((out + e).strip().splitlines() or ["?"])[0])
        if args.regen_config or not cfg_ok:
            gcfg = brain_dir / "system" / "brain_sbin" / "gateway_config.py"
            if gcfg.is_file():
                info("regenerating gateway config in-distro (gateway_config.py --brain-dir …)")
                self._wsl(brain, brain_dir, f"python3 {gcfg.as_posix()} --brain-dir ~/brains/{brain} 2>&1")
            else:
                warn(f"gateway_config.py not staged at {gcfg}; cannot regenerate.")

        # 4. Residency: (re)start the keepalive task so the distro stays resident.
        exists, running, _ = wdb.residency_task_running(brain)
        if exists and not running:
            info(f"residency task not running — schtasks /run /tn {wdb.residency_task(brain)}")
            run(["schtasks", "/run", "/tn", wdb.residency_task(brain)], check=False)
        elif not exists:
            warn(f"residency task {wdb.residency_task(brain)} absent — re-deploy to register it "
                 "(boot/idle persistence is a deploy stage).")

        # 5. Bring the stack up inside the distro.
        up = "cd ~/docker && docker compose up -d" + (" --force-recreate" if args.recreate else "")
        info(f"bringing stack up in-distro ({'force-recreate' if args.recreate else 'up -d'})")
        rc, out, e = self._wsl(brain, brain_dir, up)
        if rc != 0:
            die(f"stack bring-up FAILED (rc={rc}).\n{out}{e}")
        ok("stack bring-up issued")
        return 0


# ---------------------------------------------------------------------------
# OS dispatch
# ---------------------------------------------------------------------------

def _backend():
    if sys.platform.startswith("linux"):
        return LinuxBackend()
    if sys.platform in ("win32", "cygwin") or sys.platform.startswith("win"):
        return WindowsBackend()
    if sys.platform == "darwin":
        die("macOS is not yet a brain runtime target — the deploy path is objective 009 "
            "(Lima/Colima VM), not yet built. There is no macOS brain to diagnose or repair.\n"
            "    (On a Mac hosting a brain via a Linux VM, run brain_doctor inside that VM.)")
    die(f"unsupported platform {sys.platform!r} — brain_doctor targets Linux (native) or "
        "Windows (WSL2); macOS is objective 009.")


def diagnose(args):
    be = _backend()
    banner(f"Brain doctor — diagnose: {args.brain}  [{be.label}]")
    rep = be.diagnose(args)
    rep.print()
    verdict = "HEALTHY" if rep.healthy() else "UNHEALTHY"
    print(f"\n  verdict: {verdict}")
    return 0 if rep.healthy() else 1


def repair(args):
    be = _backend()
    banner(f"Brain doctor — repair: {args.brain}  [{be.label}]")
    code = be.repair(args)
    print()
    banner(f"Post-repair state: {args.brain}")
    rep = be.diagnose(args)
    rep.print()
    if rep.healthy():
        print("\n  verdict: HEALTHY")
        ok("REPAIR COMPLETE — brain is healthy")
        return 0
    print("\n  verdict: UNHEALTHY")
    warn("repair ran but the brain is not fully healthy — see the report above.")
    return code or 1


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    ap = argparse.ArgumentParser(
        description="Diagnose and repair a deployed brain's runtime (Linux / Windows).",
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
                    help="Linux: restart the rootless daemon; Windows: bounce (terminate) the distro")
    rp.add_argument("--recreate", action="store_true",
                    help="docker compose up -d --force-recreate (recreate all containers)")
    rp.add_argument("--regen-config", action="store_true",
                    help="re-render gateway/token config (gateway_config.py) before bring-up")
    rp.set_defaults(func=lambda a: sys.exit(repair(a)))

    return ap.parse_args()


def main():
    args = parse_args()
    validate_brain_name(args.brain)
    args.func(args)


if __name__ == "__main__":
    main()
