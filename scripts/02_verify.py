#!/usr/bin/env python3
"""Check every edition under data/raw/ against its MANIFEST.json, and the GeoParquet against the Shapefiles.

For each edition directory:
  - every file in the manifest exists with the bytes and sha256 recorded,
    and no file in the directory is missing from the manifest
  - every zip (and the xlsx) passes zipfile.testzip; every PDF starts with %PDF
  - every Shapefile zip: each .shp comes with .dbf, .shx, .prj and a .cpg
    saying UTF-8, and has as many records in its .shx as its DBF header says
  - every GeoJSON zip holds the same files as the Shapefile zip of its
    prefecture, each read with the json module, with as many features as
    the DBF has records and the CRS urn:ogc:def:crs:EPSG::6668
  - every CityGML zip: the number of .gml members is printed
  - the municipality list (xlsx): for each layer, how many municipalities it
    marks 〇 and how many have a Shapefile, printed; they differ, and the
    difference is not counted as a failure (the list is dated separately)

For each layer's GeoParquet, against the Shapefiles in the zips:
  - as many rows as the DBF headers say, in the order of source_file and fid
  - the columns source_file, fid, the DBF names (union over the files), and
    geometry, each of the type column_type gives its name
  - every attribute value of every record equals the DBF's, read here with
    a reader of its own (not GDAL), decoded as strict UTF-8
  - every geometry has the bytes of the x and y of its .shp record, part by
    part (parts compared as a set, since GDAL groups polygon rings into
    polygons); a null shape is a null geometry
  - Citycode is the city code in the file's name, in every row
  - the GeoParquet metadata states EPSG:6668, as the .prj says
  - a DuckDB without the spatial extension opens the file; no bloom filters

Prints one ok/FAIL line per check and exits 1 if any failed.

    uv run python scripts/02_verify.py              # every edition
    uv run python scripts/02_verify.py --raw-only   # skip the Parquet
"""

import argparse
import hashlib
import importlib.util
import json
import struct
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PQ = ROOT / "data" / "parquet"


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


export = _load("export", "03_export_parquet.py")
download = _load("download", "01_download.py")

# the column headings of the municipality list -> the layer in the file names
LISTING_LAYERS = {
    "都市計画区域": "tokei", "区域区分": "senbiki", "用途地域": "youto",
    "特別用途地区": "tkbt", "高度地区": "koudoti", "高度利用地区": "koudori",
    "防火準防火": "bouka", "土地区画整理事業": "tochiku", "地区計画": "chikukei",
    "都市計画道路": "douro", "公園": "kouen", "立地適正化計画": "ritteki",
    "特例容積率適用地区": "tokureiyouseki", "高層住居誘導地区": "kousoujyukyo",
    "居住調整地域": "kyojyuchosei", "特定用途誘導地区": "tokuteiyuudou",
    "特定防火街区整備地区": "tokuteibou", "歴史的風土保存地区": "rekifuu",
    "緑化地域": "ryokukachiiki", "航空機騒音障害防止地区": "soubou",
    "一団地の復興再生拠点市街地形成施設": "fukkousaiseikyoten",
    "準都市計画区域": "jyuntoshi", "都市再生特別地区": "toshisaisei",
    "特定用途制限地域": "tokuteiyouto", "風致地区": "fuuchichiku",
    "特別緑地保全地区": "tokuryoku",
}  # fmt: skip
GEOJSON_CRS = "urn:ogc:def:crs:EPSG::6668"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------- readers of our own


def shp_parts(b: bytes) -> list[list[bytes]]:
    """Each .shp record as the bytes of its parts' x, y pairs (little-endian doubles)."""
    out, p = [], 100
    while p < len(b):
        length = struct.unpack(">i", b[p + 4 : p + 8])[0] * 2
        rec = b[p + 8 : p + 8 + length]
        p += 8 + length
        kind = struct.unpack("<i", rec[:4])[0]
        if kind == 0:
            out.append([])
        elif kind in (3, 5):
            nparts, npoints = struct.unpack("<2i", rec[36:44])
            starts = list(struct.unpack(f"<{nparts}i", rec[44 : 44 + 4 * nparts])) + [npoints]
            q = 44 + 4 * nparts
            out.append(
                [rec[q + 16 * s : q + 16 * e] for s, e in zip(starts, starts[1:], strict=False)]
            )
        else:
            raise ValueError(f"shape type {kind} not handled")
    return out


