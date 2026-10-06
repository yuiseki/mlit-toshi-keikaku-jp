#!/usr/bin/env python3
"""Fetch the national edition of MLIT's 都市計画決定GISデータ (urban planning decision GIS data).

The Ministry of Land, Infrastructure, Transport and Tourism (MLIT), City
Bureau, publishes the data on
https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000087.html : that page
states the edition (データ作成年度), the update history, the terms of use,
and links the data definition (PDF), the CityGML specification (PDF) and the
list of municipalities and layers (xlsx). Its "ダウンロードページへ" button
(enabled once the terms are ticked) leads to a second page whose table gives,
per prefecture, one zip per format: Shapefile, CityGML and GeoJSON. This
script reads both pages and fetches every one of those files: 3 documents and
47 x 3 zips. The two pages themselves are kept too (pages/), as the record of
the terms and the links at fetch time.

The pages hold one edition only, and a correction replaces a zip in place
(the table notes "（R8.7.1修正）" beside it; the URL may stay the same). So the
version is the edition the pages state, "令和7年度" giving fy2025, and within
it the files follow the source: --refresh asks the server for each listed
file's Content-Length and Last-Modified and fetches again whatever differs
from the manifest. A new edition lands in a new directory.

Files go to data/raw/<edition>/ as docs/<served name>, pages/<page>.html and
<format>/<JIS prefecture code>_<prefecture>.zip. data/raw/<edition>/MANIFEST.json
records for each its URL, size, sha256, Last-Modified, fetch time, the page's
label and correction note, and what the source states: the edition, the
update history, the terms, and, from the xlsx, how many municipalities have
each layer. It is written after every file, so an interrupted run resumes; a
file whose manifest entry has the same URL and whose sha256 still matches is
not fetched again.

    uv run python scripts/01_download.py                 # everything (about 2.0 GB)
    uv run python scripts/01_download.py --only shp 31   # Shapefile zip of Tottori
    uv run python scripts/01_download.py --only docs --limit 2
    uv run python scripts/01_download.py --dry-run       # print the estimate only
    uv run python scripts/01_download.py --refresh       # follow corrections upstream
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
LANDING_URL = "https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000087.html"
UA = "mlit-toshi-keikaku-jp/1 (+https://github.com/yuiseki/mlit-toshi-keikaku-jp)"
DELAY = 1.0
LICENCE = (
    "公共データ利用規約（第1.0版） (PDL1.0), compatible with CC BY 4.0; "
    "MLIT site terms https://www.mlit.go.jp/link.html"
)

FORMATS = {"シェープファイル形式": "shp", "CityGML形式": "citygml", "GeoJSON形式": "geojson"}

# JIS X 0401 code -> (name on the page, slug used in file names)
PREFECTURES = {
    "01": ("北海道", "hokkaido"), "02": ("青森県", "aomori"), "03": ("岩手県", "iwate"),
    "04": ("宮城県", "miyagi"), "05": ("秋田県", "akita"), "06": ("山形県", "yamagata"),
    "07": ("福島県", "fukushima"), "08": ("茨城県", "ibaraki"), "09": ("栃木県", "tochigi"),
    "10": ("群馬県", "gunma"), "11": ("埼玉県", "saitama"), "12": ("千葉県", "chiba"),
    "13": ("東京都", "tokyo"), "14": ("神奈川県", "kanagawa"), "15": ("新潟県", "niigata"),
    "16": ("富山県", "toyama"), "17": ("石川県", "ishikawa"), "18": ("福井県", "fukui"),
    "19": ("山梨県", "yamanashi"), "20": ("長野県", "nagano"), "21": ("岐阜県", "gifu"),
    "22": ("静岡県", "shizuoka"), "23": ("愛知県", "aichi"), "24": ("三重県", "mie"),
    "25": ("滋賀県", "shiga"), "26": ("京都府", "kyoto"), "27": ("大阪府", "osaka"),
    "28": ("兵庫県", "hyogo"), "29": ("奈良県", "nara"), "30": ("和歌山県", "wakayama"),
    "31": ("鳥取県", "tottori"), "32": ("島根県", "shimane"), "33": ("岡山県", "okayama"),
    "34": ("広島県", "hiroshima"), "35": ("山口県", "yamaguchi"), "36": ("徳島県", "tokushima"),
    "37": ("香川県", "kagawa"), "38": ("愛媛県", "ehime"), "39": ("高知県", "kochi"),
    "40": ("福岡県", "fukuoka"), "41": ("佐賀県", "saga"), "42": ("長崎県", "nagasaki"),
    "43": ("熊本県", "kumamoto"), "44": ("大分県", "oita"), "45": ("宮崎県", "miyazaki"),
    "46": ("鹿児島県", "kagoshima"), "47": ("沖縄県", "okinawa"),
}  # fmt: skip
PREF_CODE = {name: code for code, (name, _) in PREFECTURES.items()}

_last_request = 0.0


# ---------------------------------------------------------------- page parsing


def _squash(text: str) -> str:
    """Collapse the markup's line breaks and indentation; keep full-width spaces as written."""
    return re.sub(r"[ \t\r\n\xa0]+", " ", text).strip(" ")


