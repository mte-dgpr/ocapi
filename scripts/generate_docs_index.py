#!/usr/bin/env python3
#
# Copyright (c) 2026 Direction générale de la prévention des risques (DGPR).
#
# This file is part of OCAPI.
# See https://github.com/mte-dgpr/ocapi for further info.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Regenerate docs/index.html from snapshots/ (GitHub Pages).

Usage (from repo root):
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
    root = docs / "snapshots"
    if not root.is_dir():
        raise SystemExit(
            f"Missing {root}: copy snapshots first, e.g. "
            "`rm -rf docs/snapshots && cp -R snapshots docs/snapshots`"
        )

    arretes = sorted(root.glob("arretes_html/*/*.html"))
    permis = sorted(root.glob("arretes_consolidation/*/permis*.html"))

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
            arr_links.append(f'<a href="{html.escape(rel(p))}">{html.escape(p.name)}</a>')
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

    css = """
    body {
      font-family: system-ui, sans-serif;
      max-width: 960px;
      margin: 2rem auto;
      padding: 0 1rem;
      line-height: 1.5;
    }
    h1 { color: #1a1a2e; }
    table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
    th, td {
      border: 1px solid #ccc;
      padding: 0.5rem 0.75rem;
      vertical-align: top;
      text-align: left;
    }
    th { background: #f4f4f6; }
    code { font-size: 0.95em; }
    .note { color: #444; font-size: 0.95rem; margin-top: 1.5rem; }
    a { color: #0d47a1; }
"""

    repo_link = f'<a href="{html.escape(REPO_URL)}">mte-dgpr/ocapi</a>'
    page = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OCAPI — Exemples ICPE (arrêtés &amp; permis HTML)</title>
  <style>{css}  </style>
</head>
<body>
  <h1>OCAPI — Exemples ICPE (tests)</h1>
  <p>
    Cette page est publiée via <strong>GitHub Pages</strong>
    à partir du dossier <code>snapshots/</code> du dépôt {repo_link}.
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
    Pour activer le site :
    <em>Settings → Pages → Build and deployment → GitHub Actions</em>.
  </p>
</body>
</html>
"""
    out = docs / "index.html"
    out.write_text(page, encoding="utf-8")
    print(f"Wrote {out} ({len(all_aiots)} AIOT)")


if __name__ == "__main__":
    main()
