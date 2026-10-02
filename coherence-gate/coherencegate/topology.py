"""Topology registry (the paper's H: what is local, who reads/writes what).

MVP: a role -> {read keys, write keys} registry used by the gate's authority
check. Should-ship extras: a GYO-reduction join-tree check on the role-overlap
hypergraph (Thm 3.1; hub-and-spoke is a star, so it reports acyclic; a 3-cycle
reports cyclic) and a Bernstein parallel-safety table.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RoleSpec:
    reads: set[str] = field(default_factory=set)
    writes: set[str] = field(default_factory=set)


class Topology:
    def __init__(self) -> None:
        self._roles: dict[str, RoleSpec] = {}

    def register(self, role: str, reads: set[str] | None = None,
                 writes: set[str] | None = None) -> None:
        self._roles[role] = RoleSpec(set(reads or ()), set(writes or ()))

    def can_write(self, role: str, key: str) -> bool:
        spec = self._roles.get(role)
        if spec is None:
            return False
        return key in spec.writes

    def role(self, name: str) -> RoleSpec | None:
        return self._roles.get(name)

    def roles(self) -> dict[str, RoleSpec]:
        return dict(self._roles)

    # ---- should-ship: GYO join-tree check (Thm 3.1) ----
    def gyo_check(self) -> dict:
        """GYO reduction on the hypergraph whose edges are each role's key scope
        (reads ∪ writes). Returns {"acyclic": bool, "message": str}."""
        edges = {name: (spec.reads | spec.writes)
                 for name, spec in self._roles.items() if (spec.reads | spec.writes)}
        hyper = {name: set(keys) for name, keys in edges.items()}
        changed = True
        while changed and hyper:
            changed = False
            # Rule 1: remove vertices that appear in exactly one edge (ears' private keys)
            counts: dict[str, int] = {}
            for keys in hyper.values():
                for k in keys:
                    counts[k] = counts.get(k, 0) + 1
            for name in list(hyper):
                lonely = {k for k in hyper[name] if counts.get(k, 0) == 1}
                if lonely:
                    hyper[name] -= lonely
                    changed = True
            # Rule 2: remove empty edges or edges contained in another edge
            for name in list(hyper):
                keys = hyper[name]
                if not keys:
                    del hyper[name]
                    changed = True
                    continue
                for other, okeys in hyper.items():
                    if other != name and keys <= okeys:
                        del hyper[name]
                        changed = True
                        break
        if not hyper:
            return {"acyclic": True,
                    "message": "acyclic: pairwise reconciliation suffices (join tree exists)"}
        return {"acyclic": False,
                "message": "cyclic: pairwise reconciliation insufficient "
                           f"(irreducible core: {sorted(hyper)})"}

    # ---- should-ship: Bernstein parallel-safety table ----
    def bernstein_table(self) -> list[dict]:
        """Pairwise parallel safety: safe iff W_i∩R_j = W_j∩R_i = W_i∩W_j = ∅."""
        names = sorted(self._roles)
        rows = []
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                sa, sb = self._roles[a], self._roles[b]
                conflicts = sorted((sa.writes & sb.reads) | (sb.writes & sa.reads)
                                   | (sa.writes & sb.writes))
                rows.append({"pair": [a, b], "parallel_safe": not conflicts,
                             "conflict_keys": conflicts})
        return rows