class _Tables(HTMLParser):
    """Every <tr> of every table as a list of cells {lines, links}; also onclick targets."""

    def __init__(self, base: str):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.rows: list[list[dict]] = []
        self.cell: dict | None = None
        self.href: str | None = None
        self.atext: list[str] = []
        self.onclick: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("onclick"):
            mt = re.search(r"location\.href\s*=\s*'([^']+)'", a["onclick"])
            if mt:
                self.onclick.append(urllib.parse.urljoin(self.base, mt.group(1)))
        if tag == "tr":
            self.rows.append([])
        elif tag in ("td", "th") and self.rows:
            self.cell = {"lines": [""], "links": []}
            self.rows[-1].append(self.cell)
        elif tag == "br" and self.cell is not None:
            self.cell["lines"].append("")
        elif tag == "a" and self.cell is not None and a.get("href"):
            self.href = urllib.parse.urljoin(self.base, a["href"])
            self.atext = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.cell["lines"] = [_squash(t) for t in self.cell["lines"]]
            self.cell["lines"] = [t for t in self.cell["lines"] if t]
            self.cell = None
        elif tag == "a" and self.href is not None:
            self.cell["links"].append((self.href, _squash("".join(self.atext))))
            self.href = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["lines"][-1] += data
        if self.href is not None:
            self.atext.append(data)


def _tables(html: str, base: str) -> _Tables:
    p = _Tables(base)
    p.feed(html)
    return p


def parse_landing(html: str, base: str) -> dict:
    """The landing page's two-column table, its documents and the download page link."""
    p = _tables(html, base)
    fields = {}
    for row in p.rows:
        if len(row) == 2 and row[0]["lines"]:
            fields[row[0]["lines"][0]] = row[1]
    docs = []
    for key in ("シェープファイル・GeoJSON形式", "CityGML形式", "公表自治体及び掲載データ一覧"):
        if key not in fields or not fields[key]["links"]:
            raise ValueError(f"the landing page has no link for {key}")
        docs += fields[key]["links"]
    pages = [u for u in p.onclick if u.endswith(".html")]
    if len(pages) != 1:
        raise ValueError(f"expected one download page link, found {pages}")
    return {
        "download_page": pages[0],
        "fiscal_year": fields["データ作成年度"]["lines"][0],
        "update_history": fields["更新履歴"]["lines"],
        "content": fields["内容"]["lines"],
        "original_sources": fields["原典資料"]["lines"],
        "method": fields["作成方法"]["lines"],
        "listing_as_of": [
            t for t in fields["公表自治体及び掲載データ一覧"]["lines"] if "時点" in t
        ],
        "terms": [t.removeprefix("・") for t in fields["このデータの使用許諾条件"]["lines"]],
        "documents": docs,
    }


