#!/usr/bin/env python3
"""Turn the Shapefiles of an edition into one GeoParquet per layer.

Each prefecture's Shapefile zip holds <pref>_<name>/<citycode>_<name>/<citycode>_<layer>.shp
(with .dbf, .shx, .prj and a .cpg that says UTF-8) for every layer the
municipality has: youto (用途地域), tokei (都市計画区域), douro (都市計画道路) and
so on, 26 layers in fy2025. For every layer, the files of all 47 zips are
read with DuckDB's spatial extension (ST_Read, which uses GDAL) and written,
one after another, to data/parquet/<edition>/<layer>.parquet, rows in the
order of zip, member path and record. The GeoJSON zips hold the same
features (02_verify.py checks the counts) and the CityGML zips a different
model; both are published as served and not converted.

Columns are the DBF's own names, the union over all files of the layer in
the order first met; a file without a column gives NULL there. Two columns
are added in front: source_file, the .shp's path inside its zip, and fid,
the record's position in that Shapefile from 0. Types come from the name,
never from the DBF or from inference:
  - <Something>Code (YoutoCode, AreaCode, DistCode, ...) is INTEGER
  - FAR and BCR (容積率, 建蔽率, in %) are DOUBLE; the DBF holds them as text
  - everything else is VARCHAR: Citycode with its leading zero, the dates
    (INDate, FNDate, written in many ways) and the notice numbers.
Each cast is guarded by a regular expression and a value that does not fit
stops the run with error(), naming the file and column. Some producers wrote
text fields (ValidType, INDate, Custodian, ...) as numeric DBF fields filled
with '*', the DBF's null; such a field must hold nothing else, or the run
stops. Citycode must be five digits.

The text is UTF-8, as every .cpg says; a .cpg saying anything else stops the
run (DuckDB's own Shift_JIS decoding breaks at a 32 MB boundary, so such data
would have to be decoded in Python first). The geometry is the Shapefile's,
in the CRS the .prj names (GCS_JGD_2011, EPSG:6668, longitude/latitude in
degrees), never reprojected.

    uv run python scripts/03_export_parquet.py            # the newest edition
    uv run python scripts/03_export_parquet.py fy2025
"""

import json
import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "parquet"
WORK = ROOT / "data" / "work"

# the GEOGCS name in the .prj -> the CRS the GeoParquet states
PRJ_CRS = {"GCS_JGD_2011": "EPSG:6668"}
DOUBLES = {"FAR", "BCR"}
MEMBER = re.compile(r"(\d{2})_[^/]+/(\d{5})_[^/]+/(\d{5})_([A-Za-z0-9]+)\.shp")


def column_type(name: str) -> str:
    if re.fullmatch(r"[A-Z][A-Za-z]*Code", name):
        return "INTEGER"
    if name in DOUBLES:
        return "DOUBLE"
    return "VARCHAR"


def crs_from_prj(text: str) -> str:
    mt = re.match(r'\s*GEOGCS\["([^"]+)"', text)
    if not mt or mt.group(1) not in PRJ_CRS:
        raise ValueError(f"no rule for the .prj {text[:80]!r}")
    return PRJ_CRS[mt.group(1)]


def parse_member(name: str) -> tuple[str, str, str] | None:
    """(prefecture code, city code, layer) of a .shp member; None for other members."""
    if not name.endswith(".shp"):
        return None
    mt = MEMBER.fullmatch(name)
    if not mt or mt.group(2) != mt.group(3):
        raise ValueError(f"unexpected member {name!r}")
    return mt.group(1), mt.group(2), mt.group(4)


# ---------------------------------------------------------------- DBF, read here without GDAL


def dbf_fields(b: bytes) -> tuple[int, int, int, list[tuple[str, str, int, int]]]:
    """(records, header length, record length, [(name, type, width, decimals)])."""
    n, header_len, rec_len = struct.unpack("<IHH", b[4:12])
    fields, i = [], 32
    while b[i] != 0x0D:
        name = b[i : i + 11].split(b"\0")[0].decode("ascii")
        fields.append((name, chr(b[i + 11]), b[i + 16], b[i + 17]))
        i += 32
    return n, header_len, rec_len, fields


