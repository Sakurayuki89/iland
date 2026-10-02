#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown", "pillow"]
# ///
"""Build the dependency-free GitHub Pages reference site.

Run with: uv run tools/site_build.py
"""
from __future__ import annotations

import csv
import html
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import markdown
from PIL import Image

from _common import utf8_output

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site"
ASSETS = ROOT / "assets"
DOCS = ROOT / "docs"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def page(title: str, body: str, depth: int = 0) -> str:
    root = "../" * depth
    nav = (
        f'<a href="{root}index.html">섬 지도</a><a href="{root}assets.html">에셋</a>'
        f'<a href="{root}world.html">세계 도감</a><a href="{root}docs/DEVLOG.html">개발 일지</a>'
        f'<a href="{root}docs/index.html">문서</a>'
    )
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Island 영어 학습 게임의 세계와 에셋 자료실">
<title>{esc(title)} · Island</title><link rel="stylesheet" href="{root}style.css"></head>
<body><header><a class="brand" href="{root}index.html">Island <small>worldbook</small></a><nav>{nav}</nav></header>
<main>{body}</main><footer>Island · 정적 세계 자료실 · <a href="{root}llms.txt">llms.txt</a></footer>
<script src="{root}app.js"></script></body></html>"""


def atlas_for(png: Path) -> dict | None:
    atlas_file = png.with_suffix(".json")
    if not atlas_file.exists():
        return None
    try:
        atlas = read_json(atlas_file)
        anim_file = png.with_suffix(".anims.json")
        anims = read_json(anim_file).get("anims", []) if anim_file.exists() else []
        frames = atlas.get("frames", {})
        return {
            "image": f"assets/{png.relative_to(ASSETS).as_posix()}",
            "frames": [{"name": name, **data} for name, data in frames.items()],
            "anims": anims,
        }
    except (OSError, ValueError, KeyError):
        return None


def collect_assets() -> list[dict]:
    manifest = read_json(ASSETS / "env/manifest.json")
    by_file = {entry["file"]: (entry.get("world"), entry.get("origin")) for entry in manifest.values()}
    records = []
    for png in sorted(ASSETS.rglob("*.png")):
        rel = png.relative_to(ASSETS).as_posix()
        if png.name.endswith("_contact.png") or rel == "env/_contact.png":
            continue
        with Image.open(png) as image:
            size = list(image.size)
        world, origin = by_file.get(rel, (None, None))
        records.append({
            "id": png.relative_to(ASSETS).with_suffix("").as_posix(),
            "category": png.parent.relative_to(ASSETS).as_posix() or "root",
            "path": f"assets/{rel}",
            "px": size,
            "world": world,
            "origin": origin,
            "atlas": atlas_for(png),
        })
    return records


def read_vocab() -> list[dict]:
    rows: list[dict] = []
    for path in sorted((ROOT / "data/vocab").glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                for key, value in row.items():
                    if value and value.startswith("assets/") and not (OUT / value).exists() and not (ROOT / value).exists():
                        row[key] = ""
                rows.append(row)
    return rows


def icon(item: dict, cls: str = "tiny-icon") -> str:
    return f'<img class="{cls}" src="{esc(item["icon"])}" alt="{esc(item["name_ko"])}">'


def docs_nav(markdown_files: list[Path], root: str = "../") -> str:
    links = "".join(
        f'<li><a href="{root}docs/{esc(item.stem)}.html"><code>{esc(item.name)}</code></a></li>'
        for item in markdown_files
    )
    return f"<ul class=\"doc-list\">{links}</ul>"


def build_index(zones: list[dict], species: list[dict], npcs: list[dict]) -> str:
    species_by_id = {item["id"]: item for item in species}
    npcs_by_id = {item["id"]: item for item in npcs}
    first = next(zone for zone in zones if zone["name_en"] == "Camp")
    def detail(zone: dict) -> str:
        creatures = [species_by_id[item] for item in zone["insects"] + zone["fish"]]
        people = [npcs_by_id[item] for item in zone["npcs"]]
        creature_html = "".join(icon(item) for item in creatures) or "<span>아직 없음</span>"
        people_html = "".join(f"<span>{esc(item['name_ko'])}</span>" for item in people) or "<span>없음</span>"
        return (
            f'<h2>{esc(zone["name_ko"])} <small>{esc(zone["name_en"])}</small></h2>'
            f'<p>{esc(zone["summary_ko"])}</p><p><b>활동</b> <code>{esc(", ".join(zone["activities"]))}</code></p>'
            f'<div class="zone-creatures">{creature_html}</div><p><b>주민</b> {people_html}</p>'
        )
    cells = "".join(
        f'<button class="zone-cell{" later" if zone["status"] == "later" else ""}{" selected" if zone["id"] == first["id"] else ""}" '
        f'data-zone="{esc(zone["id"])}" aria-label="{esc(zone["name_ko"])}" '
        f'aria-pressed="{"true" if zone["id"] == first["id"] else "false"}">{esc(zone["name_ko"])}</button>'
        for zone in zones
    )
    details = "".join(
        f'<article class="zone-detail{" active" if zone["id"] == first["id"] else ""}" id="zone-{esc(zone["id"])}">{detail(zone)}</article>'
        for zone in zones
    )
    showcase_dir = DOCS / "img/showcase"
    showcase = []
    captions = {
        "inventory": "인벤토리·도감 화면 (목업)",
        "catch_fx": "포획 이펙트",
        "night": "밤 풍경",
        "rain": "비 오는 날 캠프",
        "previs": "게임 시연 영상 — 게이지 바로 3번 놓치고 4번째에 나비가 도망 (Blender)",
        "gear_rewards": "장비 3단계(장갑·신발·채집망)와 보상 아이콘 (Grok)",
    }
    if showcase_dir.is_dir():
        media_files = [path for path in showcase_dir.iterdir() if path.is_file()]
        has_video = any(path.suffix.lower() == ".mp4" for path in media_files)
        image_order = {"catch_fx": 0, "gear_rewards": 1, "inventory": 2, "night": 3, "rain": 4}
        def showcase_sort_key(media: Path) -> tuple[int, int | str, str]:
            if media.suffix.lower() == ".mp4":
                return (0, 0, media.name.lower())
            if media.stem in image_order:
                return (1, image_order[media.stem], media.name.lower())
            return (2, media.name.lower(), media.name.lower())

        for media in sorted(media_files, key=showcase_sort_key):
            suffix, stem = media.suffix.lower(), media.stem
            if has_video and (stem.endswith("_poster") or stem.endswith(("_day", "_night"))):
                continue
            caption = captions.get(stem, stem)
            if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
                showcase.append(f'<figure class="showcase-tile"><a href="img/showcase/{esc(media.name)}" target="_blank" rel="noopener"><img loading="lazy" src="img/showcase/{esc(media.name)}" alt="{esc(caption)}"></a><figcaption>{esc(caption)}</figcaption></figure>')
            elif suffix == ".mp4":
                poster_file = showcase_dir / f"{stem}_poster.jpg"
                poster = f"img/showcase/{poster_file.name}" if poster_file.exists() else "img/island_overview.png"
                showcase.append(f'<figure class="showcase-video"><video controls preload="metadata" poster="{poster}"><source src="img/showcase/{esc(media.name)}" type="video/mp4"></video><figcaption>{esc(caption)}</figcaption></figure>')
    showcase_html = "".join(showcase) or "<p>쇼케이스 자료가 준비되면 이곳에 자동으로 나타납니다.</p>"
    return page("섬 지도", f"""