def parse_download_table(html: str, base: str) -> tuple[str, list[dict]]:
    """(fiscal year stated above the table, one row per prefecture and format)."""
    mt = re.search(r"データ作成年度：\s*([^<\s]+)", html)
    if not mt:
        raise ValueError("the download page states no データ作成年度")
    p = _tables(html, base)
    header = None
    out = []
    for row in p.rows:
        texts = [" ".join(c["lines"]) for c in row]
        if texts and texts[0].startswith("都道府県"):
            header = [FORMATS.get(t.replace("　", "").strip()) for t in texts[1:]]
            if None in header:
                raise ValueError(f"unknown format column in {texts}")
            continue
        if header is None or not texts:
            continue
        pref = texts[0].strip()
        if pref not in PREF_CODE:
            raise ValueError(f"unknown prefecture {pref!r}")
        if len(row) - 1 != len(header):
            raise ValueError(f"{pref}: {len(row) - 1} cells, header has {len(header)}")
        for fmt, cell in zip(header, row[1:], strict=True):
            if len(cell["links"]) != 1:
                raise ValueError(f"{pref} {fmt}: {len(cell['links'])} links")
            note = "".join(t for t in cell["lines"] if t != "ダウンロード")
            out.append(
                {
                    "pref_code": PREF_CODE[pref],
                    "pref": pref,
                    "format": fmt,
                    "url": cell["links"][0][0],
                    "note": note,
                }
            )
    return mt.group(1), out


def edition(fiscal_year: str) -> str:
    """'令和７年度' -> 'fy2025' (Reiwa 1 = 2019)."""
    mt = re.fullmatch(r"令和(\d+)年度", unicodedata.normalize("NFKC", fiscal_year).strip())
    if not mt:
        raise ValueError(f"cannot read the fiscal year {fiscal_year!r}")
    return f"fy{2018 + int(mt.group(1))}"


def make_plan(info: dict, rows: list[dict]) -> list[dict]:
    plan = []
    for url, label in info["documents"]:
        name = Path(urllib.parse.urlparse(url).path).name
        plan.append({"path": f"docs/{name}", "url": url, "label": label, "kind": "docs"})
    for r in rows:
        slug = PREFECTURES[r["pref_code"]][1]
        plan.append(
            {
                "path": f"{r['format']}/{r['pref_code']}_{slug}.zip",
                "url": r["url"],
                "label": r["pref"],
                "note": r["note"],
                "kind": r["format"],
                "pref_code": r["pref_code"],
            }
        )
    paths = [p["path"] for p in plan]
    if len(paths) != len(set(paths)):
        raise ValueError("two files map to one path")
    return plan


def select(plan: list[dict], only: list[str] | None, limit: int | None) -> list[dict]:
    """--only takes kinds (docs, shp, citygml, geojson) and/or prefecture codes.

    The documents are taken when docs is named. A zip is taken when a format or
    a prefecture is named, and it matches every format and prefecture given.
    """
    out = plan
    if only:
        kinds = {o for o in only if o in ("docs", *FORMATS.values())}
        prefs = {o.zfill(2) for o in only if o.isdigit()}
        bad = set(only) - kinds - {o for o in only if o.isdigit()}
        if bad or prefs - set(PREFECTURES):
            raise SystemExit(f"--only takes docs, shp, citygml, geojson or 01..47, not {only}")
        fmts = kinds - {"docs"}
        out = [
            p
            for p in out
            if (p["kind"] == "docs" and "docs" in kinds)
            or (
                p["kind"] != "docs"
                and (fmts or prefs)
                and (not fmts or p["kind"] in fmts)
                and (not prefs or p["pref_code"] in prefs)
            )
        ]
    return out[:limit] if limit else out


# ---------------------------------------------------------------- the xlsx listing

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _sheet_rows(data: bytes) -> list[list[str]]:
    with zipfile.ZipFile(BytesIO(data)) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(f"{_NS}t")) for si in root]
        root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in root.iter(f"{_NS}row"):
        cells: dict[int, str] = {}
        for c in row.iter(f"{_NS}c"):
            col = 0
            for ch in re.match(r"[A-Z]+", c.get("r")).group(0):
                col = col * 26 + ord(ch) - 64
            if c.get("t") == "inlineStr":
                v = "".join(t.text or "" for t in c.iter(f"{_NS}t"))
            else:
                e = c.find(f"{_NS}v")
                v = "" if e is None else (shared[int(e.text)] if c.get("t") == "s" else e.text)
            cells[col - 1] = v
        rows.append([cells.get(i, "") for i in range(max(cells, default=-1) + 1)])
    return rows