def dbf_value(raw: bytes, kind: str):
    """A DBF cell as GDAL gives it: text trimmed (blank is null), numbers parsed, '*' fill null."""
    s = raw.decode("utf-8", errors="strict").strip(" ")
    if not s:
        return None
    if kind in ("N", "F"):
        if set(s) == {"*"}:
            return None
        return float(s) if "." in s else int(s)
    return s


def read_dbf(b: bytes) -> tuple[list[tuple[str, str, int, int]], list[list]]:
    n, header_len, rec_len, fields = dbf_fields(b)
    rows = []
    for r in range(n):
        rec = b[header_len + r * rec_len : header_len + (r + 1) * rec_len]
        if rec[:1] != b" ":
            raise ValueError(f"record {r} is marked deleted")
        p, row = 1, []
        for _, kind, width, _ in fields:
            row.append(dbf_value(rec[p : p + width], kind))
            p += width
        rows.append(row)
    return fields, rows


# ---------------------------------------------------------------- planning and SQL


def plan_layers(zips: list[Path]) -> dict[str, dict]:
    """Per layer: its (zip, .shp member) files in order, column union, DBF record count, CRS."""
    plan: dict[str, dict] = {}
    for zpath in zips:
        with zipfile.ZipFile(zpath) as z:
            names = set(z.namelist())
            for name in sorted(names):
                got = parse_member(name)
                if got is None:
                    continue
                stem = name[:-4]
                for ext in (".dbf", ".shx", ".prj", ".cpg"):
                    if stem + ext not in names:
                        raise ValueError(f"{zpath.name}: {stem}{ext} missing")
                cpg = z.read(stem + ".cpg").decode("ascii").strip()
                if cpg.upper() not in ("UTF-8", "UTF8"):
                    raise ValueError(f"{zpath.name}: {stem}.cpg says {cpg!r}, not UTF-8")
                with z.open(stem + ".dbf") as f:
                    head = f.read(32 * 256)
                n, _, _, fields = dbf_fields(head)
                crs = crs_from_prj(z.read(stem + ".prj").decode("ascii"))
                layer = plan.setdefault(got[2], {"files": [], "columns": [], "rows": 0, "crs": crs})
                if layer["crs"] != crs:
                    raise ValueError(f"{name}: CRS {crs}, the layer's other files {layer['crs']}")
                layer["files"].append((zpath, name))
                layer["rows"] += n
                for fname, *_ in fields:
                    if fname not in layer["columns"]:
                        layer["columns"].append(fname)
    return dict(sorted(plan.items()))


def column_expr(label: str, name: str, rule: str, gdal: str) -> str:
    """The select item for one column: the type its name gives, or error()."""
    c = f'"{name}"'
    v = f"cast({c} as varchar)"
    where = f"{label}: {name}"
    if rule == "VARCHAR" and gdal != "VARCHAR":
        return (
            f"case when {c} is null then null "
            f"else error('{where} is a numeric DBF field holding ' || {v}) end as {c}"
        )
    if rule == "INTEGER":
        return (
            f"case when {c} is null then null "
            f"when regexp_full_match({v}, '-?[0-9]{{1,9}}') then cast({v} as integer) "
            f"else error('{where} is not an integer: ' || {v}) end as {c}"
        )
    if rule == "DOUBLE":
        return (
            f"case when {c} is null then null "
            f"when regexp_full_match({v}, '[0-9]+(\\.[0-9]+)?') then cast({v} as double) "
            f"else error('{where} is not a number: ' || {v}) end as {c}"
        )
    if name == "Citycode":
        return (
            f"case when {c} is null or regexp_full_match({c}, '[0-9]{{5}}') then {c} "
            f"else error('{where} is not five digits: ' || {c}) end as {c}"
        )
    return f"{c} as {c}"