def wkb_parts(b: bytes | None) -> list[bytes]:
    """The x, y bytes of each ring or line of a 2D little-endian WKB geometry, in order."""
    if b is None:
        return []
    out: list[bytes] = []

    def seq(p: int) -> int:
        (n,) = struct.unpack("<I", b[p : p + 4])
        out.append(b[p + 4 : p + 4 + 16 * n])
        return p + 4 + 16 * n

    def geom(p: int) -> int:
        if b[p] != 1:
            raise ValueError("big-endian WKB")
        (kind,) = struct.unpack("<I", b[p + 1 : p + 5])
        p += 5
        if kind == 2:
            return seq(p)
        if kind in (3, 5, 6):
            (n,) = struct.unpack("<I", b[p : p + 4])
            p += 4
            for _ in range(n):
                p = seq(p) if kind == 3 else geom(p)
            return p
        raise ValueError(f"WKB type {kind} not handled")

    geom(0)
    return out


def expected(name: str, raw):
    """What the Parquet should hold for a DBF value read by export.read_dbf."""
    if raw is None:
        return None
    t = export.column_type(name)
    if t == "INTEGER":
        return int(raw)
    if t == "DOUBLE":
        return float(raw)
    return raw


def shapefile_counts(zpath: Path) -> dict[str, int]:
    """Stem -> DBF record count, for every .shp of a zip."""
    out = {}
    with zipfile.ZipFile(zpath) as z:
        for name in z.namelist():
            if export.parse_member(name) is not None:
                with z.open(name[:-4] + ".dbf") as f:
                    out[name[:-4]] = struct.unpack("<I", f.read(8)[4:8])[0]
    return out


def geojson_counts(zpath: Path) -> dict[str, tuple[int, str]]:
    """Stem -> (features, CRS name) for every .geojson of a zip."""
    out = {}
    with zipfile.ZipFile(zpath) as z:
        for name in z.namelist():
            if name.endswith(".geojson"):
                d = json.loads(z.read(name).decode("utf-8"))
                crs = ((d.get("crs") or {}).get("properties") or {}).get("name", "")
                out[name.removesuffix(".geojson")] = (len(d["features"]), crs)
    return out


# ---------------------------------------------------------------- raw files


