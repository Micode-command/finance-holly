import re

import pandas as pd

from holly.commentary import balance_sheet, macro_commentary, on_rrp
from holly.indicators import build_dataset


def test_every_note_is_bilingual(raw):
    notes = macro_commentary(build_dataset(raw))
    assert len(notes) >= 8
    for n in notes:
        assert n["zh"] and n["en"] and n["tone"] in {"good", "bad", "neutral"}
        assert n["en"].isascii() or "—" in n["en"]  # 英文評語不夾中文


def _weekly_dataset(col, values):
    idx = pd.date_range("2025-01-01", periods=len(values), freq="W-WED")
    raw = pd.DataFrame({col: values, "SPY": 1.0}, index=idx)
    return build_dataset(raw)


def test_qt_detected_and_chinese_units_converted():
    # 每週少 100 億 (10B) → 每月約 -43B → QT；中文應顯示「億」= B × 10
    ds = _weekly_dataset("Total_Assets", [7_000_000 - 10_000 * i for i in range(30)])
    note = balance_sheet(ds)
    assert note["topic"] == "QT 縮表" and note["tone"] == "bad"
    assert re.search(r"每月抽走約 4[23]\d 億美元", note["zh"])  # 約 43B = 430 億
    assert re.search(r"~\$4[23]B per month", note["en"])


def test_on_rrp_empty():
    ds = _weekly_dataset("ON_RRP", [50_000] * 20)  # 500 億美元
    note = on_rrp(ds)
    assert note["topic"] == "ON RRP 見底" and "500 億美元" in note["zh"] and "$50B" in note["en"]
