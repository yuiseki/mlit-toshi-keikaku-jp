import importlib.util
import io
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures"

_spec = importlib.util.spec_from_file_location("dl", ROOT / "scripts" / "01_download.py")
dl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dl)

LANDING = (FIX / "landing.html").read_text(encoding="utf-8")
DOWNLOAD = (FIX / "download.html").read_text(encoding="utf-8")
BASE = "https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000087.html"


def test_landing_page():
    info = dl.parse_landing(LANDING, BASE)
    assert (
        info["download_page"] == "https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000182.html"
    )
    assert info["fiscal_year"] == "令和7年度"
    assert info["update_history"] == [
        "令和8年5月21日",
        "令和8年7月1日（シェープファイル形式・GeoJSONファイル形式　一部修正）",
        "令和8年7月2日（シェープファイル形式・GeoJSONファイル形式　一部修正）",
        "令和8年7月7日（CityGMLファイル形式　一部修正）",
    ]
    assert info["documents"] == [
        ("https://www.mlit.go.jp/toshi/tosiko/content/001752702.pdf", "データ定義書.pdf"),
        ("https://www.mlit.go.jp/toshi/tosiko/content/001752828.pdf", "CityGML仕様書.pdf"),
        (
            "https://www.mlit.go.jp/toshi/tosiko/content/001864274.xlsx",
            "公表自治体及び掲載データ一覧.xlsx",
        ),
    ]
    assert info["terms"][0].startswith("掲載データは、市町村又は都道府県から提出された")
    assert len(info["terms"]) == 10
    assert info["terms"][-1].endswith("何ら責任を負うものではありません。")


def test_download_table():
    year, rows = dl.parse_download_table(DOWNLOAD, "https://www.mlit.go.jp/x/y.html")
    assert year == "令和７年度"
    assert [(r["pref_code"], r["pref"], r["format"]) for r in rows] == [
        ("01", "北海道", "shp"),
        ("01", "北海道", "citygml"),
        ("01", "北海道", "geojson"),
        ("03", "岩手県", "shp"),
        ("03", "岩手県", "citygml"),
        ("03", "岩手県", "geojson"),
        ("45", "宮崎県", "shp"),
        ("45", "宮崎県", "citygml"),
        ("45", "宮崎県", "geojson"),
    ]
    iwate = [r for r in rows if r["pref"] == "岩手県"]
    assert iwate[0]["url"] == "https://www.mlit.go.jp/toshi/tosiko/content/001752714.zip"
    assert [r["note"] for r in iwate] == ["（R8.7.1修正）", "（R8.7.7修正）", "（R8.7.1修正）"]
    assert rows[0]["note"] == ""


def test_edition_from_fiscal_year():
    assert dl.edition("令和７年度") == "fy2025"
    assert dl.edition("令和7年度") == "fy2025"
    assert dl.edition("令和10年度") == "fy2028"
    with pytest.raises(ValueError):
        dl.edition("平成30年度")


def test_plan_paths_and_filters():
    info = dl.parse_landing(LANDING, BASE)
    _, rows = dl.parse_download_table(DOWNLOAD, "https://www.mlit.go.jp/x/y.html")
    plan = dl.make_plan(info, rows)
    paths = [p["path"] for p in plan]
    assert paths[:3] == [
        "docs/001752702.pdf",
        "docs/001752828.pdf",
        "docs/001864274.xlsx",
    ]
    assert "shp/03_iwate.zip" in paths
    assert "geojson/45_miyazaki.zip" in paths
    assert len(paths) == len(set(paths)) == 3 + 9
    assert [p["path"] for p in dl.select(plan, ["shp"], None)] == [
        "shp/01_hokkaido.zip",
        "shp/03_iwate.zip",
        "shp/45_miyazaki.zip",
    ]
    assert [p["path"] for p in dl.select(plan, ["45"], None)] == [
        "shp/45_miyazaki.zip",
        "citygml/45_miyazaki.zip",
        "geojson/45_miyazaki.zip",
    ]
    assert [p["path"] for p in dl.select(plan, ["shp", "45"], None)] == ["shp/45_miyazaki.zip"]
    assert len(dl.select(plan, ["docs"], None)) == 3
    assert len(dl.select(plan, ["docs", "45"], None)) == 3 + 3
    assert len(dl.select(plan, ["docs", "geojson"], None)) == 3 + 3
    assert len(dl.select(plan, None, 2)) == 2
    with pytest.raises(SystemExit):
        dl.select(plan, ["nonsense"], None)


def test_skip_only_when_hash_matches(tmp_path):
    f = tmp_path / "a.zip"
    f.write_bytes(b"abc")
    entry = {"url": "u", "sha256": dl.sha256(f), "bytes": 3}
    assert dl.up_to_date(f, entry, "u")
    assert not dl.up_to_date(f, entry, "other-url")
    assert not dl.up_to_date(f, {**entry, "sha256": "0" * 64}, "u")
    assert not dl.up_to_date(tmp_path / "missing.zip", entry, "u")
    assert not dl.up_to_date(f, None, "u")


def _xlsx(rows: list[list[str]]) -> bytes:
    """A minimal workbook with inline strings, as the listing's layout."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    body = []
    for i, r in enumerate(rows, 1):
        cells = "".join(
            f'<c r="{chr(65 + j)}{i}" t="inlineStr"><is><t>{v}</t></is></c>'
            for j, v in enumerate(r)
            if v != ""
        )
        body.append(f'<row r="{i}">{cells}</row>')
    sheet = f'<worksheet xmlns="{ns}"><sheetData>{"".join(body)}</sheetData></worksheet>'
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return b.getvalue()


def test_listing_counts():
    header = ["", "団体コード", "都道府県名\n（漢字）", "市区町村名\n（漢字）", "", "", "",
              "都市計画区域", "用途地域", "データ作成年", "データ時点年", "留意事項"]  # fmt: skip
    rows = [
        ["title"],
        ["", "legend"],
        header,
        ["", "010006", "北海道"],
        ["", "011002", "北海道", "札幌市", "", "", "", "〇", "〇", "45539", "45539", ""],
        ["", "012025", "北海道", "函館市", "", "", "", "〇", "×", "44645", "44645", ""],
        ["", "473626", "沖縄県", "八重瀬町", "", "", "", "〇", "－", "45366", "45000", ""],
    ]
    got = dl.parse_listing(_xlsx(rows))
    assert got["municipalities"] == 3
    assert got["layers"] == {
        "都市計画区域": {"〇": 3},
        "用途地域": {"〇": 1, "×": 1, "－": 1},
    }
    assert got["by_city"]["01100"] == {"都市計画区域": "〇", "用途地域": "〇"}
    assert got["by_city"]["47362"]["用途地域"] == "－"


def test_manifest_keeps_entries_added_after_a_write(tmp_path):
    m = tmp_path / "MANIFEST.json"
    manifest = {"files": {"b": {"n": 1}}}
    files = manifest["files"]
    dl.write_manifest(m, manifest)
    files["a"] = {"n": 2}
    dl.write_manifest(m, manifest)
    got = json.loads(m.read_text())["files"]
    assert list(got) == ["a", "b"]
