import importlib.util
import zipfile
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures"

_spec = importlib.util.spec_from_file_location("export", ROOT / "scripts" / "03_export_parquet.py")
ex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ex)

MEMBER = "31_鳥取県/31202_米子市/31202_fuuchichiku"


def test_column_types_by_name():
    assert ex.column_type("YoutoCode") == "INTEGER"
    assert ex.column_type("AreaCode") == "INTEGER"
    assert ex.column_type("FaciCode") == "INTEGER"
    assert ex.column_type("FAR") == "DOUBLE"
    assert ex.column_type("BCR") == "DOUBLE"
    assert ex.column_type("Citycode") == "VARCHAR"
    assert ex.column_type("INDate") == "VARCHAR"
    assert ex.column_type("ValidType") == "VARCHAR"
    assert ex.column_type("Custodian") == "VARCHAR"


def test_crs_from_prj():
    prj = 'GEOGCS["GCS_JGD_2011",DATUM["D_JGD_2011",SPHEROID["GRS_1980",6378137.0,298.257222101]]]'
    assert ex.crs_from_prj(prj) == "EPSG:6668"
    with pytest.raises(ValueError):
        ex.crs_from_prj('PROJCS["JGD_2011_Japan_Zone_9",GEOGCS["GCS_JGD_2011"]]')


def test_member_names():
    assert ex.parse_member(MEMBER + ".shp") == ("31", "31202", "fuuchichiku")
    assert ex.parse_member("13_東京都/13101_千代田区/13101_youto.shp") == ("13", "13101", "youto")
    assert ex.parse_member("13_東京都/13101_千代田区/13101_youto.dbf") is None
    with pytest.raises(ValueError):
        ex.parse_member("13_東京都/13101_youto.shp")


def test_read_dbf_fixture():
    with zipfile.ZipFile(FIX / "shp_sample.zip") as z:
        fields, rows = ex.read_dbf(z.read(MEMBER + ".dbf"))
    names = [f[0] for f in fields]
    assert names == ["DistName", "DistType", "DistCode", "Pref", "Citycode", "Cityname",
                     "INDate", "FNDate", "ValidType", "Custodian", "INNumber", "FNNumber"]  # fmt: skip
    kinds = dict((f[0], f[1]) for f in fields)
    assert kinds["DistCode"] == "N" and kinds["INDate"] == "N" and kinds["Pref"] == "C"
    assert len(rows) == 1
    row = dict(zip(names, rows[0], strict=True))
    assert row["DistType"] == "風致地区"
    assert row["Citycode"] == "31202"
    assert row["DistCode"] == 28
    assert row["INDate"] is None  # a numeric field filled with '*' is the DBF's null
    assert row["DistName"] is None  # blank text is null, as GDAL reads it


def test_dbf_value_rules():
    assert ex.dbf_value(b"  abc  ", "C") == "abc"
    assert ex.dbf_value(b"     ", "C") is None
    assert ex.dbf_value(b"*" * 24, "N") is None
    assert ex.dbf_value(b"   28", "N") == 28
    assert ex.dbf_value(b"  1.500", "N") == 1.5
    with pytest.raises(UnicodeDecodeError):
        ex.dbf_value("用途".encode()[:-1], "C")


def test_layer_plan_from_zip():
    plan = ex.plan_layers([FIX / "shp_sample.zip"])
    assert list(plan) == ["fuuchichiku"]
    assert plan["fuuchichiku"]["files"] == [(FIX / "shp_sample.zip", MEMBER + ".shp")]
    assert plan["fuuchichiku"]["columns"][:3] == ["DistName", "DistType", "DistCode"]
    assert plan["fuuchichiku"]["rows"] == 1
    assert plan["fuuchichiku"]["crs"] == "EPSG:6668"


def _run(expr: str, value, name: str = "x"):
    con = duckdb.connect()
    return con.execute(f'select {expr} from (select ?::varchar as "{name}")', [value]).fetchone()[0]


def test_guards_cast_or_stop():
    i = ex.column_expr("f", "x", "INTEGER", "BIGINT")
    assert _run(i, "28") == 28
    with pytest.raises(duckdb.Error, match="not an integer"):
        _run(i, "2a")
    d = ex.column_expr("f", "x", "DOUBLE", "VARCHAR")
    assert _run(d, "150.0") == 150.0
    assert _run(d, None) is None
    with pytest.raises(duckdb.Error, match="not a number"):
        _run(d, "150%")
    c = ex.column_expr("f", "Citycode", "VARCHAR", "VARCHAR")
    assert _run(c, "01100", "Citycode") == "01100"
    with pytest.raises(duckdb.Error, match="five digits"):
        _run(c, "1100", "Citycode")
    # text by name, but GDAL typed the DBF field as a number: only nulls may pass
    t = ex.column_expr("f", "x", "VARCHAR", "DOUBLE")
    assert _run(t, None) is None
    with pytest.raises(duckdb.Error, match="numeric DBF field"):
        _run(t, "20200401")


def test_export_fixture(tmp_path):
    out = tmp_path / "pq"
    n = ex.export_all([FIX / "shp_sample.zip"], out, tmp_path / "work")
    assert n == {"fuuchichiku": 1}
    p = out / "fuuchichiku.parquet"
    con = duckdb.connect()
    con.execute("load spatial")
    cols = con.sql(f"describe select * from '{p}'").fetchall()
    types = {c[0]: c[1] for c in cols}
    assert [c[0] for c in cols][:2] == ["source_file", "fid"]
    assert types["DistCode"] == "INTEGER"
    assert types["INDate"] == "VARCHAR"
    assert types["geometry"].startswith("GEOMETRY")
    row = con.sql(
        f"select source_file, fid, DistType, INDate, st_geometrytype(geometry)::varchar from '{p}'"
    ).fetchone()
    assert row == (MEMBER + ".shp", 0, "風致地区", None, "POLYGON")
    geo = con.sql(
        f"select decode(value) from parquet_kv_metadata('{p}') where decode(key) = 'geo'"
    ).fetchone()[0]
    assert '"code":6668' in geo.replace(" ", "")
