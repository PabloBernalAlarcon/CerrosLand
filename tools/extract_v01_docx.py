"""Extract rule titles, validation states and source-hierarchy notes from the v0.1
component DOCX fichas (the only place where they survive).

Usage: python3 -I extract_v01_docx.py <dir_with_v01_docx> <out.json>
Read-only on inputs; writes one JSON file.
"""
import json
import re
import sys
from pathlib import Path

import docx

CID = re.compile(r"(?<![A-Z])((?:FL|TX|WF|PR|IN|SP)-[A-Z][0-9]{2})(?![0-9])")


def cells(row):
    return [c.text.strip() for c in row.cells]


def main(src: Path, out: Path):
    result = {}
    for p in sorted(src.rglob("*.docx")):
        name = p.name
        m = CID.search(name)
        if not m or "Indice" in name:
            continue
        cid = m.group(1)
        d = docx.Document(str(p))
        rules, states, notes = {}, {}, []
        for t in d.tables:
            if not t.rows:
                continue
            head = [h.lower() for h in cells(t.rows[0])]
            if head[:1] == ["id"] and len(head) >= 3 and "regla" in head[1]:
                for r in t.rows[1:]:
                    c = cells(r)
                    if c[0].startswith("R-"):
                        rules[c[0]] = {"title": c[1], "text": c[2]}
            elif head[:1] == ["estado"] and len(head) >= 2:
                for r in t.rows[1:]:
                    c = cells(r)
                    if c[0]:
                        states[c[0]] = c[1]
        # paragraphs right after the sources table often carry hierarchy notes
        paras = [x.text.strip() for x in d.paragraphs]
        for i, txt in enumerate(paras):
            if re.search(r"prelaci|jerarqu|precedencia|prevalec", txt, re.I) and len(txt) < 400:
                notes.append(txt)
        result[cid] = {"file": name, "rules": rules, "validation_states": states,
                       "hierarchy_notes": notes}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(result)} components extracted")
    for cid, v in sorted(result.items()):
        print(f"  {cid}: {len(v['rules'])} rules, states={list(v['validation_states'])}, notes={len(v['hierarchy_notes'])}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
