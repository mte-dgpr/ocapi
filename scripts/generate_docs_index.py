#!/usr/bin/env python3
"""Regenerate docs/index.html from docs/examples/ (GitHub Pages).

Usage (from repo root):
  cp -R examples docs/examples   # mirror examples first
  python scripts/generate_docs_index.py
"""
from __future__ import annotations

import html
from collections import defaultdict
from pathlib import Path

REPO_URL = "https://github.com/mte-dgpr/ocapi"


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    docs = repo_root / "docs"
    root = docs / "examples"
    if not root.is_dir():
        raise SystemExit(
            f"Missing {root}: copy examples first, e.g. "
            "`rm -rf docs/examples && cp -R examples docs/examples`"
        )

    arretes = sorted(root.glob("arretes_html/*/*.html"))
    permis = sorted(root.glob("consolidated_permit/*/permis*.html"))

    arretes_by: dict[str, list[Path]] = defaultdict(list)
    for p in arretes:
        aiot = p.relative_to(root).parts[1]
        arretes_by[aiot].append(p)

    permis_by: dict[str, Path] = {}
    for p in permis:
        aiot = p.relative_to(root).parts[1]
        permis_by[aiot] = p

    all_aiots = sorted(set(arretes_by) | set(permis_by))

    def rel(p: Path) -> str:
        return p.relative_to(docs).as_posix()

    rows: list[str] = []
    for aiot in all_aiots:
        arr_links = []
        for p in sorted(arretes_by.get(aiot, []), key=lambda x: x.name):
            arr_links.append(
                f'<a href="{html.escape(rel(p))}">{html.escape(p.name)}</a>'
            )
        arr_cell = "<br>".join(arr_links) if arr_links else "—"
        if aiot in permis_by:
            p = permis_by[aiot]
            perm_cell = f'<a href="{html.escape(rel(p))}">permis consolidé</a>'
        else:
            perm_cell = "—"
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(aiot)}</code></td>"
            f"<td>{arr_cell}</td>"
            f"<td>{perm_cell}</td>"
            "</tr>"
        )

    table_body = "\n".join(rows)

    page = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OCAPI — Exemples ICPE (arrêtés & permis HTML)</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
    h1 {{ color: #1a1a2e; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #ccc; padding: 0.5rem 0.75rem; vertical-align: top; text-align: left; }}
    th {{ background: #f4f4f6; }}
    code {{ font-size: 0.95em; }}
    .note {{ color: #444; font-size: 0.95rem; margin-top: 1.5rem; }}
    a {{ color: #0d47a1; }}
  </style>
</head>
<body>
  <h1>OCAPI — Exemples ICPE (tests)</h1>
  <p>
    Cette page est publiée via <strong>GitHub Pages</strong> à partir du dossier <code>docs/</code> du dépôt
    <a href="{html.escape(REPO_URL)}">mte-dgpr/ocapi</a>.
    Les fichiers ci-dessous proviennent du dossier <code>examples/</code> (copie sous <code>docs/examples/</code> pour l’hébergement statique).
  </p>
  <table>
    <thead>
      <tr>
        <th>Code AIOT</th>
        <th>Arrêtés (HTML)</th>
        <th>Permis consolidé</th>
      </tr>
    </thead>
    <tbody>
{table_body}
    </tbody>
  </table>
  <p class="note">
    Pour activer le site : <em>Settings → Pages → Build and deployment → Branch → main, folder /docs</em>.
  </p>
</body>
</html>
"""
    out = docs / "index.html"
    out.write_text(page, encoding="utf-8")
    print(f"Wrote {out} ({len(all_aiots)} AIOT)")


if __name__ == "__main__":
    main()
