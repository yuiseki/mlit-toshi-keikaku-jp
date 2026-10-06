import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "publish", Path(__file__).parents[1] / "src" / "publish.py"
)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def _data(tmp_path, card_layers=("youto",), raw=b"x", manifest_raw=b"x"):
    d = tmp_path / "data"
    (d / "parquet" / "fy2025").mkdir(parents=True)
    (d / "parquet" / "fy2025" / "youto.parquet").write_bytes(b"PAR1")
    (d / "raw" / "fy2025" / "shp").mkdir(parents=True)
    (d / "raw" / "fy2025" / "shp" / "31_tottori.zip").write_bytes(raw)
    files = {"shp/31_tottori.zip": {"sha256": hashlib.sha256(manifest_raw).hexdigest()}}
    (d / "raw" / "fy2025" / "MANIFEST.json").write_text(json.dumps({"files": files}))
    card = "---\nconfigs:\n" + "".join(m.subset_entry("fy2025", t) for t in card_layers) + "---\n"
    (d / "README.md").write_text(card)
    for f in ("LICENSE", "provenance.yaml"):
        (d / f).write_text("x")
    return d


def test_collect_lists_card_parquet_and_raw(tmp_path):
    assert m.collect(_data(tmp_path)) == [
        "README.md", "LICENSE", "provenance.yaml", "parquet/fy2025/youto.parquet",
        "raw/fy2025/shp/31_tottori.zip", "raw/fy2025/MANIFEST.json",
    ]  # fmt: skip


def test_a_parquet_the_card_does_not_declare_stops_it(tmp_path):
    with pytest.raises(SystemExit, match="fy2025.youto"):
        m.collect(_data(tmp_path, card_layers=("tokei",)))


def test_a_raw_file_unlike_its_manifest_stops_it(tmp_path):
    with pytest.raises(SystemExit, match="raw/fy2025/shp/31_tottori.zip"):
        m.collect(_data(tmp_path, raw=b"changed"))


def test_the_default_repo():
    assert m.REPO == "yuiseki/mlit-toshi-keikaku-jp"
