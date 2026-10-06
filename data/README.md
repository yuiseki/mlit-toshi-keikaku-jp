---
license: cc-by-4.0
language:
- ja
- en
pretty_name: MLIT urban planning decision GIS data (都市計画決定GISデータ)
tags:
- geospatial
- geoparquet
- gis
- japan
- urban-planning
- zoning
- land-use
size_categories:
- 100K<n<1M
configs:
- config_name: 'fy2025.youto'
  data_files: parquet/fy2025/youto.parquet
  default: true
- config_name: 'fy2025.douro'
  data_files: parquet/fy2025/douro.parquet
- config_name: 'fy2025.kouen'
  data_files: parquet/fy2025/kouen.parquet
- config_name: 'fy2025.koudoti'
  data_files: parquet/fy2025/koudoti.parquet
- config_name: 'fy2025.chikukei'
  data_files: parquet/fy2025/chikukei.parquet
- config_name: 'fy2025.tkbt'
  data_files: parquet/fy2025/tkbt.parquet
- config_name: 'fy2025.tokei'
  data_files: parquet/fy2025/tokei.parquet
- config_name: 'fy2025.bouka'
  data_files: parquet/fy2025/bouka.parquet
- config_name: 'fy2025.ritteki'
  data_files: parquet/fy2025/ritteki.parquet
- config_name: 'fy2025.senbiki'
  data_files: parquet/fy2025/senbiki.parquet
- config_name: 'fy2025.tochiku'
  data_files: parquet/fy2025/tochiku.parquet
- config_name: 'fy2025.fuuchichiku'
  data_files: parquet/fy2025/fuuchichiku.parquet
- config_name: 'fy2025.tokuteiyouto'
  data_files: parquet/fy2025/tokuteiyouto.parquet
- config_name: 'fy2025.koudori'
  data_files: parquet/fy2025/koudori.parquet
- config_name: 'fy2025.tokuryoku'
  data_files: parquet/fy2025/tokuryoku.parquet
- config_name: 'fy2025.ryokukachiiki'
  data_files: parquet/fy2025/ryokukachiiki.parquet
- config_name: 'fy2025.toshisaisei'
  data_files: parquet/fy2025/toshisaisei.parquet
- config_name: 'fy2025.rekifuu'
  data_files: parquet/fy2025/rekifuu.parquet
- config_name: 'fy2025.soubou'
  data_files: parquet/fy2025/soubou.parquet
- config_name: 'fy2025.jyuntoshi'
  data_files: parquet/fy2025/jyuntoshi.parquet
- config_name: 'fy2025.tokuteiyuudou'
  data_files: parquet/fy2025/tokuteiyuudou.parquet
- config_name: 'fy2025.tokuteibou'
  data_files: parquet/fy2025/tokuteibou.parquet
- config_name: 'fy2025.kyojyuchosei'
  data_files: parquet/fy2025/kyojyuchosei.parquet
- config_name: 'fy2025.tokureiyouseki'
  data_files: parquet/fy2025/tokureiyouseki.parquet
- config_name: 'fy2025.fukkousaiseikyoten'
  data_files: parquet/fy2025/fukkousaiseikyoten.parquet
- config_name: 'fy2025.kousoujyukyo'
  data_files: parquet/fy2025/kousoujyukyo.parquet
---

# mlit-toshi-keikaku-jp

The national edition of 都市計画決定GISデータ (urban planning decision GIS
data) that the City Bureau of Japan's Ministry of Land, Infrastructure,
Transport and Tourism (MLIT) publishes: the city planning decisions of about
1,400 municipalities, from use districts (用途地域) with their floor-area and
building-coverage ratios to planned roads, parks, district plans and
location normalisation plans. One GeoParquet subset per layer, beside the
zips MLIT serves in its three formats (Shapefile, GeoJSON, CityGML).

