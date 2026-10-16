"""Read-only guard over the OpenClaw tree, enforced at runtime via sys.addaudithook.

Protected roots: always /root/.openclaw, plus any --root / --path passed to a
subcommand, plus $OPENCLAW_HOME if set. Under a protected root the hook raises
GuardViolation on write/create opens, destructive os.* calls, sqlite3.connect,
and non-allowlisted subprocess use. Invoking an `openclaw` binary is a
violation everywhere, not only under a root.

Audit hooks cannot be uninstalled, so violations are scoped to the protected
roots: file operations elsewhere (results/, local/, tmp dirs) pass through.
"""

import os
import re
import sys

OPENCLAW_ROOT = "/root/.openclaw"
GIT_READ_ALLOWED = {"log", "show", "cat-file", "rev-parse", "ls-tree"}
# `openclaw` is named here only so the guard can BLOCK any invocation of it.
_OPENCLAW_WORD = re.compile(r"(^|[\s;&|(`])openclaw($|[\s;&|)`])")

_WRITE_MODE = re.compile(r"[wax+]")
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC

_state = {"installed": False, "roots": [], "enabled": True}


class GuardViolation(Exception):
    """A write/mutation was attempted under a protected root (CLI exit 3)."""


def _norm(path):
    if hasattr(path, "__fspath__"):
        path = path.__fspath__()
    if isinstance(path, bytes):
        try:
            path = os.fsdecode(path)
        except Exception:
            return None
    if not isinstance(path, str):
        return None
    return os.path.abspath(path)


def _under_root(path):
    p = _norm(path)
    if p is None:
        return False
    for root in _state["roots"]:
        if p == root or p.startswith(root + os.sep):
            return True
    return False


def _is_write_open(mode, flags):
    if isinstance(mode, str) and mode:
        return bool(_WRITE_MODE.search(mode))
    if isinstance(flags, int):
        return bool(flags & _WRITE_FLAGS)
    return False


def _strings(args):
    out = []
    if args is None:
        return out
    if isinstance(args, (str, bytes)):
        args = [args]
    try:
        for a in args:
            if isinstance(a, bytes):
                try:
                    a = os.fsdecode(a)
                except Exception:
                    continue
            if isinstance(a, str):
                out.append(a)
    except TypeError:
        pass
    return out


def _git_subcommand(argv):
    """First subcommand of a git argv, skipping -C <dir>, -c k=v and --opts."""
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        return a
    return None


def _refs_protected(strs, cwd=None):
    if cwd is not None and _under_root(cwd):
        return True
    for s in strs:
        for root in _state["roots"]:
            if root in s:
                return True
    return False


# Read-only pipeline heads a shell command may use while naming a protected
# root (claims verify re-runs ledger commands like
# `policygate bundle show --root /root/.openclaw ... | jq -r ...`).
_SAFE_HEADS = {"policygate", "jq", "grep", "head", "tail", "cut", "sort", "wc",
               "diff", "cmp", "test", "tr", "uniq", "read", "while", "do", "done"}
_SHELL_SPLIT = re.compile(r"\|\||&&|[|;\n]")


def _shell_cmd_safe(cmd):
    """True if every pipeline segment of a shell string has a read-only head
    and nothing redirects into a protected root."""
    for seg in _SHELL_SPLIT.split(cmd):
        seg = seg.strip()
        if not seg:
            continue
        if ">" in seg and _refs_protected([seg.split(">", 1)[1]]):
            return False
        toks = seg.split()
        while toks and re.match(r"^\w+=", toks[0]):
            toks = toks[1:]
        if not toks:
            continue
        head = os.path.basename(toks[0])
        if head == "git":
            if _git_subcommand(toks) not in GIT_READ_ALLOWED:
                return False
            continue
        if head not in _SAFE_HEADS:
            return False
    return True


def _check_exec(argv, cwd=None):
    strs = _strings(argv)
    if not strs:
        return
    head = os.path.basename(strs[0])
    if head == "openclaw" or any(
        _OPENCLAW_WORD.search(s) for s in strs
    ):
        raise GuardViolation(f"invocation of an openclaw binary is blocked: {strs[:3]}")
    if head == "git":
        sub = _git_subcommand(strs)
        if sub in GIT_READ_ALLOWED:
            return
        if _refs_protected(strs, cwd):
            raise GuardViolation(
                f"git subcommand {sub!r} not in read allowlist under a protected root"
            )
        return
    if head == "policygate":
        return
    if head in ("bash", "sh") and len(strs) >= 3 and strs[1] == "-c":
        if _refs_protected(strs[2:], cwd) and not _shell_cmd_safe(strs[2]):
            raise GuardViolation(f"shell command references a protected root: {strs[2][:80]}")
        return
    if _refs_protected(strs, cwd):
        raise GuardViolation(f"subprocess call references a protected root: {strs[:3]}")


