# mlit-toshi-keikaku-jp

A reproducible copy of 都市計画決定GISデータ (urban planning decision GIS data),
the national edition that the City Bureau of Japan's Ministry of Land,
Infrastructure, Transport and Tourism (MLIT) publishes: the city planning
decisions of about 1,400 municipalities (use districts with their floor-area
and building-coverage ratios, city planning areas, urbanisation areas, planned
roads, parks, district plans, location normalisation plans and 20 more
layers), per prefecture in three formats: Shapefile, GeoJSON and CityGML.
The Shapefiles become one GeoParquet per layer.

The dataset is published at
<https://huggingface.co/datasets/yuiseki/mlit-toshi-keikaku-jp>; its card is
`data/README.md`.

## Source

- Landing page with the edition, the update history, the conditions of use
  and the documents: <https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000087.html>
- Download table, one zip per prefecture and format:
  <https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000182.html>

The pages hold one edition (データ作成年度, now 令和7年度 = `fy2025`) and MLIT
corrects its zips in place. An edition is kept under its own directory;
within it the files follow the source.

## Licence

MLIT's site terms (<https://www.mlit.go.jp/link.html>) apply the Public Data
License 1.0 (公共データ利用規約 第1.0版, PDL1.0), compatible with CC BY 4.0:
reuse, including commercial use, is allowed with credit and a note of any
modification. The landing page adds conditions of use that are disclaimers
(reference use only, approximate extents, no liability). The code here is MIT.

## Usage

```sh
uv run python scripts/01_download.py            # the full collection (below)
uv run python scripts/03_export_parquet.py      # one GeoParquet per layer
uv run python scripts/02_verify.py              # check the zips, and the Parquet against them
uv run python src/publish.py                    # dry run: list what would be uploaded
uv run python src/publish.py --push             # upload to huggingface.co/datasets/yuiseki/mlit-toshi-keikaku-jp
uv run python -m pytest                         # unit tests
uv run ruff check scripts tests src
```

### The full collection

```sh
uv run python scripts/01_download.py
```

reads both pages, then fetches the 3 documents and the 141 zips (47
prefectures x Shapefile, CityGML, GeoJSON), about 2.03 GB, and saves the two
pages. Before fetching it asks the server for each file's size (one HEAD
request per file) and prints the estimate. Requests are sequential, at least
1 second apart, and back off on 429 and 503. About 300 requests in all; on
2026-10-06 it took about 13 minutes.

To fetch a slice, name formats, prefecture codes or `docs`:

```sh
uv run python scripts/01_download.py --only shp 31      # the Shapefile zip of Tottori
uv run python scripts/01_download.py --only docs
uv run python scripts/01_download.py --only geojson --limit 5
uv run python scripts/01_download.py --dry-run          # the estimate only
```

To resume, run the same command again: `MANIFEST.json` is written after
every file, and a file whose entry has the same URL and whose sha256 still
matches is skipped (a partial download stays as `.part` and is fetched
again). To follow MLIT's corrections, add `--refresh`: each listed file's
Content-Length and Last-Modified are compared with the manifest and what
changed is fetched again.

`03_export_parquet.py` extracts one prefecture zip at a time to
`data/work/`, reads every Shapefile with DuckDB's spatial extension and
writes `data/parquet/<edition>/<layer>.parquet` (GeoParquet, zstd, no bloom
filters), then deletes the extracted files. Column names are the DBF's;
types come from the names (`...Code` INTEGER, `FAR` and `BCR` DOUBLE, else
text), each cast guarded by a regular expression, and a value that does not
fit stops the run. Text is UTF-8 as every `.cpg` says (another code page
stops the run); geometry stays in JGD2011 (EPSG:6668), as the `.prj` says.

`02_verify.py` re-hashes every file against the manifest, tests every zip,
checks that the GeoJSON zips hold the same files and feature counts as the
Shapefile zips, prints the municipality list's counts beside the files, and
checks every Parquet against the Shapefiles, read with readers of its own:
row counts and order, every attribute value, every coordinate, column types,
the CRS, that a DuckDB without extensions opens the files, and no bloom
filters. It exits 1 on any failure.

## Layout

```
scripts/01_download.py        fetch the documents and zips the pages list
scripts/02_verify.py          re-hash and test every fetched file, check the Parquet
scripts/03_export_parquet.py  Shapefiles to GeoParquet, one file per layer
src/publish.py                upload to the Hugging Face Hub (dry run by default)
tests/                        unit tests; fixtures trimmed from the pages and one zip
data/README.md                the dataset card
data/LICENSE                  the licence and what the Parquet changes
data/provenance.yaml          source, edition, files, counts, checks
data/parquet/<edition>/       <layer>.parquet (not in git)
data/work/                    extracted Shapefiles while 03 runs (not in git)
data/raw/<edition>/           as served (not in git)
    MANIFEST.json             per file: url, bytes, sha256, last_modified,
                              fetched_at, label and correction note; and
                              what the pages state (edition, history, terms,
                              the list's counts per layer)
    docs/                     data definition, CityGML specification, list of municipalities
    pages/                    the landing page and the download table
    shp/ geojson/ citygml/    <JIS prefecture code>_<prefecture>.zip
```