def parse_listing(data: bytes) -> dict:
    """Per layer, how many municipalities the list marks 〇 (data), × (none) or － (no decision)."""
    rows = _sheet_rows(data)
    hi = next(i for i, r in enumerate(rows) if len(r) > 1 and r[1] == "団体コード")
    header = rows[hi]
    first = header.index("都市計画区域")
    last = header.index("データ作成年")
    layers = header[first:last]
    counts: dict[str, dict[str, int]] = {name: {} for name in layers}
    by_city = {}
    for r in rows[hi + 1 :]:
        r = r + [""] * (len(header) - len(r))
        if len(r) < 4 or not r[3]:  # prefecture rows have no municipality name
            continue
        marks = dict(zip(layers, r[first:last], strict=True))
        by_city[r[1][:5]] = marks
        for name, m in marks.items():
            counts[name][m] = counts[name].get(m, 0) + 1
    return {"municipalities": len(by_city), "layers": counts, "by_city": by_city}


# ---------------------------------------------------------------- HTTP


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def up_to_date(path: Path, entry: dict | None, url: str) -> bool:
    return bool(entry) and entry["url"] == url and path.exists() and sha256(path) == entry["sha256"]


def _open(url: str, method: str = "GET"):
    """One request at least DELAY after the previous; backs off on 429 and 503."""
    global _last_request
    for attempt in range(6):
        wait = DELAY - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": UA}, method=method)
        try:
            r = urllib.request.urlopen(req, timeout=300)
            _last_request = time.monotonic()
            return r
        except urllib.error.HTTPError as e:
            _last_request = time.monotonic()
            if e.code not in (429, 503) or attempt == 5:
                raise
            ra = e.headers.get("Retry-After", "")
            pause = int(ra) if ra.isdigit() else 30 * 2**attempt
            print(f"  {e.code} on {url}, waiting {pause} s", flush=True)
            time.sleep(pause)
    raise AssertionError("unreachable")


def get_bytes(url: str) -> bytes:
    with _open(url) as r:
        return r.read()


def head(url: str) -> tuple[int | None, str]:
    with _open(url, "HEAD") as r:
        v = r.headers.get("Content-Length")
        return (int(v) if v else None), r.headers.get("Last-Modified", "")


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, dest: Path) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    with _open(url) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
        length = r.headers.get("Content-Length")
        lm = r.headers.get("Last-Modified", "")
    got = tmp.stat().st_size
    if length is not None and got != int(length):
        tmp.unlink()
        raise SystemExit(f"{url}: got {got} bytes, the server stated {length}")
    tmp.replace(dest)
    return {"url": url, "bytes": got, "sha256": sha256(dest), "last_modified": lm,
            "fetched_at": now()}  # fmt: skip


def save_page(dest: Path, url: str, data: bytes, lm: str) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return {"url": url, "bytes": len(data), "sha256": sha256(dest), "last_modified": lm,
            "fetched_at": now()}  # fmt: skip