<section class="hero"><div><p class="eyebrow">영어로 함께 탐험하는 작은 섬</p><h1>Island</h1>
<p>고양이 친구들과 곤충을 잡고, 꽃을 가꾸고, 물고기를 낚으며 영어를 자연스럽게 쓰는 협동 학습 게임입니다.</p>
<a class="button" href="#map">지도 둘러보기</a></div><img src="img/island_overview.png" alt="Island 4x4 섬 지도"></section>
<section id="map"><h2>16개 구역 지도</h2><p>지도의 구역을 누르면 그곳에서 할 수 있는 일을 볼 수 있어요.</p>
<div class="map-layout"><div class="zone-map"><img src="img/island_overview.png" alt="" aria-hidden="true"><div class="zone-grid">{cells}</div></div>
<aside class="zone-panel">{details}</aside></div></section>
<section><h2>크기와 움직임</h2><div class="facts"><div><b>타일</b>48 px</div><div><b>고양이</b>약 92 px</div><div><b>화면</b>960 × 540</div><div><b>섬</b>3840 × 2160</div><div><b>이동</b>140 px/s</div><div><b>가로 횡단</b>약 27초</div></div></section>
<section><h2>쇼케이스</h2><div class="showcase">{showcase_html}</div></section>""")


def asset_card(asset: dict) -> str:
    atlas = asset["atlas"]
    preview = (
        f'<canvas class="atlas-canvas" width="180" height="140" data-atlas="{esc(json.dumps(atlas, ensure_ascii=False))}"></canvas>'
        if atlas else f'<img loading="lazy" src="{esc(asset["path"])}" alt="{esc(asset["id"])}">'
    )
    select = ""
    if atlas and atlas["anims"]:
        options = "".join(f'<option value="{esc(anim["key"])}">{esc(anim["key"])}</option>' for anim in atlas["anims"])
        select = f'<label>동작 <select class="anim-select">{options}</select></label>'
    world = f'{asset["world"][0]} × {asset["world"][1]} world px' if asset["world"] else ""
    return f"""<article class="asset-card" data-search="{esc((asset["id"] + " " + asset["path"] + " " + asset["category"]).lower())}" data-category="{esc(asset["category"])}">