The edition here is 令和7年度 (fiscal year 2025), `fy2025`, first published
on 21 May 2026 and corrected in July 2026. The data comes under MLIT's site
terms, the Public Data License 1.0 (PDL1.0), compatible with CC BY 4.0 (see
Licence). It is a reference, not a legal record: MLIT says the extents are
approximate and may differ from the decisions themselves.

## Source

- Landing page, terms of use and update history:
  <https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000087.html>
- Download table (one zip per prefecture and format), reached from the
  landing page's button once the terms are ticked:
  <https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000182.html>
- Data definition for Shapefile and GeoJSON (データ定義書.pdf), CityGML
  specification (CityGML仕様書.pdf), and the list of municipalities and
  layers (公表自治体及び掲載データ一覧.xlsx, as of 1 July 2026), all linked
  from the landing page and kept under `raw/fy2025/docs/`.

What the landing page says about the edition, in its own words:

| | |
|---|---|
| 内容 (content) | 全国の都市計画決定情報のＧＩＳデータを整備したもの |
| データ作成年度 (edition) | 令和7年度 |
| 原典資料 (sources) | 地方公共団体等作成の都市計画総括図又はGISデータ、国土交通省作成の国土数値情報 |
| 更新履歴 (history) | 令和8年5月21日; 令和8年7月1日（シェープファイル形式・GeoJSONファイル形式　一部修正）; 令和8年7月2日（同）; 令和8年7月7日（CityGMLファイル形式　一部修正） |

Where a local government supplied GIS data, MLIT checked and restructured
it to its product specification; where none was supplied and nothing had
changed since 1 April 2019, MLIT used the 国土数値情報 (National Land
Numerical Information) data of 2018; otherwise it scanned, georeferenced and
digitised the paper master plan maps (都市計画総括図).

### Editions and corrections

The pages carry one edition only, and MLIT corrects it in place: the
download table marks a corrected zip "（R8.7.1修正）" and the zip keeps its
URL (Shapefile, CityGML) or gets a new one (GeoJSON). The Tokyo Shapefile
zip was replaced again on 17 July 2026 (Last-Modified) without a new entry
in the history. Earlier editions are not online; the PMTiles that UN Smart
Maps made in 2024 from an earlier edition use a different attribute schema
(`kubunID`, `YoutoID`, Japanese column names) from this one. So this
dataset follows the source: an edition lives under its own name (`fy2025`),
a correction replaces the file in place (the Hub's git history keeps the
earlier copy), and a new edition will be added beside this one.

## Subsets and columns

One subset per layer, `fy2025.<layer>`, at `parquet/fy2025/<layer>.parquet`,
made from the Shapefiles of all 47 prefectures (8,173 Shapefiles in all). The
layer is the suffix of MLIT's file names (`13101_youto.shp`).

