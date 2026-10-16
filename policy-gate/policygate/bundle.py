"""Policy bundle loader with git version pinning (AC #3). DETERMINISTIC.

A bundle TOML lists policy sources relative to a policy repo root. At a probe
time t each source resolves to the newest commit with committer time <= t
(git log -1 --before) and is read with `git show <sha>:<path>`. A source with
no commit <= t is ABSENT at t; a source whose newest commit <= t DELETED it is
also ABSENT (absent_reason "deleted", with the deleting sha), detected via the
allowlisted ls-tree. A per-source git error never aborts the bundle: the source
gets status ERROR with the message. Platform rules come from
config/platform_rules.toml with `effective_from` (ISO-8601 or "unknown").
"""

import json
import tomllib
from dataclasses import dataclass, field

from . import gitread


@dataclass
class SourceAt:
    path: str
    kind: str
    subjects: list
    precedence: int
    commit: str | None  # None = ABSENT at t (or ERROR)
    text: str | None
    status: str = "PRESENT"       # PRESENT | ABSENT | ERROR
    absent_reason: str | None = None   # "never_added" | "deleted" when ABSENT
    deleted_in: str | None = None      # sha of the deleting commit
    error: str | None = None           # git error message when status == ERROR


@dataclass
class BundleAt:
    root: str
    at: str
    sources: dict  # path -> SourceAt
    platform_rules: list = field(default_factory=list)


class PolicyBundle:
    def __init__(self, root, sources, platform_rules):
        self.root = str(root)
        self.sources = sources  # list of {path, kind, subjects, precedence}
        self.platform_rules = platform_rules

    @classmethod
    def load(cls, bundle_toml, root):
        with open(bundle_toml, "rb") as f:
            cfg = tomllib.load(f)
        sources = []
        for s in cfg.get("source", []):
            sources.append({
                "path": s["path"],
                "kind": s["kind"],
                "subjects": s.get("subjects", ["*"]),
                "precedence": int(s.get("precedence", 0)),
            })
        # per-agent sources generated from the agents list
        for agent in cfg.get("agents", []):
            for name, kind in (("AGENTS.md", "agent_agents"), ("SOUL.md", "agent_soul"),
                               ("MEMORY.md", "agent_memory")):
                prefix = "workspace" if agent == "main" else f"workspace-{agent}"
                sources.append({
                    "path": f"{prefix}/{name}",
                    "kind": kind,
                    "subjects": [f"agent:{agent}" if agent != "main" else "main"],
                    "precedence": int(cfg.get("agent_precedence", 10)),
                })
        platform_rules = []
        plat = cfg.get("platform_rules_file")
        if plat:
            import os
            p = plat if os.path.isabs(plat) else os.path.normpath(
                os.path.join(os.path.dirname(os.path.abspath(bundle_toml)), plat))
            with open(p, "rb") as f:
                platform_rules = tomllib.load(f).get("rule", [])
        return cls(root, sources, platform_rules)

    def at(self, t):
        resolved = {}
        for s in self.sources:
            resolved[s["path"]] = self._resolve_source(s, t)
        return BundleAt(root=self.root, at=t, sources=resolved,
                        platform_rules=self.platform_rules)

    def _resolve_source(self, s, t):
        """Resolve one source at t. Never raises: git errors become ERROR."""
        base = dict(path=s["path"], kind=s["kind"], subjects=s["subjects"],
                    precedence=s["precedence"])
        try:
            sha = gitread.commit_before(self.root, s["path"], t)
            if sha is None:
                return SourceAt(**base, commit=None, text=None, status="ABSENT",
                                absent_reason="never_added")
            # the newest commit touching the path may be the one that DELETED
            # it (git log --before includes deletions); check the tree first
            if not gitread.path_in_tree(self.root, sha, s["path"]):
                return SourceAt(**base, commit=None, text=None, status="ABSENT",
                                absent_reason="deleted", deleted_in=sha)
            text = gitread.show(self.root, sha, s["path"])
            return SourceAt(**base, commit=sha, text=text)
        except gitread.GitReadError as e:
            return SourceAt(**base, commit=None, text=None, status="ERROR",
                            error=str(e))


def history(pb, since=None, until=None):
    """Per source, every commit that touched it (sha, committer time ISO-8601
    UTC, change kind A/M/D), oldest first, via gitread `log` only. Per-source
    git errors become {"status": "ERROR", "error": msg} instead of aborting."""
    out = {}
    for s in pb.sources:
        try:
            commits = gitread.history(pb.root, s["path"], since=since, until=until)
            out[s["path"]] = {"status": "OK", "commits": commits}
        except gitread.GitReadError as e:
            out[s["path"]] = {"status": "ERROR", "error": str(e), "commits": []}
    return out


def render_history(pb, hist, since=None, until=None, fmt="json"):
    data = {
        "schema": "policygate-bundle-history-v1",
        "root": pb.root,
        "since": since,
        "until": until,
        "sources": {p: hist[p] for p in sorted(hist)},
    }
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=2)
    lines = [f"bundle history (since={since} until={until})"]
    for p in sorted(hist):
        h = hist[p]
        if h["status"] == "ERROR":
            lines.append(f"  {p}: ERROR {h['error']}")
            continue
        lines.append(f"  {p}: {len(h['commits'])} commit(s)")
        for c in h["commits"]:
            lines.append(f"    {c['kind']} {c['sha'][:8]} {c['time']}")
    return "\n".join(lines)


def _source_dict(s):
    d = {
        "kind": s.kind,
        "subjects": s.subjects,
        "precedence": s.precedence,
        "commit": s.commit if s.commit else ("ERROR" if s.status == "ERROR" else "ABSENT"),
        "bytes": len(s.text) if s.text is not None else 0,
        "status": s.status,
    }
    if s.absent_reason:
        d["absent_reason"] = s.absent_reason
    if s.deleted_in:
        d["deleted_in"] = s.deleted_in
    if s.error:
        d["error"] = s.error
    return d


def render_show(bundle_at, fmt):
    data = {
        "at": bundle_at.at,
        "sources": {p: _source_dict(s) for p, s in sorted(bundle_at.sources.items())},
        "platform_rules": [
            {"id": r["id"], "effective_from": r.get("effective_from", "unknown"),
             "source": r.get("source", "")}
            for r in bundle_at.platform_rules
        ],
    }
    if fmt == "json":
        return json.dumps(data, sort_keys=True, indent=2)
    lines = [f"bundle at {bundle_at.at}"]
    for p, s in sorted(bundle_at.sources.items()):
        if s.commit:
            c = s.commit[:8]
        elif s.status == "ERROR":
            c = "ERROR"
        elif s.absent_reason == "deleted":
            c = f"ABSENT (deleted in {s.deleted_in[:8]})"
        else:
            c = "ABSENT"
        lines.append(f"  {p:55s} {c}")
    for r in bundle_at.platform_rules:
        lines.append(f"  platform {r['id']}: effective_from={r.get('effective_from', 'unknown')}")
    return "\n".join(lines)