<div class="asset-image">{preview}</div><div class="asset-info"><code>{esc(asset["id"])}</code><small>{asset["px"][0]} × {asset["px"][1]} px {esc(world)}</small>{select}
<button class="copy-path" data-path="{esc(asset["path"])}">경로 복사</button></div></article>"""


def build_assets(assets: list[dict]) -> str:
    categories = sorted({item["category"] for item in assets})
    chips = '<button class="chip active" data-filter="">전체</button>' + "".join(
        f'<button class="chip" data-filter="{esc(category)}">{esc(category)}</button>' for category in categories
    )
    review = [path.relative_to(ASSETS).as_posix() for path in ASSETS.rglob("*_contact.png")]
    review_links = " · ".join(f'<a href="assets/{esc(path)}"><code>{esc(path)}</code></a>' for path in review)
    return page("에셋 카탈로그", f"""
<section class="page-intro"><p class="eyebrow">asset catalog</p><h1>에셋 카탈로그</h1><p>투명 배경은 체크무늬로 표시됩니다. 스프라이트는 동작을 선택해 재생할 수 있어요.</p></section>
<div class="toolbar"><input id="asset-search" type="search" placeholder="id, 경로, 카테고리 검색" aria-label="에셋 검색"><div class="chips">{chips}</div></div>
<p class="review-sheets"><b>검토 시트:</b> {review_links}</p><div class="asset-grid">{"".join(asset_card(item) for item in assets)}</div>""")


def build_world(zones: list[dict], species: list[dict], npcs: list[dict]) -> str:
    zone_lookup = {zone["id"]: zone for zone in zones}
    zone_cards = "".join(
        f'<article class="zone-card"><h3>{esc(zone["name_ko"])} <small>{esc(zone["name_en"])}</small></h3><p>{esc(zone["summary_ko"])}</p><code>{esc(", ".join(zone["activities"]))}</code> <span class="status">{esc(zone["status"])}</span></article>'
        for zone in zones
    )
    species_cards = "".join(
        f'<article class="dex-card">{icon(item, "dex-icon")}<div><h3>{esc(item["name_ko"])} <small>{esc(item["name_en"])}</small></h3><p><b>{esc(item["word"])}</b> · {esc(item["time"])} · {"★" * item["rarity"]}</p><p>{esc(", ".join(zone_lookup[key]["name_ko"] for key in item["zones"]))}</p></div></article>'
        for item in species
    )
    npc_cards = "".join(
        f'<article class="npc-card"><img src="{esc(npc["portrait"])}" alt="{esc(npc["name_ko"])}"><div><h3>{esc(npc["name_ko"])} <small>{esc(npc["name_en"])}</small></h3><p>{esc(npc["role_ko"])}</p><code>{esc(", ".join(npc["topics"]))}</code><p>{esc(zone_lookup[npc["zone"]]["name_ko"])}</p></div></article>'
        for npc in npcs
    )
    return page("세계 도감", f"""