| subset | layer | geometry | rows | municipalities | prefectures | null geometry | Parquet bytes |
|---|---|---|---:|---:|---:|---:|---:|
| `fy2025.douro` | 都市計画道路 planned roads and squares | LineString | 191,584 | 785 | 47 | 5,802 | 93,197,243 |
| `fy2025.youto` | 用途地域 use districts | Polygon | 102,159 | 1,215 | 47 | 0 | 134,497,731 |
| `fy2025.kouen` | 公園 parks, green spaces, cemeteries | Polygon | 41,161 | 716 | 47 | 0 | 20,511,679 |
| `fy2025.koudoti` | 高度地区 height control districts | Polygon | 18,461 | 214 | 31 | 1 | 27,053,687 |
| `fy2025.chikukei` | 地区計画 district plans | Polygon | 10,886 | 601 | 47 | 0 | 16,218,212 |
| `fy2025.tkbt` | 特別用途地区 special use districts | Polygon | 10,319 | 337 | 47 | 65 | 11,093,039 |
| `fy2025.tokei` | 都市計画区域 city planning areas | Polygon | 10,279 | 1,373 | 47 | 0 | 92,193,062 |
| `fy2025.bouka` | 防火地域・準防火地域 fire prevention districts | Polygon | 10,040 | 581 | 47 | 109 | 16,974,922 |
| `fy2025.ritteki` | 立地適正化計画 location normalisation plans | Polygon | 9,675 | 582 | 47 | 0 | 84,839,192 |
| `fy2025.senbiki` | 区域区分 urbanisation promotion / control areas | Polygon | 7,259 | 637 | 46 | 0 | 93,240,376 |
| `fy2025.tochiku` | 土地区画整理事業 land readjustment projects | Polygon | 6,522 | 485 | 47 | 0 | 13,224,888 |
| `fy2025.fuuchichiku` | 風致地区 scenic districts | Polygon | 2,155 | 185 | 45 | 0 | 9,101,739 |
| `fy2025.tokuteiyouto` | 特定用途制限地域 specified use restriction areas | Polygon | 1,639 | 77 | 30 | 0 | 9,538,034 |
| `fy2025.koudori` | 高度利用地区 high-level use districts | Polygon | 976 | 231 | 45 | 7 | 339,444 |
| `fy2025.tokuryoku` | 特別緑地保全地区 special green space conservation districts | Polygon | 687 | 80 | 18 | 0 | 686,020 |
| `fy2025.ryokukachiiki` | 緑化地域 greening areas | Polygon | 217 | 4 | 3 | 0 | 1,389,012 |
| `fy2025.toshisaisei` | 都市再生特別地区 special urban renaissance districts | Polygon | 95 | 14 | 13 | 0 | 26,857 |
| `fy2025.rekifuu` | 歴史的風土保存地区 historic landscape preservation districts | Polygon | 77 | 7 | 4 | 0 | 792,701 |
| `fy2025.soubou` | 航空機騒音障害防止地区 aircraft noise districts | Polygon | 51 | 5 | 1 | 0 | 45,800 |
| `fy2025.jyuntoshi` | 準都市計画区域 quasi city planning areas | Polygon | 41 | 25 | 12 | 0 | 1,270,638 |
| `fy2025.tokuteiyuudou` | 特定用途誘導地区 specified use inducement districts | Polygon | 29 | 6 | 6 | 0 | 43,696 |
| `fy2025.tokuteibou` | 特定防災街区整備地区 specified disaster-prevention block districts | Polygon | 14 | 8 | 3 | 0 | 11,279 |
| `fy2025.kyojyuchosei` | 居住調整地域 residence adjustment areas | Polygon | 4 | 1 | 1 | 0 | 55,297 |
| `fy2025.tokureiyouseki` | 特例容積率適用地区 special FAR districts | Polygon | 2 | 2 | 2 | 0 | 5,014 |
| `fy2025.fukkousaiseikyoten` | 一団地の復興再生拠点市街地形成施設 reconstruction base facilities | Polygon | 2 | 1 | 1 | 0 | 12,123 |
| `fy2025.kousoujyukyo` | 高層住居誘導地区 high-rise residential districts | Polygon | 1 | 1 | 1 | 0 | 3,465 |

424,335 rows in all. Columns, in order:

| column | type | |
|---|---|---|
| `source_file` | VARCHAR | added: the `.shp`'s path inside MLIT's zip, `<pref>_<name>/<citycode>_<name>/<citycode>_<layer>.shp` |
| `fid` | BIGINT | added: the record's position in that Shapefile, from 0; rows are in the order of `source_file`, `fid` |
| `YoutoName`, `TokeiName`, `AreaType`, `DistName`, `DistType`, `DouroType`, `ParkName`, `ParkType`, `FaciName`, ... | VARCHAR | name or kind of the district |
| `YoutoCode`, `TokeiCode`, `AreaCode`, `DistCode`, `DouroCode`, `ParkCode`, `FaciCode` | INTEGER | code of the kind, from the 都市計画データ標準製品仕様書 code lists (for example `YoutoCode` 1 to 13 in `youto` (in `tkbt` it is the kind of special use district), `AreaCode` 22 市街化区域 / 23 市街化調整区域, `DouroCode` 3011 road / 3023 square) |
| `FAR`, `BCR` (youto only) | DOUBLE | 容積率 and 建蔽率 in percent; text in the DBF (`"200.0"`) |
| `Pref`, `Cityname` | VARCHAR | prefecture and municipality |
| `Citycode` | VARCHAR | five-digit municipality code (JIS X 0402 without check digit), leading zero kept; equals the code in the file name in every row |
| `INDate`, `FNDate` | VARCHAR | date the plan first took effect, date of the last notice, as written |
| `ValidType` | VARCHAR | 決定 / 変更 / 廃止 per the definition; mostly empty |
| `Custodian` | VARCHAR | who decides the plan |
| `INNumber`, `FNNumber` | VARCHAR | notice numbers, first and last |
| `geometry` | GEOMETRY | the Shapefile's geometry, EPSG:6668 |

The attribute names are the DBF's own, as MLIT's data definition gives them;
they are the same across all files of a layer. A file without a column would
have NULL there. The type of a column comes from its name, never from
the DBF or from inference: names ending in `Code` are INTEGER, `FAR` and
`BCR` DOUBLE, all else text; a value that does not fit stopped the build.

### Coordinate reference system

Every `.prj` says `GEOGCS["GCS_JGD_2011",...]`: JGD2011 longitude and
latitude in degrees, EPSG:6668, which the data definition states too
("座標参照系：JGD2011 / (B,L)"). The GeoParquet metadata states EPSG:6668;
nothing is reprojected. The GeoJSON files name `urn:ogc:def:crs:EPSG::6668`;
the CityGML files use EPSG:6697 (JGD2011 with height).

```sql
-- DuckDB, straight off the Hub: floor-area ratios of the use districts of Chiyoda-ku
SELECT YoutoName, FAR, BCR, count(*)
FROM 'hf://datasets/yuiseki/mlit-toshi-keikaku-jp/parquet/fy2025/youto.parquet'
WHERE Citycode = '13101'
GROUP BY ALL ORDER BY FAR DESC;
```

```sql
-- the use district at a point (the spatial extension reads the geometry)
INSTALL spatial; LOAD spatial;
SELECT Cityname, YoutoName, FAR, BCR
FROM 'hf://datasets/yuiseki/mlit-toshi-keikaku-jp/parquet/fy2025/youto.parquet'
WHERE Citycode = '13101'
  AND ST_Contains(geometry, ST_Point(139.7671, 35.6812)::GEOMETRY('EPSG:6668'));
```

### The raw files

Under `raw/fy2025/`, byte for byte as served, with `MANIFEST.json` (URL,
bytes, sha256, Last-Modified, fetch time, the table's correction note, and
what the pages state, including the terms of use and the list's counts per
layer):

| path | files | bytes | |
|---|---:|---:|---|
| `shp/<code>_<pref>.zip` | 47 | 605,061,992 | Shapefile, UTF-8 (`.cpg`), the source of the Parquet |
| `geojson/<code>_<pref>.zip` | 47 | 785,216,248 | GeoJSON, the same 8,173 files and feature counts as the Shapefiles |
| `citygml/<code>_<pref>.zip` | 47 | 634,326,282 | CityGML 2.0 with i-UR 3.0 (urf), 7,380 `.gml` files; not converted |
| `docs/` | 3 | 817,199 | data definition, CityGML specification, list of municipalities |
| `pages/` | 2 | 41,408 | the landing page and the download table as fetched |

## Things to know

- Coverage is what local governments supplied, not every decision. The
  list of municipalities marks, per layer, 〇 data, × none, － no such
  decision; it is dated 1 July 2026 and does not match the files exactly:
  for `douro` it marks 834 municipalities 〇 and 785 have a file, for
  `kouen` 762 and 716, for `chikukei` 644 and 601; for `tokuryoku` it marks
  16 and 80 have a file. Count from the data, not from the list.
