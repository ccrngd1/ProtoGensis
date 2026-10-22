"""Sandboxed execution of untrusted LLM-generated code.

Every run gets a fresh tempdir and an EMPTY environment. When running as
root: unshare --net (no network) and drop to uid/gid nobody. Always: rlimits
(CPU, AS, NPROC, FSIZE) and a wall-clock timeout. When not root (e.g. in
tests), rlimits + timeout still apply and the missing network isolation is
logged once.
"""

import logging
import os
import pwd
import resource
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass

log = logging.getLogger(__name__)

CPU_LIMIT_S = 30
AS_LIMIT_BYTES = 1 << 31          # 2 GiB address space
NPROC_LIMIT = 64
FSIZE_LIMIT_BYTES = 64 << 20      # 64 MiB max file size
DEFAULT_WALL_TIMEOUT_S = 40

_warned_no_netns = False


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    returncode: int | None
    timed_out: bool

    @property
    def ok(self) -> bool:
        return not self.timed_out and self.returncode == 0


def _is_root() -> bool:
    return os.geteuid() == 0


def _nobody_ids():
    p = pwd.getpwnam("nobody")
    return p.pw_uid, p.pw_gid


def _make_preexec():
    """Apply rlimits and setsid; does NOT drop privileges (handled by unshare --setuid/--setgid)."""
    def preexec():
        resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_S, CPU_LIMIT_S))
        resource.setrlimit(resource.RLIMIT_AS, (AS_LIMIT_BYTES, AS_LIMIT_BYTES))
        resource.setrlimit(resource.RLIMIT_NPROC, (NPROC_LIMIT, NPROC_LIMIT))
        resource.setrlimit(resource.RLIMIT_FSIZE, (FSIZE_LIMIT_BYTES, FSIZE_LIMIT_BYTES))
        os.setsid()
    return preexec


def run_untrusted(
    code: str,
    stdin_data: str = "",
    wall_timeout_s: float = DEFAULT_WALL_TIMEOUT_S,
    argv_extra: list | None = None,
) -> SandboxResult:
    """Run untrusted Python code in a fresh tempdir with an empty env."""
    global _warned_no_netns
    as_root = _is_root()
    workdir = tempfile.mkdtemp(prefix="sbx_")
    try:
        script = os.path.join(workdir, "main.py")
        with open(script, "w") as f:
            f.write(code)
        if as_root:
            uid, gid = _nobody_ids()
            os.chown(workdir, uid, gid)
            os.chown(script, uid, gid)
            # --setuid/--setgid drop privileges AFTER unshare creates the net namespace.
            # DO NOT use preexec_fn to setuid: that runs before exec(unshare) and
            # would deny the privilege needed to create a new network namespace.
            cmd = [
                "unshare", "--net",
                "--setuid", str(uid),
                "--setgid", str(gid),
                sys.executable, "-I", script,
            ]
        else:
            if not _warned_no_netns:
                log.warning(
                    "not running as root: network isolation (unshare --net) "
                    "unavailable; applying rlimits + timeout only"
                )
                _warned_no_netns = True
            cmd = [sys.executable, "-I", script]
        if argv_extra:
            cmd += argv_extra
        try:
            proc = subprocess.run(
                cmd,
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=wall_timeout_s,
                cwd=workdir,
                env={},  # empty environment: no tokens, no proxies, nothing
                preexec_fn=_make_preexec(),
            )
            return SandboxResult(proc.stdout, proc.stderr, proc.returncode, False)
        except subprocess.TimeoutExpired as e:
            out = e.stdout or b""
            err = e.stderr or b""
            if isinstance(out, bytes):
                out = out.decode(errors="replace")
            if isinstance(err, bytes):
                err = err.decode(errors="replace")
            return SandboxResult(out, err, None, True)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
