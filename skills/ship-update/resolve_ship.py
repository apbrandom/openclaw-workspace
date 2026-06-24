#!/usr/bin/env python3
"""Resolve a free-text ship name to its canonical filename.

Reads JSON from stdin or --json arg.

Input:
  {"query": "Модус"}          # any form: Cyrillic alias, English, uppercase, mixed

Output (stdout, JSON):
  {"found": true,  "canonical": "MODUS", "path": "vault/ships/craneship/MODUS.md"}
  {"found": false, "query":    "Неизвестное"}

Matching order (stops at first hit):
  1. Exact filename match (case-insensitive): "modus" → MODUS.md
  2. `name:` field in frontmatter (case-insensitive)
  3. Any entry in `aliases:` list (case-insensitive)
  3.5 Token-exact (multi-word query): one ship uniquely matches a token → resolve
      (forward titles like "Атлас-1 Атлас"). Ambiguous/no-match falls through.
  4. Partial / prefix match (≥4 chars) — returns first hit, marks `"partial": true`

Exit 0 always (caller decides what to do with found=false).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WORKSPACE = Path("/home/apbrandom/.openclaw/workspace")
SHIPS_DIRS = [
    WORKSPACE / "vault" / "ships" / "myship",
    WORKSPACE / "vault" / "ships" / "craneship",
]

_FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_NAME_RE = re.compile(r"^name:\s*(.+)$", re.MULTILINE)
_ALIASES_BLOCK_RE = re.compile(r"^aliases:\n((?:[ \t]+-[ \t]+.+\n?)*)", re.MULTILINE)
_ALIAS_ITEM_RE = re.compile(r"^[ \t]+-[ \t]+(.+)$", re.MULTILINE)


def _parse_frontmatter(text: str) -> dict:
    m = _FM_RE.match(text)
    if not m:
        return {}
    fm = m.group(1)
    name_m = _NAME_RE.search(fm)
    name = name_m.group(1).strip() if name_m else ""
    aliases_m = _ALIASES_BLOCK_RE.search(fm)
    aliases = []
    if aliases_m:
        aliases = [a.strip() for a in _ALIAS_ITEM_RE.findall(aliases_m.group(1))]
    return {"name": name, "aliases": aliases}


def _all_cards() -> list[tuple[Path, dict]]:
    cards = []
    for d in SHIPS_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            try:
                fm = _parse_frontmatter(p.read_text(encoding="utf-8"))
                cards.append((p, fm))
            except OSError:
                pass
    return cards


def resolve(query: str) -> dict:
    q = query.strip()
    q_lower = q.lower()

    cards = _all_cards()

    # Pass 1: exact filename match (case-insensitive)
    for p, fm in cards:
        if p.stem.lower() == q_lower:
            return {"found": True, "canonical": p.stem,
                    "path": str(p.relative_to(WORKSPACE))}

    # Pass 2: frontmatter name match
    for p, fm in cards:
        if fm.get("name", "").lower() == q_lower:
            return {"found": True, "canonical": p.stem,
                    "path": str(p.relative_to(WORKSPACE))}

    # Pass 3: alias match
    for p, fm in cards:
        for alias in fm.get("aliases", []):
            if alias.lower() == q_lower:
                return {"found": True, "canonical": p.stem,
                        "path": str(p.relative_to(WORKSPACE))}

    # Pass 3.5: token-exact match — forward-шапка вида "Атлас-1 Атлас" (алиас +
    # лишнее слово). Бьём запрос на токены; если РОВНО одно судно точно матчит
    # какой-либо токен по stem/name/alias — резолвим. Неоднозначность ("Атлас" →
    # ATLAS_1 и ATLAS_5) или промах → проваливаемся дальше. Чистый резолв имени.
    tokens = [t for t in re.split(r"\s+", q) if t]
    if len(tokens) > 1:
        matched: dict[str, Path] = {}
        for p, fm in cards:
            keys = {p.stem.lower(), fm.get("name", "").lower()}
            keys |= {a.lower() for a in fm.get("aliases", [])}
            keys.discard("")
            if any(tok.lower() in keys for tok in tokens):
                matched[p.stem] = p
        if len(matched) == 1:
            p = next(iter(matched.values()))
            return {"found": True, "canonical": p.stem,
                    "path": str(p.relative_to(WORKSPACE))}

    # Pass 4: prefix / partial (≥4 chars)
    if len(q) >= 4:
        hits = []
        for p, fm in cards:
            candidates = [p.stem, fm.get("name", "")] + fm.get("aliases", [])
            for c in candidates:
                if c.lower().startswith(q_lower) or q_lower in c.lower():
                    hits.append((p, fm))
                    break
        if len(hits) == 1:
            p, _ = hits[0]
            return {"found": True, "canonical": p.stem,
                    "path": str(p.relative_to(WORKSPACE)), "partial": True}

    return {"found": False, "query": q}


def main() -> None:
    ap = argparse.ArgumentParser(description="Resolve ship name alias to canonical")
    ap.add_argument("--json", help="JSON payload (if absent, read from stdin)")
    args = ap.parse_args()

    raw = args.json if args.json is not None else sys.stdin.read()
    if not raw.strip():
        print(json.dumps({"found": False, "query": "", "error": "empty input"}))
        sys.exit(0)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"found": False, "query": raw.strip(), "error": str(e)}))
        sys.exit(0)

    query = payload.get("query", "")
    if not isinstance(query, str) or not query.strip():
        print(json.dumps({"found": False, "query": str(query), "error": "'query' missing or empty"}))
        sys.exit(0)

    print(json.dumps(resolve(query), ensure_ascii=False))


if __name__ == "__main__":
    main()