- Null geometries: the Shapefile records have a null shape in 5,802 rows of
  `douro` (three municipalities), 109 of `bouka`, 65 of `tkbt`, 7 of
  `koudori` and 1 of `koudoti`. They keep their attributes.
- `youto` has six rows with `YoutoCode` 0 and `YoutoName` 調整 (Chigasaki),
  a code the definition does not list. `ritteki` has `AreaCode` 0 for the
  plan area itself (立地適正化計画区域), as the definition says.
- `FAR` is NULL in 8,561 `youto` rows and `BCR` in 8,548.
- Dates are free text in many forms: `昭和48年12月25日`, `S43.3.13`,
  `1937-12-19`, `2024/03/29`, `H25.04.26`, full-width digits, sometimes with
  the notice number appended (`平成26年9月30日 県告示第624号`). Most rows have none (`INDate` is NULL in
  101,092 of 102,159 `youto` rows).
- `Custodian` mixes names (`都城市`), `国`, and codes such as `3`.
- 539 text values hold line breaks (CR, LF) inside them; they are kept as
  they are. No text value starts with a space.
- Some producers wrote text fields (`ValidType`, `INDate`, `INNumber`,
  `Custodian`, ...) as numeric DBF fields filled with `*`, the DBF's null.
  They are NULL here; the build checked that they held nothing else.
- The GeoJSON zips hold exactly the same features as the Shapefile zips
  (same files, same counts), so only the Shapefiles were converted.

## Checked before upload

`scripts/02_verify.py` in the source repository checks:

- every raw file against `MANIFEST.json` (bytes and sha256); every zip and
  the xlsx pass `zipfile.testzip`; the PDFs are PDFs
- every Shapefile has `.dbf`, `.shx`, `.prj` and a `.cpg` saying UTF-8, and
  as many `.shx` records as the DBF header says
- every GeoJSON zip holds the same files as the Shapefile zip of its
  prefecture, with as many features (read with the json module) and the CRS
  EPSG:6668
- every layer's Parquet has as many rows as its DBFs, in their order, with
  the columns and types the rules give
- every attribute value of every record (4,967,475 values) equals the DBF,
  read with a reader of its own (not GDAL), as strict UTF-8
- every geometry has the bytes of the x and y of its `.shp` record, part by
  part; null shapes are the NULL geometries
- `Citycode` equals the code in the file name in every row
- the GeoParquet 1.0.0 metadata states EPSG:6668; a DuckDB without the
  spatial extension opens every file; no bloom filters

## Licence

MLIT's landing page gives no licence of its own; it sets conditions of use
(このデータの使用許諾条件) that a visitor ticks before the download button
works. They are disclaimers and notes, not restrictions on reuse:

> ・掲載データは、市町村又は都道府県から提出されたGISデータや総括図等の資料を用いて、国土交通省都市局都市計画課において整備したものです。
> ・掲載データは、建築確認申請や不動産重要事項説明等の手続に用いることを保証するものではなく、参考情報として利用を想定しています。
> ・掲載データに含まれる地区・地域の範囲は、概ねの位置を示すものであり、実際の都市計画の決定範囲等と異なる場合があります。
> ・地方公共団体がGISデータを保有していない、あるいはGISデータとして公表できないといった理由から、都市計画決定があっても本サイトに掲載されていないデータがあります。
> ・掲載データは、当該自治体の都市計画等の情報全てではないことがあります。
> ・都市計画区域ポリゴンを、行政区域界、市街化区域界、市街化調整区域界から作成している自治体が一部に含まれております。
> ・掲載データは、最新のものではないことがあります。掲載データの時点については、上欄の「公表自治体及び掲載データ一覧.xlsx」を参考にしてください。
> ・掲載データについてのお問い合わせは、国土交通省都市局都市計画課都市計画調査室までお願いします。
> ・最新の正確な都市計画決定情報が必要な場合は、該当する地方公共団体の担当課までお問合せください。
> ・国及び原典データを提供した地方公共団体は、利用者が掲載データを用いて行う一切の行為（コンテンツを編集・加工等した情報を利用することを含む。）及び掲載データの利用によって発生した直接または間接の損失、損害等について、何ら責任を負うものではありません。