def verify_raw(d: Path, check) -> dict:
    manifest = json.loads((d / "MANIFEST.json").read_text())
    files = manifest["files"]
    on_disk = {
        p.relative_to(d).as_posix()
        for p in d.rglob("*")
        if p.is_file() and p.name != "MANIFEST.json"
    }
    extra = sorted(on_disk - set(files))
    check(not extra, f"{d.name}: no files outside the manifest {extra or ''}".rstrip())
    for name, e in files.items():
        p = d / name
        if not p.exists():
            check(False, f"{d.name}/{name}: missing")
            continue
        ok = p.stat().st_size == e["bytes"] and sha256(p) == e["sha256"]
        check(ok, f"{d.name}/{name}: {e['bytes']:,} bytes, sha256 as in the manifest")
        if name.endswith((".zip", ".xlsx")):
            try:
                with zipfile.ZipFile(p) as z:
                    bad = z.testzip()
                check(bad is None, f"{d.name}/{name}: zip test" + (f" (bad {bad})" if bad else ""))
            except zipfile.BadZipFile as ex:
                check(False, f"{d.name}/{name}: {ex}")
        elif name.endswith(".pdf"):
            check(p.read_bytes()[:5] == b"%PDF-", f"{d.name}/{name}: a PDF")

    shp_total: dict[str, int] = {}
    cities: dict[str, set[str]] = {}
    for name, e in sorted(files.items()):
        if e.get("format") != "shp":
            continue
        try:
            plan = export.plan_layers([d / name])  # checks members, .cpg, .prj
        except ValueError as ex:
            check(False, f"{d.name}/{name}: {ex}")
            continue
        shx_bad = []
        with zipfile.ZipFile(d / name) as z:
            for layer, lp in plan.items():
                for _, member in lp["files"]:
                    nshx = (z.getinfo(member[:-4] + ".shx").file_size - 100) // 8
                    with z.open(member[:-4] + ".dbf") as f:
                        ndbf = struct.unpack("<I", f.read(8)[4:8])[0]
                    if nshx != ndbf:
                        shx_bad.append(member)
                    cities.setdefault(layer, set()).add(export.parse_member(member)[1])
                shp_total[layer] = shp_total.get(layer, 0) + lp["rows"]
        nfiles = sum(len(lp["files"]) for lp in plan.values())
        check(
            not shx_bad, f"{d.name}/{name}: {nfiles} Shapefiles, .shx and DBF agree {shx_bad or ''}"
        )

        gname = name.replace("shp/", "geojson/", 1)
        if gname in files:
            shp = shapefile_counts(d / name)
            gj = geojson_counts(d / gname)
            same = set(shp) == set(gj)
            diff = [s for s in shp if s in gj and gj[s][0] != shp[s]]
            crs = Counter(c for _, c in gj.values())
            check(
                same and not diff and set(crs) <= {GEOJSON_CRS},
                f"{d.name}/{gname}: the same {len(gj)} files, feature counts equal the DBFs "
                f"({sum(n for n, _ in gj.values()):,} features), CRS {dict(crs)}"
                + (f" differ: {diff[:5]}" if diff else ""),
            )
    for name, e in sorted(files.items()):
        if e.get("format") == "citygml":
            with zipfile.ZipFile(d / name) as z:
                n = sum(1 for m in z.namelist() if m.endswith(".gml"))
            print(f"info  {d.name}/{name}: {n} .gml files")

    listing = next((n for n in files if n.startswith("docs/") and n.endswith(".xlsx")), None)
    if listing:
        got = download.parse_listing((d / listing).read_bytes())
        unknown = set(got["layers"]) - set(LISTING_LAYERS)
        check(not unknown, f"{d.name}/{listing}: every layer heading known {sorted(unknown) or ''}")
        print(f"info  {d.name}: {got['municipalities']} municipalities in the list")
        for jp, layer in LISTING_LAYERS.items():
            marked = {c for c, m in got["by_city"].items() if m.get(jp) == "〇"}
            have = cities.get(layer, set())
            print(
                f"info  {layer:<19} list 〇 {len(marked):>5}, Shapefiles {len(have):>5}, "
                f"〇 without a file {len(marked - have):>3}, a file without 〇 {len(have - marked):>3}"
            )
    return {"rows": shp_total, "files": files}


# ---------------------------------------------------------------- Parquet


def _rows(cur):
    while chunk := cur.fetchmany(20000):
        yield from chunk