<section class="page-intro"><p class="eyebrow">world data</p><h1>세계 도감</h1><p>구역, 생물, 주민은 <code>data/world.json</code>에서 바로 읽을 수 있습니다.</p></section>
<section><h2>구역</h2><div class="zone-cards">{zone_cards}</div></section>
<section><h2>생물 도감</h2><div class="dex-grid">{species_cards}</div></section>
<section><h2>주민</h2><div class="npc-grid">{npc_cards}</div></section>
<section><h2>크기 비교</h2><img class="scale-chart" src="img/scale_chart.png" alt="고양이, 곤충, 환경 에셋 크기 비교표"></section>""")


def rewrite_doc_targets(source: str, names: set[str]) -> str:
    def markdown_target(match: re.Match) -> str:
        prefix, target = match.group(1), match.group(2)
        target = re.sub(r"^img/", "../img/", target)
        target = re.sub(
            r"^([A-Za-z0-9_-]+)\.md(?=($|#))",
            lambda item: f"{item.group(1)}.html" if item.group(1) + ".md" in names else item.group(0),
            target,
        )
        return prefix + target

    def html_target(match: re.Match) -> str:
        attribute, quote, target = match.groups()
        target = re.sub(r"^img/", "../img/", target)
        target = re.sub(
            r"^([A-Za-z0-9_-]+)\.md(?=($|#))",
            lambda item: f"{item.group(1)}.html" if item.group(1) + ".md" in names else item.group(0),
            target,
        )
        return f"{attribute}={quote}{target}{quote}"

    source = re.sub(r"(\]\(\s*)([^)\s]+)", markdown_target, source)
    return re.sub(r"\b(src|href)=(['\"])([^'\"]+)\2", html_target, source)


def doc_description(path: Path) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    title_seen = False
    paragraph: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not title_seen:
            title_seen = stripped.startswith("# ")
            continue
        if not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith(("#", "---", ">", "-", "|", "![")):
            if paragraph:
                break
            continue
        paragraph.append(stripped)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", " ".join(paragraph))
    text = re.sub(r"[\x60*_]", "", text)
    return (text[:117].rstrip() + "…") if len(text) > 120 else text


def markdown_page(path: Path, names: set[str]) -> str:
    source = rewrite_doc_targets(path.read_text(encoding="utf-8", errors="replace"), names)
    body = markdown.markdown(source, extensions=["tables", "fenced_code"])
    def responsive_table(match: re.Match) -> str:
        table = match.group(0)
        if path.name == "DEVLOG.md":
            header_match = re.search(
                r"<thead>\s*<tr>\s*<th>이전 기획</th>\s*<th>확정 기획</th>\s*</tr>\s*</thead>",
                table,
            )
            if header_match:
                table = table.replace(
                    "<table>",
                    '<table class="plan-compare"><colgroup><col><col></colgroup>',
                    1,
                )

                def label_cells(row: re.Match) -> str:
                    cells = re.sub(r"<td>", '<td data-label="이전 기획">', row.group(1), count=1)
                    cells = re.sub(r"<td>", '<td data-label="확정 기획">', cells, count=1)
                    return f"<tr>{cells}</tr>"

                return re.sub(r"<tr>(.*?)</tr>", label_cells, table, flags=re.DOTALL)
        if "<img" in table:
            return table.replace("<table>", '<table class="doc-image-table">', 1)
        return f'<div class="doc-table-wrap">{table}</div>'

    body = re.sub(r"<table>.*?</table>", responsive_table, body, flags=re.DOTALL)
    if path.name != "DEVLOG.md":
        return page(path.stem, f'<article class="document"><p class="eyebrow">documentation</p>{body}</article>', 1)

    def linked_image(match: re.Match) -> str:
        attrs = match.group(1)
        source_match = re.search(r'\bsrc="([^"]+)"', attrs)
        if not source_match:
            return match.group(0)
        image = match.group(0)
        return f'<a class="doc-image" href="{source_match.group(1)}" target="_blank" rel="noopener">{image}</a>'

    body = re.sub(r"<img\b([^>]*)>", linked_image, body)
    week_matches = list(re.finditer(r"<h2>(.*?)</h2>", body, flags=re.DOTALL))
    weeks: list[str] = []
    toc_weeks: list[str] = []
    before_weeks = body[:week_matches[0].start()] if week_matches else body
    for week_index, match in enumerate(week_matches, start=1):
        content_start = match.end()
        content_end = week_matches[week_index].start() if week_index < len(week_matches) else len(body)
        title, content = match.group(1), body[content_start:content_end]
        topic_links: list[str] = []

        def topic_heading(topic: re.Match) -> str:
            topic_index = len(topic_links) + 1
            topic_id = f"devlog-w{week_index}-{topic_index}"
            label = re.sub(r"<[^>]+>", "", topic.group(1))
            topic_links.append(f'<li><a href="#{topic_id}">{label}</a></li>')
            return f'<h3 id="{topic_id}">{topic.group(1)}</h3>'

        content = re.sub(r"<h3>(.*?)</h3>", topic_heading, content, flags=re.DOTALL)
        week_id = f"devlog-w{week_index}"
        label = re.sub(r"<[^>]+>", "", title)
        nested_topics = f'<ol>{"".join(topic_links)}</ol>' if topic_links else ""
        toc_weeks.append(f'<li><a href="#{week_id}">{label}</a>{nested_topics}</li>')
        open_attribute = " open" if week_index == 1 else ""
        weeks.append(
            f'<details class="devlog-week"{open_attribute}><summary>'
            f'<h2 id="{week_id}">{title}</h2></summary>{content}</details>'
        )

    toc_items = "".join(toc_weeks)
    toc = f'<aside class="devlog-toc"><p class="eyebrow">목차</p><ol>{toc_items}</ol></aside>'
    mobile_toc = f'<details class="mobile-doc-toc"><summary>목차</summary><ol>{toc_items}</ol></details>'
    body = before_weeks + "".join(weeks)
    return page(path.stem, f'<div class="devlog-layout">{mobile_toc}<article class="document devlog"><p class="eyebrow">development log</p>{body}</article>{toc}</div>', 1)


def integrity_check() -> None:
    bad: list[str] = []
    candidates: list[tuple[Path, str]] = []
    for path in OUT.rglob("*.html"):
        candidates += [(path, value) for value in re.findall(r'(?:src|href|poster)="([^"]+)"', path.read_text(encoding="utf-8"))]
    for name in ("data/world.json", "data/assets.json", "llms.txt"):
        path = OUT / name
        candidates += [(path, value) for value in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding="utf-8"))]
        if name.startswith("data/"):
            candidates += [(path, value) for value in re.findall(r'"(assets/[^"]+|img/[^"]+)"', path.read_text(encoding="utf-8"))]
    for owner, value in candidates:
        if value.startswith(("#", "http:", "https:", "mailto:", "data:")):
            continue
        path = unquote(urlparse(value).path)
        target = ((OUT / path) if path.startswith(("assets/", "img/", "data/")) else (owner.parent / path)).resolve()
        try:
            target.relative_to(OUT.resolve())
        except ValueError:
            bad.append(f"{owner.relative_to(OUT)} -> {value} (outside site)")
        else:
            if not target.exists():
                bad.append(f"{owner.relative_to(OUT)} -> {value}")
    if bad:
        raise RuntimeError("Broken site references:\n" + "\n".join(sorted(set(bad))))


STYLE = r"""
.zone-cell.selected { outline:3px solid var(--sun); outline-offset:-4px; background:#5a3a2877; }
.zone-detail.active { display:block !important; }
.zone-detail:first-child:not(.active) { display:none !important; }
.devlog-layout { display:grid; grid-template-columns:minmax(0,1fr) 230px; gap:24px; align-items:start; }
.devlog-layout .document { max-width:none; }
.devlog-layout > .document { width:100%; max-width:100%; }
.devlog-toc { position:sticky; top:20px; max-height:calc(100vh - 40px); overflow:auto; padding:16px; background:var(--card); border:2px solid var(--line); border-radius:18px; box-shadow:var(--shade); }
.devlog-toc ol { margin:0; padding-left:1.25em; }
.devlog-toc li { margin:.45em 0; font-size:.9rem; }
.document blockquote { margin:1.25em 0; padding:1em 1.15em; border:2px solid var(--line); border-radius:18px; background:color-mix(in srgb, var(--sun) 20%, var(--card)); position:relative; }
.document blockquote::before { content:"“"; position:absolute; left:.25em; top:-.25em; color:var(--sun); font:3rem/1 Georgia,serif; }
.document blockquote > :first-child { margin-top:0; }
.document blockquote > :last-child { margin-bottom:0; }
.document .doc-image { display:block; width:max-content; max-width:100%; }
.document .doc-image img { display:block; max-width:100%; height:auto; }
.devlog-week { min-width:0; max-width:100%; margin:1.25rem 0; border:2px solid var(--line); border-radius:16px; background:var(--card); overflow:hidden; }
.devlog-week > summary { display:block; cursor:pointer; padding:0 18px; }
.devlog-week > summary::marker,.devlog-week > summary::-webkit-details-marker { display:none; }
.devlog-week > summary::after { content:"+"; float:right; margin-top:-2.45rem; color:var(--grass); font-size:1.5rem; font-weight:800; }
.devlog-week[open] > summary::after { content:"−"; }
.devlog-week > summary h2 { margin:1rem 2rem 1rem 0; }
.devlog-week > :not(summary) { max-width:calc(100% - 36px); margin-left:18px; margin-right:18px; }
.devlog-week > :last-child { margin-bottom:18px; }
.devlog-toc ol ol { margin:.35em 0 .6em; padding-left:1.15em; }
.devlog-toc ol ol li { font-size:.88em; }
.document table.plan-compare { display:table; width:100% !important; min-width:0; max-width:100%; table-layout:fixed; }
.document .devlog-week > table, .document .devlog-week > table.plan-compare { width:calc(100% - 36px) !important; }  /* tables ignore max-width; account for the 18px side margins */
.plan-compare col { width:50%; }
.plan-compare th:first-child { background:color-mix(in srgb, var(--line) 40%, var(--card)); }
.plan-compare th:nth-child(2) { background:var(--grass); color:#fff; }
.plan-compare td { vertical-align:top; }
@media (max-width:680px) { .devlog-layout { grid-template-columns:1fr; } .devlog-toc { position:static; order:-1; max-height:none; } }
:root { --paper:#fff9e8; --ink:#5a3a28; --grass:#6d9f5c; --sky:#48b9bd; --sun:#f3bf59; --card:#fffdf4; --line:#d6b98b; --shade:0 8px 24px #5a3a2820; color-scheme:light dark; }
@media (prefers-color-scheme: dark) { :root { --paper:#1e2823; --ink:#f6e7c6; --grass:#9acb77; --sky:#6ed7d6; --sun:#ffd879; --card:#27352d; --line:#695b45; --shade:0 8px 24px #0007; } }
* { box-sizing:border-box } html,body { margin:0; overflow-x:hidden } body { background:var(--paper); color:var(--ink); font:16px/1.55 system-ui,-apple-system,"Malgun Gothic",sans-serif } a { color:inherit; text-underline-offset:3px } header,main,footer { max-width:1180px; margin:auto; padding-inline:20px } header { min-height:68px; display:flex; gap:22px; align-items:center; justify-content:space-between; border-bottom:2px solid var(--line) } .brand { font:800 1.5rem Georgia,serif; text-decoration:none } .brand small,.eyebrow { color:var(--grass); font:700 .75rem ui-monospace,monospace; letter-spacing:.09em; text-transform:uppercase } nav { display:flex; flex-wrap:wrap; gap:14px } nav a { font-weight:700; text-decoration:none } main { padding-block:36px 62px } footer { padding-block:24px; border-top:2px solid var(--line); font-size:.9rem } h1,h2,h3 { line-height:1.18 } h1 { font:800 clamp(2.6rem,8vw,5.5rem)/.95 Georgia,serif; margin:.15em 0 } h2 { margin-top:2.2rem } small,code { font-family:ui-monospace,SFMono-Regular,Consolas,monospace } small { font-size:.8em; opacity:.8 } code { font-size:.82em; overflow-wrap:anywhere } .hero { display:grid; grid-template-columns:1fr 1.1fr; align-items:center; gap:30px; min-height:410px } .hero>img { width:100%; border:3px solid var(--ink); border-radius:28px; box-shadow:var(--shade) } .button,.copy-path { display:inline-block; border:2px solid var(--ink); background:var(--sun); color:var(--ink); padding:.55em .9em; border-radius:999px; font-weight:800; text-decoration:none; cursor:pointer } section { margin-block:42px } .map-layout { display:grid; grid-template-columns:minmax(0,2fr) minmax(230px,1fr); gap:18px } .zone-map { position:relative; aspect-ratio:16/9; min-width:0; border:3px solid var(--ink); border-radius:18px; overflow:hidden } .zone-map>img { display:block; width:100%; height:100%; object-fit:cover } .zone-grid { position:absolute; inset:0; display:grid; grid-template:repeat(4,1fr)/repeat(4,1fr) } .zone-cell { color:white; background:#1d372033; border:1px solid #fff8; font-weight:800; text-shadow:0 1px 3px #000; cursor:pointer; padding:2px; font-size:clamp(.55rem,1.4vw,.92rem) } .zone-cell:hover,.zone-cell:focus,.zone-cell.later { background:#5a3a2866 } .zone-panel,.asset-card,.zone-card,.dex-card,.npc-card,.document { background:var(--card); border:2px solid var(--line); border-radius:18px; box-shadow:var(--shade) } .zone-panel { padding:18px } .zone-detail { display:none } .zone-detail:first-child { display:block } .zone-creatures { display:flex; gap:6px; min-height:36px; align-items:center; flex-wrap:wrap } .tiny-icon { width:34px; height:34px; object-fit:contain } .facts { display:grid; grid-template-columns:repeat(6,1fr); gap:9px } .facts div { background:var(--grass); color:white; border-radius:13px; padding:12px; text-align:center } .facts b { display:block; font-size:.82rem } .showcase { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:16px } figure { margin:0 } figure img,figure video { width:100%; border-radius:14px; background:#ddd } figcaption { font:italic .85rem ui-monospace,monospace } .toolbar { position:sticky; top:0; z-index:2; padding:12px 0; background:var(--paper) } input[type=search] { width:min(100%,520px); padding:.75em 1em; border:2px solid var(--ink); border-radius:999px; background:var(--card); color:var(--ink); font:inherit } .chips { display:flex; gap:7px; flex-wrap:wrap; margin-top:9px } .chip { border:1px solid var(--line); border-radius:999px; padding:.35em .65em; background:var(--card); color:var(--ink); cursor:pointer } .chip.active { background:var(--grass); color:#fff } .asset-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); gap:14px } .asset-card { overflow:hidden; min-width:0 } .asset-image { height:170px; display:grid; place-items:center; background:repeating-conic-gradient(#ddd 0 25%,#f7f7f7 0 50%) 50%/20px 20px } .asset-image img,.atlas-canvas { max-width:100%; max-height:100%; object-fit:contain } .atlas-canvas { width:180px; height:140px } .asset-info { padding:10px; display:grid; gap:7px } .asset-info label { font-size:.82rem } .review-sheets { font-size:.85rem; overflow-wrap:anywhere } .zone-cards,.npc-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px } .zone-card { padding:15px } .zone-card h3,.dex-card h3,.npc-card h3 { margin:0 0 .3em } .status { float:right; padding:.15em .5em; background:var(--sun); color:#3d281d; border-radius:99px; font-size:.78rem } .dex-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(255px,1fr)); gap:12px } .dex-card,.npc-card { padding:12px; display:flex; gap:12px; align-items:center } .dex-icon { width:70px; height:70px; object-fit:contain; flex:none } .npc-card img { width:88px; height:88px; border-radius:50%; object-fit:cover; background:#d8eac7 } .scale-chart { max-width:100%; border-radius:18px; border:2px solid var(--line) } .document { max-width:880px; margin:auto; padding:clamp(18px,4vw,48px) } .document img { max-width:100%; height:auto } .document pre { overflow:auto; padding:14px; background:#171d1a; color:#f5ead4; border-radius:12px } .document table { border-collapse:collapse; max-width:100%; overflow:auto; display:block } .document th,.document td { padding:7px; border:1px solid var(--line) }
@media (max-width:680px) { header { align-items:flex-start; flex-direction:column; padding-block:14px; gap:7px } main { padding-inline:14px } .hero,.map-layout { grid-template-columns:1fr } .hero { min-height:0 } .hero>img { order:-1 } .facts { grid-template-columns:repeat(2,1fr) } .zone-panel { min-height:210px } }

/* Documentation stays inside a narrow viewport; wide data remains locally scrollable. */
.mobile-doc-toc { display:none; }
.devlog-layout, .document { min-width:0; }
.document :is(h1,h2,h3,h4,h5,h6) { scroll-margin-top:20px; }
.document :is(p,li,td,th,blockquote,a,code) { overflow-wrap:anywhere; }
.document img, .document a.doc-image img, .document td img { display:block; max-width:100%; height:auto; }
.document pre { max-width:100%; overflow:auto; }
.document video { display:block; max-width:100%; height:auto; }
.doc-table-wrap { max-width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch; }
.document .doc-table-wrap table { display:table; max-width:none; }
.document table.doc-image-table { display:table; width:100%; max-width:100%; table-layout:fixed; }
.showcase-video { grid-column:1/-1; }
.showcase-video video { display:block; width:100%; aspect-ratio:16/9; object-fit:contain; }
.showcase-tile a { display:block; aspect-ratio:16/9; overflow:hidden; border-radius:14px; background:var(--card); }
.showcase-tile img { display:block; width:100%; height:100%; object-fit:contain; }
@media (max-width:680px) {
  body { font-size:16px; line-height:1.7; }
  header, main, footer { padding-inline:16px; }
  nav { width:100%; gap:0 10px; }
  nav a { display:inline-flex; align-items:center; min-height:40px; }
  .devlog-layout { grid-template-columns:minmax(0,1fr); gap:16px; }
  .devlog-toc { display:none; }
  .mobile-doc-toc { display:block; order:-1; padding:12px 16px; border:2px solid var(--line); border-radius:14px; background:var(--card); }
  .mobile-doc-toc summary { min-height:40px; display:flex; align-items:center; cursor:pointer; font-weight:800; }
  .mobile-doc-toc ol { margin:8px 0 0; padding-left:1.25em; }
  .document { padding:16px; }
  .document h1 { font-size:2rem; }
  .document h2 { font-size:1.3rem; }
  .document blockquote { border-width:0 0 0 4px; border-radius:0 12px 12px 0; padding:.9em 1em; }
  .document blockquote::before { display:none; }
  .document table.doc-image-table, .document table.doc-image-table thead,
  .document table.doc-image-table tbody, .document table.doc-image-table tr,
  .document table.doc-image-table th, .document table.doc-image-table td { display:block; width:100%; }
  .document table.doc-image-table :is(th,td) { padding:8px 0; border-width:0 0 1px; }
  .document table.plan-compare, .document table.plan-compare thead,
  .document table.plan-compare tbody, .document table.plan-compare tr,
  .document table.plan-compare th, .document table.plan-compare td { display:block; width:100%; }
  .document table.plan-compare { border:0; }
  .document .devlog-week > table.plan-compare { width:auto !important; }
  .document table.plan-compare thead { display:none; }
  .document table.plan-compare tbody { display:grid; gap:12px; }
  .document table.plan-compare tr { overflow:hidden; border:1px solid var(--line); border-radius:12px; background:var(--paper); }
  .document table.plan-compare td { padding:10px; border:0; }
  .document table.plan-compare td + td { border-top:1px solid var(--line); }
  .document table.plan-compare td::before { content:attr(data-label); display:block; margin-bottom:.35em; color:var(--grass); font-size:.78rem; font-weight:800; letter-spacing:.05em; }
  .document table.plan-compare td img { width:100%; }
}
"""


APP = r"""
const $ = (selector, root=document) => root.querySelector(selector);
function selectZone(button) {
  document.querySelectorAll('.zone-cell').forEach(item => {
    const selected = item === button;
    item.classList.toggle('selected', selected);
    item.setAttribute('aria-pressed', String(selected));
  });
  document.querySelectorAll('.zone-detail').forEach(detail => detail.classList.remove('active'));
  const detail = $('#zone-' + button.dataset.zone); if (detail) detail.classList.add('active');
}
document.querySelectorAll('.zone-cell').forEach(button => button.addEventListener('click', () => selectZone(button)));
let category = '';
const filterAssets = () => {
  const term = ($('#asset-search')?.value || '').toLowerCase();
  document.querySelectorAll('.asset-card').forEach(card => card.hidden = !!((category && card.dataset.category !== category) || (term && !card.dataset.search.includes(term))));
};
$('#asset-search')?.addEventListener('input', filterAssets);
document.querySelectorAll('.chip').forEach(chip => chip.addEventListener('click', () => { category = chip.dataset.filter; document.querySelectorAll('.chip').forEach(item => item.classList.toggle('active', item === chip)); filterAssets(); }));
document.querySelectorAll('.copy-path').forEach(button => button.addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(button.dataset.path); button.textContent = '복사됨'; setTimeout(() => button.textContent = '경로 복사', 1200); } catch { button.textContent = button.dataset.path; }
}));
function animate(canvas, data, key) {
  const anim = data.anims.find(item => item.key === key) || data.anims[0]; if (!anim) return;
  const image = new Image(), frames = Object.fromEntries(data.frames.map(item => [item.name, item]));
  let index = 0, last = 0; image.src = data.image;
  const draw = now => { requestAnimationFrame(draw); if (now-last < 1000/(anim.frameRate || 8)) return; last=now;
    const frameRef = anim.frames[index++ % anim.frames.length].frame, item = frames[frameRef], frame = item?.frame; if (!frame) return;
    const ctx = canvas.getContext('2d'), scale = Math.min(canvas.width/item.sourceSize.w, canvas.height/item.sourceSize.h)*.85;
    ctx.clearRect(0,0,canvas.width,canvas.height); ctx.save(); ctx.translate(canvas.width/2,canvas.height*.85); if(anim.flipX) ctx.scale(-1,1);
    ctx.drawImage(image,frame.x,frame.y,frame.w,frame.h,(item.spriteSourceSize.x-item.sourceSize.w/2)*scale,(item.spriteSourceSize.y-item.sourceSize.h)*scale,frame.w*scale,frame.h*scale); ctx.restore();
  }; image.onload = () => requestAnimationFrame(draw);
}
document.querySelectorAll('.atlas-canvas').forEach(canvas => {
  const data = JSON.parse(canvas.dataset.atlas), select = $('.anim-select', canvas.closest('.asset-card'));
  animate(canvas,data,select?.value); select?.addEventListener('change', () => animate(canvas,data,select.value));
});
function openDevlogTarget(hash = location.hash) {
  const id = hash.startsWith('#') ? hash.slice(1) : '';
  if (!id) return;
  let target;
  try { target = document.getElementById(decodeURIComponent(id)); } catch { return; }
  target?.closest('details.devlog-week')?.setAttribute('open', '');
}
document.addEventListener('click', event => {
  const link = event.target.closest('a[href^="#"]');
  if (link) openDevlogTarget(link.getAttribute('href'));
});
window.addEventListener('hashchange', () => openDevlogTarget());
openDevlogTarget();
"""


def main() -> int:
    utf8_output()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    zones = read_json(ROOT / "data/world/zones.json")
    species = read_json(ROOT / "data/world/species.json")
    npcs = read_json(ROOT / "data/world/npcs.json")
    assets = collect_assets()
    vocab = read_vocab()
    world = {"scale": {"tile": 48, "cat_height": 92, "screen": [960, 540], "world": [3840, 2160], "walk_px_s": 140, "stored_scale": 2}, "zones": zones, "species": species, "npcs": npcs, "vocab": vocab}
    shutil.copytree(ASSETS, OUT / "assets")
    if (DOCS / "img").is_dir():
        shutil.copytree(DOCS / "img", OUT / "img")
    write(OUT / "style.css", STYLE)
    write(OUT / "app.js", APP)
    write(OUT / "data/assets.json", json.dumps(assets, ensure_ascii=False, indent=2))
    write(OUT / "data/world.json", json.dumps(world, ensure_ascii=False, indent=2))
    write(OUT / "index.html", build_index(zones, species, npcs))
    write(OUT / "assets.html", build_assets(assets))
    write(OUT / "world.html", build_world(zones, species, npcs))
    markdown_files = sorted(DOCS.glob("*.md"), key=lambda path: (path.name != "DEVLOG.md", path.name))
    names = {item.name for item in markdown_files}
    write(OUT / "docs/index.html", page("문서", f'<section class="page-intro"><p class="eyebrow">documentation</p><h1>프로젝트 문서</h1>{docs_nav(markdown_files)}</section>', 1))
    for source in markdown_files:
        write(OUT / "docs" / f"{source.stem}.html", markdown_page(source, names))
    doc_links = "\n".join(
        f"- [{item.stem}](docs/{item.stem}.html): {doc_description(item)}" for item in markdown_files
    )
    llms = f"""# Island
> 고양이 친구들과 함께 탐험하며 영어를 배우는 초등 학습 게임의 공개 세계 자료실.

## Data
- [World data](data/world.json): 구역, 생물, 주민, 어휘와 스케일 데이터
- [Asset catalog data](data/assets.json): 이미지 에셋의 경로와 크기, 아틀라스 정보

## Docs
{doc_links}

## Pages
- [Island map](index.html): 4x4 섬 지도와 구역 안내
- [Assets](assets.html): 검색 가능한 에셋 카탈로그
- [World book](world.html): 구역, 생물, 주민 도감
"""
    write(OUT / "llms.txt", llms)
    full_docs = "\n\n".join(f"# {item.name}\n\n{item.read_text(encoding='utf-8', errors='replace')}" for item in markdown_files)
    write(OUT / "llms-full.txt", f"# Island full reference\n\n{full_docs}\n\n# world.json\n\n{json.dumps(world, ensure_ascii=False, indent=2)}\n")
    integrity_check()
    total = sum(path.stat().st_size for path in OUT.rglob("*") if path.is_file())
    print(f"site: {len(assets)} assets, {4 + len(markdown_files)} pages, {total / 1024 / 1024:.1f} MiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