def write_manifest(mpath: Path, manifest: dict) -> None:
    """Write atomically, files sorted by path; manifest["files"] stays the same dict."""
    out = {**manifest, "files": dict(sorted(manifest["files"].items()))}
    tmp = mpath.with_name(mpath.name + ".part")
    tmp.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    tmp.replace(mpath)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", nargs="+", help="docs, shp, citygml, geojson and/or prefecture codes")
    ap.add_argument("--limit", type=int, help="fetch at most N of the selected files")
    ap.add_argument("--refresh", action="store_true",
                    help="HEAD every selected file and refetch what changed upstream")  # fmt: skip
    ap.add_argument("--dry-run", action="store_true", help="print the estimate and stop")
    a = ap.parse_args()

    with _open(LANDING_URL) as r:
        landing, landing_lm = r.read(), r.headers.get("Last-Modified", "")
    info = parse_landing(landing.decode("utf-8"), LANDING_URL)
    with _open(info["download_page"]) as r:
        dpage, dpage_lm = r.read(), r.headers.get("Last-Modified", "")
    year, rows = parse_download_table(dpage.decode("utf-8"), info["download_page"])
    version = edition(info["fiscal_year"])
    if edition(year) != version:
        raise SystemExit(f"the pages disagree on the edition: {info['fiscal_year']} vs {year}")
    if sorted({r["pref_code"] for r in rows}) != sorted(PREFECTURES) or len(rows) != 47 * 3:
        raise SystemExit(f"the download table has {len(rows)} files, expected 47 x 3")

    d = RAW / version
    d.mkdir(parents=True, exist_ok=True)
    mpath = d / "MANIFEST.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {"files": {}}
    files = manifest["files"]
    manifest.update(
        {
            "edition": version,
            "fiscal_year": info["fiscal_year"],
            "source_page": LANDING_URL,
            "download_page": info["download_page"],
            "update_history": info["update_history"],
            "content": info["content"],
            "original_sources": info["original_sources"],
            "method": info["method"],
            "listing_as_of": info["listing_as_of"],
            "terms_of_use": info["terms"],
            "licence": LICENCE,
        }
    )
    for name, url, data, lm in (
        ("pages/toshi_tosiko_tk_000087.html", LANDING_URL, landing, landing_lm),
        (f"pages/{Path(info['download_page']).name}", info["download_page"], dpage, dpage_lm),
    ):
        old = files.get(name)
        if not old or old["sha256"] != hashlib.sha256(data).hexdigest():
            files[name] = save_page(d / name, url, data, lm)
            print(f"{version}/{name}: {len(data):,} bytes (page changed or new)")

    plan = select(make_plan(info, rows), a.only, a.limit)
    todo = []
    for p in plan:
        e = files.get(p["path"])
        if up_to_date(d / p["path"], e, p["url"]):
            if not a.refresh:
                continue
            length, lm = head(p["url"])
            if length == e["bytes"] and lm == e["last_modified"]:
                continue
            print(f"  {p['path']}: changed upstream ({e['last_modified']} -> {lm})")
        todo.append(p)

    sizes = [head(p["url"])[0] for p in todo] if todo else []
    known = sum(s or 0 for s in sizes)
    unknown = sum(s is None for s in sizes)
    print(
        f"{version}: {len(plan)} files selected, {len(plan) - len(todo)} already here; "
        f"to fetch {len(todo)} files, {known:,} bytes ({known / 1e9:.2f} GB)"
        + (f", {unknown} without a stated size" if unknown else "")
        + f", {len(todo)} requests, about {len(todo) * DELAY / 60 + known / 5e6 / 60:.0f} min"
    )
    if a.dry_run:
        write_manifest(mpath, manifest)
        return 0

    for i, p in enumerate(todo, 1):
        entry = fetch(p["url"], d / p["path"])
        entry["label"] = p["label"]
        if p.get("note"):
            entry["note"] = p["note"]
        if p["kind"] != "docs":
            entry["format"] = p["kind"]
            entry["pref_code"] = p["pref_code"]
        files[p["path"]] = entry
        write_manifest(mpath, manifest)
        print(f"[{i}/{len(todo)}] {version}/{p['path']}: {entry['bytes']:,} bytes, "
              f"{entry['last_modified']}", flush=True)  # fmt: skip

    listing = next((n for n in files if n.startswith("docs/") and n.endswith(".xlsx")), None)
    if listing:
        got = parse_listing((d / listing).read_bytes())
        manifest["listing"] = {
            "file": listing,
            "municipalities": got["municipalities"],
            "layers": got["layers"],
        }
    write_manifest(mpath, manifest)
    print(f"{version}: {len(plan)} files selected, {len(todo)} fetched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
