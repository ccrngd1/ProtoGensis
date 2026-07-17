"""HTML reporter (FR7.3) — shareable, self-contained report (blog screenshots).

Dependency-free: builds a small static HTML document with inline CSS so the
report renders anywhere without external assets.
"""

from __future__ import annotations

import html

from setup_trap.model import Provenance, Severity

_SEV_COLOR = {
    Severity.CRITICAL: "#c0392b",
    Severity.WARNING: "#d68910",
    Severity.INFO: "#2471a3",
}
_PROV_BADGE = {
    Provenance.SOURCED: ("🟢 sourced", "#1e8449"),
    Provenance.SYNTHESIZED: ("🟡 synthesized", "#b7950b"),
    Provenance.INFERRED: ("🔵 inferred", "#2471a3"),
}


def _esc(s) -> str:
    return html.escape(str(s or ""))


def render_html(result, *, path: str = "", title: str = "SetupTrap report") -> str:
    grouped = result.by_severity()
    counts = {sev: len(grouped[sev]) for sev in Severity}

    rows = []
    for sev in (Severity.CRITICAL, Severity.WARNING, Severity.INFO):
        for f in grouped[sev]:
            prov = (
                Provenance(f.provenance)
                if isinstance(f.provenance, str)
                else f.provenance
            )
            badge_text, badge_color = _PROV_BADGE[prov]
            note = (
                f'<div class="note">note: {_esc(f.note)}</div>' if f.note else ""
            )
            source = (
                f'<span class="src">{_esc(f.source_ref)}</span>'
                if f.source_ref
                else ""
            )
            rows.append(
                f"""
      <div class="finding sev-{sev.name.lower()}">
        <div class="fhead">
          <span class="sev" style="background:{_SEV_COLOR[sev]}">{sev.label}</span>
          <span class="rid">{_esc(f.rule_id)}</span>
          <span class="rname">{_esc(f.rule_name)}</span>
          <span class="prov" style="color:{badge_color}">{badge_text}</span>
          {source}
        </div>
        <div class="loc">{_esc(f.file)}:{f.line}</div>
        <pre class="match">{_esc(f.matched_text)}</pre>
        <div class="msg">{_esc(f.message)}</div>
        {note}
        <div class="fix">Fix: {_esc(f.fix_guidance)}</div>
      </div>"""
            )

    findings_html = "\n".join(rows) or '<p class="clean">No findings. Clean.</p>'

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{_esc(title)}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem;
          background: #f7f9fb; color: #1a1a1a; }}
  h1 {{ margin-bottom: .2rem; }}
  .meta {{ color: #555; margin-bottom: 1rem; }}
  .summary span {{ display:inline-block; padding:.3rem .7rem; border-radius:6px;
                   color:#fff; margin-right:.5rem; font-weight:600; }}
  .finding {{ background:#fff; border-left:5px solid #ccc; border-radius:6px;
              padding:1rem; margin:.8rem 0; box-shadow:0 1px 3px rgba(0,0,0,.08); }}
  .finding.sev-critical {{ border-left-color:{_SEV_COLOR[Severity.CRITICAL]}; }}
  .finding.sev-warning  {{ border-left-color:{_SEV_COLOR[Severity.WARNING]}; }}
  .finding.sev-info     {{ border-left-color:{_SEV_COLOR[Severity.INFO]}; }}
  .fhead {{ display:flex; gap:.6rem; align-items:center; flex-wrap:wrap; }}
  .sev {{ color:#fff; padding:.1rem .5rem; border-radius:4px; font-size:.8rem; }}
  .rid {{ font-family:monospace; font-weight:700; }}
  .rname {{ font-weight:600; }}
  .prov {{ font-weight:600; font-size:.85rem; }}
  .src {{ font-size:.8rem; color:#666; font-family:monospace; }}
  .loc {{ color:#555; font-family:monospace; font-size:.85rem; margin:.3rem 0; }}
  .match {{ background:#f0f0f0; padding:.4rem .6rem; border-radius:4px;
            overflow-x:auto; font-size:.85rem; }}
  .msg {{ margin:.4rem 0; }}
  .note {{ color:#2471a3; font-style:italic; }}
  .fix {{ color:#1e8449; margin-top:.3rem; }}
  .legend {{ margin-top:2rem; padding:1rem; background:#eef3f8; border-radius:6px;
             font-size:.9rem; }}
</style></head>
<body>
  <h1>{_esc(title)}</h1>
  <div class="meta">path: <code>{_esc(path or '.')}</code> &middot;
    files scanned: {result.files_scanned} &middot; rules: {result.rules_loaded}</div>
  <div class="summary">
    <span style="background:{_SEV_COLOR[Severity.CRITICAL]}">Critical: {counts[Severity.CRITICAL]}</span>
    <span style="background:{_SEV_COLOR[Severity.WARNING]}">Warning: {counts[Severity.WARNING]}</span>
    <span style="background:{_SEV_COLOR[Severity.INFO]}">Info: {counts[Severity.INFO]}</span>
  </div>
  {findings_html}
  <div class="legend">
    <strong>Provenance (honesty gate):</strong><br>
    🟢 <b>sourced</b> — package-install supply-chain checks empirically evaluated
       by arXiv:2607.15143.<br>
    🟡 <b>synthesized</b> — behavior-hijacking rules grounded in prompt-injection
       literature, NOT paper-proven.<br>
    🔵 <b>inferred</b> — reasonable deduction (e.g. undocumented runtime read-order).
  </div>
</body></html>"""