(In short: MLIT's City Planning Division compiled the data from material
the municipalities and prefectures supplied; it is for reference and is not
guaranteed for building permits or real-estate disclosures; extents are
approximate; some decisions are missing or not current; for exact and
current information ask the local government; the State and the local
governments accept no liability for any use, including of edited data.)

The reuse terms are MLIT's site terms, リンク・著作権・免責事項
(<https://www.mlit.go.jp/link.html>, read on 2026-10-06):

> 国土交通省ウェブサイトで掲載・発信している情報（以下「コンテンツ」といいます。）の著作権は、特記されていない限り国土交通省に帰属し、権利表記の記載がない限り「公共データ利用規約（第1.0版）」（PDL1.0）に準拠した利用条件の下で、利用することができます。

> ア　コンテンツを利用する際は出典を記載してください。（略）
> イ　コンテンツを編集・加工等して利用する場合は、上記出典とは別に、編集・加工等を行ったことを記載してください。なお、編集・加工した情報を、あたかも国（又は府省等）が作成したかのような態様で公表・利用してはいけません。

(Unless stated otherwise, MLIT holds the copyright of its site's content,
which may be used under PDL1.0. Credit the source; when editing, say so
separately, and do not present the result as made by the State.)

The list of content under other rules
(<https://www.mlit.go.jp/page/kanbo01_hy_003657.html>) names the 国土数値情報
download service and others, not this data. The site terms point out the
Survey Act (測量法) for GSI's basic survey results; the data pages carry no
Survey Act notice and do not present this data as survey results. PDL1.0
is compatible with CC BY 4.0, hence `cc-by-4.0` above. Credit, for example:

    出典：「都市計画決定GISデータ」（国土交通省）
    （https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000087.html）を加工して作成

The same data is also distributed as the 国土数値情報 dataset
都市計画決定情報 (A55, <https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A55-2024.html>),
which says it was edited from this 都市計画決定GISデータ and licenses it as
"オープンデータ (CC_BY_4.0)" with no restriction noted; the latest A55 edition
is FY2024, one year older than this one.

One point is not settled. Where a municipality provided no GIS data and
made no change after 1 April 2019, MLIT edited the 2018 国土数値情報. The
older 国土数値情報 zoning dataset (用途地域 A29, FY2019) carried
per-municipality conditions
(<https://nlftp.mlit.go.jp/ksj/gml/datalist/Situation_of_the_data_collection_RestrictedZoneData.pdf>:
of 1,213 municipalities, 176 conditional, among them 114 "再配信不可" (no
redistribution), and 56 "公開不可" (not to be published)). Matching that list
with MLIT's list of municipalities (`raw/fy2025/docs/001864274.xlsx`, titled
"オープンデータ化項目"), 22 municipalities that had a condition in A29 have
zoning here with a data date before April 2019, so their zoning may come from
the 2018 国土数値情報 (for example 土浦市, 阪南市, 高島市). The data has no
per-feature source column, so this cannot be checked feature by feature. MLIT
publishes this data under its site terms and the 国土数値情報 republishes it
as plain CC BY 4.0, and neither says that the A29 conditions carry over;
whether those municipalities agreed to lift them was not confirmed. If your
use depends on it, check with the municipality or MLIT.

The zips under `raw/` are MLIT's, byte for byte. What the Parquet changes is
listed in `LICENSE` beside this file. MLIT did not make the Parquet and has
not reviewed it; this dataset is not published by the Government of Japan.
