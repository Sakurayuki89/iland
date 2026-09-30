#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema"]
# ///
"""Lint learning content for the kids' English game.

Checks (errors unless noted):
  * JSON Schema for vocab rows, dialogues, quests
  * English lines are <= 12 words
  * Every English word is allowed: function words + vocab of units <= the file's unit (+ names)
  * Korean translation is present and contains Hangul
  * duplicate ids
  * referenced image/audio files exist  (warning; error with --strict)

Exit code 0 = no errors, 1 = errors.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from _common import utf8_output

MAX_WORDS = 12
WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
HANGUL_RE = re.compile(r"[ㄱ-ㆎ가-힣]")


class Report:
    def __init__(self):
        self.items: list[tuple[str, str, str]] = []

    def error(self, where, msg): self.items.append(("ERROR", where, msg))
    def warn(self, where, msg): self.items.append(("WARN", where, msg))

    @property
    def errors(self): return sum(1 for i in self.items if i[0] == "ERROR")

    @property
    def warnings(self): return sum(1 for i in self.items if i[0] == "WARN")


def load_schema(schema_dir: Path, name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((schema_dir / name).read_text(encoding="utf-8")))


def schema_errors(validator, instance, where, rep: Report):
    for e in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        loc = "/".join(str(p) for p in e.absolute_path) or "(root)"
        rep.error(f"{where}:{loc}", f"schema: {e.message}")


def tokens(text: str) -> list[str]:
    return [t.lower() for t in WORD_RE.findall(text)]


def word_ok(tok: str, allowed: set[str]) -> bool:
    cands = {tok}
    if tok.endswith("ies"): cands.add(tok[:-3] + "y")
    if tok.endswith("es"): cands.add(tok[:-2])
    if tok.endswith("s"): cands.add(tok[:-1])
    if tok.endswith("'s"): cands.add(tok[:-2])
    return bool(cands & allowed)


def check_sentence(where, en, ko, allowed: set[str], rep: Report):
    toks = tokens(en)
    if len(toks) > MAX_WORDS:
        rep.error(where, f"English has {len(toks)} words (max {MAX_WORDS}): \"{en}\"")
    unknown = sorted({t for t in toks if not word_ok(t, allowed)})
    if unknown:
        rep.error(where, f"words not allowed at this unit: {', '.join(unknown)}  in \"{en}\"")
    if not ko or not ko.strip():
        rep.error(where, "Korean translation is empty")
    elif not HANGUL_RE.search(ko):
        rep.error(where, f"Korean translation has no Hangul: \"{ko}\"")


def load_vocab(data_dir: Path, schema_dir: Path, rep: Report):
    validator = load_schema(schema_dir, "vocab.schema.json")
    by_unit: dict[int, set[str]] = {}
    seen_ids: dict[str, str] = {}
    assets: list[tuple[str, str]] = []
    files = sorted((data_dir / "vocab").glob("*.csv"))
    for f in files:
        with f.open(encoding="utf-8-sig", newline="") as fh:
            for n, row in enumerate(csv.DictReader(fh), start=2):
                where = f"{f.name}:{n}"
                row = {k: (v or "").strip() for k, v in row.items() if k}
                inst = dict(row)
                if inst.get("unit", "").isdigit():
                    inst["unit"] = int(inst["unit"])
                schema_errors(validator, inst, where, rep)
                if row.get("id") in seen_ids:
                    rep.error(where, f"duplicate id '{row['id']}' (also {seen_ids[row['id']]})")
                elif row.get("id"):
                    seen_ids[row["id"]] = where
                if isinstance(inst.get("unit"), int) and row.get("word"):
                    by_unit.setdefault(inst["unit"], set()).update(tokens(row["word"]))
                for col in ("image", "audio"):
                    assets.append((f"{f.name}:{n}", row.get(col, "")))
    return by_unit, assets, len(files)


def load_function_words(data_dir: Path) -> set[str]:
    p = data_dir / "vocab" / "function_words.txt"
    if not p.exists():
        return set()
    out = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip().lower()
        out.update(line.split())
    return out


def allowed_for(unit: int, by_unit, function_words, names) -> set[str]:
    a = set(function_words) | {n.lower() for n in names}
    for u, ws in by_unit.items():
        if u <= unit:
            a |= ws
    return a


def lint_dialogues(data_dir, schema_dir, by_unit, fw, rep, assets):
    validator = load_schema(schema_dir, "dialogue.schema.json")
    files = sorted((data_dir / "dialogue").glob("*.json"))
    for f in files:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            rep.error(f.name, f"invalid JSON: {e}")
            continue
        schema_errors(validator, doc, f.name, rep)
        if not isinstance(doc, dict) or not isinstance(doc.get("unit"), int):
            continue
        allowed = allowed_for(doc["unit"], by_unit, fw, doc.get("names", []) + [doc.get("npc", "")])
        ids = set()
        for i, line in enumerate(doc.get("lines", [])):
            if not isinstance(line, dict):
                continue
            where = f"{f.name}:lines[{i}]" + (f"({line.get('id')})" if line.get("id") else "")
            if line.get("id") in ids:
                rep.error(where, f"duplicate line id '{line['id']}'")
            ids.add(line.get("id"))
            if isinstance(line.get("en"), str):
                check_sentence(where, line["en"], line.get("ko", ""), allowed, rep)
            assets.append((where, line.get("audio", "")))
    return len(files)


def lint_quests(data_dir, schema_dir, by_unit, fw, rep):
    validator = load_schema(schema_dir, "quest.schema.json")
    files = sorted((data_dir / "quest").glob("*.json"))
    for f in files:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            rep.error(f.name, f"invalid JSON: {e}")
            continue
        schema_errors(validator, doc, f.name, rep)
        if not isinstance(doc, dict) or not isinstance(doc.get("unit"), int):
            continue
        allowed = allowed_for(doc["unit"], by_unit, fw, doc.get("names", []))
        title = doc.get("title", {})
        if isinstance(title, dict) and isinstance(title.get("en"), str):
            check_sentence(f"{f.name}:title", title["en"], title.get("ko", ""), allowed, rep)
        for r, role in enumerate(doc.get("roles", [])):
            if not isinstance(role, dict):
                continue
            goal = role.get("goal", {})
            if isinstance(goal, dict) and isinstance(goal.get("en"), str):
                check_sentence(f"{f.name}:roles[{r}].goal", goal["en"], goal.get("ko", ""), allowed, rep)
            for k, ph in enumerate(role.get("phrases", [])):
                if isinstance(ph, dict) and isinstance(ph.get("en"), str):
                    check_sentence(f"{f.name}:roles[{r}].phrases[{k}]", ph["en"], ph.get("ko", ""), allowed, rep)
    return len(files)


def check_assets(assets, root: Path, strict: bool, verbose: bool, rep: Report):
    missing: dict[str, list[str]] = {}
    for where, path in assets:
        src = where.split(":")[0]
        if not path:
            missing.setdefault(src, []).append(f"{where}: (no path set)")
        elif not (root / path).exists():
            missing.setdefault(src, []).append(f"{where}: {path}")
    for src, items in missing.items():
        add = rep.error if strict else rep.warn
        if verbose or len(items) <= 2:
            for it in items:
                add(it.split(": ", 1)[0], f"asset missing -> {it.split(': ', 1)[1]}")
        else:
            add(src, f"{len(items)} referenced assets missing/unset (use -v to list)")


def main():
    here = Path(__file__).resolve().parent.parent
    utf8_output()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", default=str(here / "data"))
    p.add_argument("--schema-dir", default=str(here / "data" / "schema"))
    p.add_argument("--root", default=str(here), help="base for asset paths")
    p.add_argument("--strict", action="store_true", help="missing assets are errors")
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args()
    data_dir, schema_dir, root = Path(a.data_dir), Path(a.schema_dir), Path(a.root)

    rep = Report()
    by_unit, assets, n_vocab = load_vocab(data_dir, schema_dir, rep)
    fw = load_function_words(data_dir)
    if not by_unit:
        rep.error("vocab", f"no vocabulary rows found under {data_dir / 'vocab'}")
    n_dlg = lint_dialogues(data_dir, schema_dir, by_unit, fw, rep, assets)
    n_q = lint_quests(data_dir, schema_dir, by_unit, fw, rep)
    check_assets(assets, root, a.strict, a.verbose, rep)

    for level, where, msg in rep.items:
        print(f"{level:<5} {where}: {msg}")
    total_words = sum(len(v) for v in by_unit.values())
    print(f"\n{n_vocab} vocab file(s) ({total_words} words), {n_dlg} dialogue(s), {n_q} quest(s): "
          f"{rep.errors} error(s), {rep.warnings} warning(s)")
    sys.exit(1 if rep.errors else 0)


if __name__ == "__main__":
    main()