def _sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def export_all(zips: list[Path], out: Path, work: Path) -> dict[str, int]:
    """Write one GeoParquet per layer from the Shapefile zips; returns rows per layer."""
    import duckdb

    plan = plan_layers(zips)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    con = duckdb.connect(str(work / "export.duckdb"))
    con.execute("set memory_limit = '8GB'; set preserve_insertion_order = true; load spatial")
    for layer, lp in plan.items():
        cols = ", ".join(f'"{c}" {column_type(c)}' for c in lp["columns"])
        con.execute(
            f'create table "{layer}" '
            f"(source_file varchar, fid bigint, {cols}, geometry geometry('{lp['crs']}'))"
        )

    counts = {layer: 0 for layer in plan}
    by_zip: dict[Path, list[tuple[str, str]]] = {}
    for layer, lp in plan.items():
        for zpath, member in lp["files"]:
            by_zip.setdefault(zpath, []).append((layer, member))
    for zpath, members in by_zip.items():
        tmp = work / zpath.stem
        with zipfile.ZipFile(zpath) as z:
            z.extractall(tmp)  # CRC checked by zipfile on read
        for layer, member in sorted(members, key=lambda m: m[1]):
            shp = tmp / member
            want = plan[layer]["crs"]
            src = f"st_read({_sql_str(str(shp))})"
            types = dict(
                con.sql(f"select column_name, column_type from (describe select * from {src})")
                .fetchall()
            )  # fmt: skip
            got = types.pop("geom")
            if got != f"GEOMETRY('{want}')":
                raise ValueError(f"{member}: GDAL reads the .prj as {got}, the rule says {want}")
            types.pop("OGC_FID")
            label = member.replace("'", "")
            items = [f"{_sql_str(member)} as source_file", 'cast("OGC_FID" as bigint) as fid']
            items += [column_expr(label, n, column_type(n), t) for n, t in types.items()]
            items.append("geom as geometry")
            con.execute(f'insert into "{layer}" by name select {", ".join(items)} from {src}')
            counts[layer] += con.sql(f"select count(*) from {src}").fetchone()[0]
        shutil.rmtree(tmp)
        print(f"  read {zpath.name}: {len(members)} Shapefiles", flush=True)

    out.mkdir(parents=True, exist_ok=True)
    for layer, lp in plan.items():
        if counts[layer] != lp["rows"]:
            raise SystemExit(f"{layer}: GDAL read {counts[layer]} rows, the DBFs hold {lp['rows']}")
        p = out / f"{layer}.parquet"
        tmp = p.with_name(p.name + ".part")
        cols = ", ".join(f'"{c}"' for c in lp["columns"])
        con.execute(
            f'copy (select source_file, fid, {cols}, geometry from "{layer}" '
            f"order by source_file, fid) to '{tmp}' "
            "(format parquet, compression zstd, row_group_size 100000, write_bloom_filter false)"
        )
        tmp.replace(p)
        n = con.sql(f"select count(*) from '{p}'").fetchone()[0]
        if n != lp["rows"]:
            raise SystemExit(f"{layer}: {n} rows written, the DBFs hold {lp['rows']}")
        print(f"  {layer}: {n:,} rows, {p.stat().st_size:,} bytes", flush=True)
    con.close()
    shutil.rmtree(work)
    return counts


def main() -> int:
    editions = sorted(p.parent.name for p in RAW.glob("*/MANIFEST.json"))
    if not editions:
        raise SystemExit("no MANIFEST.json under data/raw/; run scripts/01_download.py")
    edition = sys.argv[1] if len(sys.argv) > 1 else editions[-1]
    d = RAW / edition
    files = json.loads((d / "MANIFEST.json").read_text())["files"]
    zips = [d / n for n, e in sorted(files.items()) if e.get("format") == "shp"]
    if len(zips) != 47:
        raise SystemExit(f"{edition}: {len(zips)} Shapefile zips in the manifest, expected 47")
    out = OUT / edition
    if out.exists():
        shutil.rmtree(out)
    counts = export_all(zips, out, WORK / edition)
    if WORK.exists() and not any(WORK.iterdir()):
        WORK.rmdir()
    print(f"{edition}: {len(counts)} layers, {sum(counts.values()):,} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
