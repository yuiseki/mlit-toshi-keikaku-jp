import importlib.util
import struct
import zipfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures"

_spec = importlib.util.spec_from_file_location("verify", ROOT / "scripts" / "02_verify.py")
vf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vf)

STEM = "31_鳥取県/31202_米子市/31202_fuuchichiku"


def test_shp_parts_and_wkb_parts_agree_on_the_fixture():
    with zipfile.ZipFile(FIX / "shp_sample.zip") as z:
        shp = z.read(STEM + ".shp")
    recs = vf.shp_parts(shp)
    assert len(recs) == 1
    assert len(recs[0]) == 1 and len(recs[0][0]) % 16 == 0
    con = duckdb.connect()
    con.execute("load spatial")
    # a WKB polygon built from the same ring must give the same bytes back
    xy = [struct.unpack("<2d", recs[0][0][i : i + 16]) for i in range(0, len(recs[0][0]), 16)]
    wkt = "POLYGON((" + ", ".join(f"{x!r} {y!r}" for x, y in xy) + "))"
    wkb = con.sql(f"select st_aswkb(st_geomfromtext('{wkt}'))").fetchone()[0]
    assert vf.wkb_parts(bytes(wkb)) == recs[0]


def test_wkb_parts_multi():
    con = duckdb.connect()
    con.execute("load spatial")
    wkb = con.sql(
        "select st_aswkb(st_geomfromtext('MULTILINESTRING((0 0, 1 1), (2 2, 3 3, 4 4))'))"
    ).fetchone()[0]
    parts = vf.wkb_parts(bytes(wkb))
    assert [len(p) // 16 for p in parts] == [2, 3]
    assert parts[1][:16] == struct.pack("<2d", 2.0, 2.0)
    assert vf.wkb_parts(None) == []


def test_expected_values_by_column_type():
    assert vf.expected("YoutoCode", 5) == 5
    assert vf.expected("FAR", "200.0") == 200.0
    assert vf.expected("BCR", None) is None
    assert vf.expected("Citycode", "01100") == "01100"
    assert vf.expected("INDate", None) is None


def test_geojson_counts_on_the_fixture():
    got = vf.geojson_counts(FIX / "geojson_sample.zip")
    assert got == {STEM: (1, "urn:ogc:def:crs:EPSG::6668")}


def test_shapefile_counts_on_the_fixture():
    got = vf.shapefile_counts(FIX / "shp_sample.zip")
    assert got == {STEM: 1}


def test_listing_layer_names_cover_the_known_layers():
    assert vf.LISTING_LAYERS["用途地域"] == "youto"
    assert vf.LISTING_LAYERS["都市計画道路"] == "douro"
    assert len(vf.LISTING_LAYERS) == 26
    assert len(set(vf.LISTING_LAYERS.values())) == 26