def verify_parquet(d: Path, raw: dict, check) -> None:
    import duckdb

    pq = PQ / d.name
    zips = [d / n for n, e in sorted(raw["files"].items()) if e.get("format") == "shp"]
    plan = export.plan_layers(zips)
    con = duckdb.connect()
    con.execute("set memory_limit = '8GB'; load spatial")
    plain = duckdb.connect(config={"autoload_known_extensions": False})
    for layer, lp in plan.items():
        p = pq / f"{layer}.parquet"
        label = f"{d.name}.{layer}"
        if not p.exists():
            check(False, f"{label}: {p.relative_to(ROOT)} missing")
            continue
        n = con.sql(f"select count(*) from '{p}'").fetchone()[0]
        check(n == lp["rows"], f"{label}: {n:,} rows, the DBFs hold {lp['rows']:,}")

        types = dict(
            con.sql(
                f"select column_name, column_type from (describe select * from '{p}')"
            ).fetchall()
        )
        want = {"source_file": "VARCHAR", "fid": "BIGINT"}
        want |= {c: export.column_type(c) for c in lp["columns"]}
        gtype = types.pop("geometry", None)
        check(
            list(types) == list(want) and types == want and gtype == f"GEOMETRY('{lp['crs']}')",
            f"{label}: columns and types as named ({len(want)} + geometry {gtype})",
        )

        cols = ", ".join(f'"{c}"' for c in lp["columns"])
        cur = con.execute(
            f"select source_file, fid, {cols}, st_aswkb(geometry) from '{p}' order by source_file, fid"
        )
        bad_attr, bad_geom, bad_order, null_geom, city_off, cells = [], [], 0, 0, Counter(), 0
        files = sorted(lp["files"], key=lambda f: f[1])

        it = _rows(cur)
        zcache: dict[Path, zipfile.ZipFile] = {}
        for zpath, member in files:
            z = zcache.setdefault(zpath, zipfile.ZipFile(zpath))
            stem = member[:-4]
            fields, recs = export.read_dbf(z.read(stem + ".dbf"))
            shapes = shp_parts(z.read(member))
            city = export.parse_member(member)[1]
            names = [f[0] for f in fields]
            for i, (rec, parts) in enumerate(zip(recs, shapes, strict=True)):
                buf = next(it, None)
                if buf is None or buf[0] != member or buf[1] != i:
                    bad_order += 1
                    break
                vals = dict(zip(lp["columns"], buf[2:-1], strict=True))
                want_vals = {c: None for c in lp["columns"]}
                want_vals |= {nm: expected(nm, v) for nm, v in zip(names, rec, strict=True)}
                cells += len(names)
                if vals != want_vals:
                    bad_attr.append((member, i))
                geom = bytes(buf[-1]) if buf[-1] is not None else None
                null_geom += geom is None
                if sorted(wkb_parts(geom)) != sorted(parts):
                    bad_geom.append((member, i))
                if vals.get("Citycode") != city:
                    city_off[f"{city}->{vals.get('Citycode')}"] += 1
        left = next(it, None)
        for z in zcache.values():
            z.close()
        check(not bad_order and left is None, f"{label}: rows in the order of the Shapefiles")
        check(
            not bad_attr,
            f"{label}: all {cells:,} attribute values equal the DBFs {bad_attr[:3] or ''}",
        )
        check(
            not bad_geom,
            f"{label}: every geometry has its .shp coordinates ({null_geom} null) {bad_geom[:3] or ''}",
        )
        check(
            not city_off,
            f"{label}: Citycode is the code in the file name in every row "
            f"{dict(city_off.most_common(5)) or ''}".rstrip(),
        )

        geo = json.loads(
            con.sql(
                f"select decode(value) from parquet_kv_metadata('{p}') where decode(key) = 'geo'"
            ).fetchone()[0]
        )
        g = geo["columns"]["geometry"]
        crs_id = "{authority}:{code}".format(**g["crs"]["id"])
        check(
            crs_id == lp["crs"],
            f"{label}: GeoParquet {geo['version']}, {g['geometry_types']}, CRS {crs_id}",
        )
        pn = plain.sql(f"select count(*) from '{p}'").fetchone()[0]
        bloom = con.sql(
            f"select count(*) filter (where bloom_filter_offset is not null) from parquet_metadata('{p}')"
        ).fetchone()[0]
        check(
            pn == n and bloom == 0, f"{label}: a DuckDB without spatial opens it; no bloom filters"
        )
    extra = sorted({q.stem for q in pq.glob("*.parquet")} - set(plan))
    check(not extra, f"{d.name}: no Parquet without a layer {extra or ''}".rstrip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-only", action="store_true")
    a = ap.parse_args()
    failures = []

    def check(ok: bool, what: str) -> None:
        print(("ok    " if ok else "FAIL  ") + what, flush=True)
        if not ok:
            failures.append(what)

    dirs = sorted(p.parent for p in RAW.glob("*/MANIFEST.json"))
    check(bool(dirs), f"{len(dirs)} edition(s) under data/raw")
    for d in dirs:
        raw = verify_raw(d, check)
        if not a.raw_only:
            if (PQ / d.name).exists():
                verify_parquet(d, raw, check)
            else:
                check(False, f"{d.name}: no Parquet; run scripts/03_export_parquet.py")
    if failures:
        print(f"\n{len(failures)} checks failed")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