def _hook(event, args):
    if not _state["enabled"]:
        return
    try:
        if event == "open":
            path, mode, flags = args[0], args[1], args[2]
            if _is_write_open(mode, flags) and _under_root(path):
                raise GuardViolation(f"write open under protected root: {_norm(path)}")
        elif event in ("os.remove", "os.unlink", "os.rmdir", "os.mkdir", "os.chmod",
                       "os.utime", "shutil.rmtree"):
            if args and _under_root(args[0]):
                raise GuardViolation(f"{event} under protected root: {_norm(args[0])}")
        elif event == "os.rename":
            if (args and _under_root(args[0])) or (len(args) > 1 and _under_root(args[1])):
                raise GuardViolation(f"rename touching protected root")
        elif event == "sqlite3.connect":
            if args and _under_root(args[0]):
                raise GuardViolation(f"sqlite3.connect under protected root: {_norm(args[0])}")
        elif event == "subprocess.Popen":
            executable, argv, cwd = args[0], args[1], args[2]
            full = _strings(argv) or _strings([executable])
            _check_exec(full, cwd)
        elif event in ("os.exec", "os.posix_spawn", "os.spawn"):
            # (path, args, env[, ...])
            path = args[0] if args else None
            argv = args[1] if len(args) > 1 else None
            full = _strings(argv) or _strings([path])
            _check_exec(full)
        elif event == "os.system":
            cmd = _strings([args[0]]) if args else []
            if cmd:
                if _OPENCLAW_WORD.search(cmd[0]):
                    raise GuardViolation("os.system invoking openclaw is blocked")
                if _refs_protected(cmd):
                    raise GuardViolation("os.system references a protected root")
    except GuardViolation:
        raise
    except Exception:
        # the guard must never crash unrelated code on malformed audit args
        return


def install(roots=()):
    """Install the audit hook (once) and register protected roots.

    The always-protected roots (/root/.openclaw, $OPENCLAW_HOME) are
    re-registered on every call, not only on first install: audit hooks cannot
    be removed, so the test suite isolates guard-installing tests from
    subprocess-spawning tests by clearing the registered roots between tests
    (_reset_registered_roots) and relying on the next install() to restore
    them. In real CLI use install() runs once, before dispatch, and nothing
    ever clears the roots."""
    if OPENCLAW_ROOT not in _state["roots"]:
        _state["roots"].append(OPENCLAW_ROOT)
    env_home = os.environ.get("OPENCLAW_HOME")
    if env_home:
        add_roots([env_home])
    add_roots(roots)
    if not _state["installed"]:
        sys.addaudithook(_hook)
        _state["installed"] = True


def _reset_registered_roots():
    """TEST ISOLATION ONLY: clear the registered roots so a test that
    installed the hook does not block later tests' subprocess calls (e.g. the
    host tests spawning `python -m policygate.cli ... --root /root/.openclaw`;
    the spawned CLI installs its own guard). The hook itself stays installed —
    it cannot be removed — and openclaw-binary invocations stay blocked
    (that check is root-independent). Never called from CLI/package code."""
    _state["roots"] = []


def add_roots(roots):
    for r in roots or ():
        n = _norm(r)
        if n and n not in _state["roots"]:
            _state["roots"].append(n)


def selftest(root):
    """Plant 9 violations under `root` and assert each raises GuardViolation.

    Works whether `root` exists already (empty dir) or not (created here,
    before it becomes protected).
    """
    import sqlite3
    import subprocess

    root = os.path.abspath(root)
    os.makedirs(root, exist_ok=True)
    install()
    add_roots([root])

    target = os.path.join(root, "planted.txt")
    plants = [
        ("write-open", lambda: open(target, "w")),
        ("append-open", lambda: open(target, "a")),
        ("rename", lambda: os.rename(target, target + ".x")),
        ("mkdir", lambda: os.mkdir(os.path.join(root, "d"))),
        ("sqlite-connect", lambda: sqlite3.connect(os.path.join(root, "db.sqlite"))),
        ("git-status", lambda: subprocess.run(["git", "-C", root, "status"])),
        ("git-checkout", lambda: subprocess.run(["git", "-C", root, "checkout", "x"])),
        ("openclaw", lambda: subprocess.run(["openclaw", "--version"])),
        ("bash-c", lambda: subprocess.run(["bash", "-c", f"echo x > {root}/f"])),
    ]
    blocked = 0
    failures = []
    for name, fn in plants:
        try:
            fn()
        except GuardViolation:
            blocked += 1
            continue
        except Exception as e:  # pragma: no cover - unexpected
            failures.append(f"{name}: raised {type(e).__name__} instead of GuardViolation")
            continue
        failures.append(f"{name}: NOT blocked")
    ok = blocked == len(plants)
    lines = [f"GUARD OK: {blocked}/{len(plants)} planted violations blocked"] if ok else (
        [f"GUARD FAIL: {blocked}/{len(plants)} planted violations blocked"] + failures
    )
    return ok, lines
