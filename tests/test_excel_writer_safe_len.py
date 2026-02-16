from __future__ import annotations

from scripts.era_extract.excel_writer import _safe_len


def test_safe_len_handles_common_types() -> None:
    assert _safe_len(1.23) == len("1.23")
    assert _safe_len(0) == len("0")
    assert _safe_len(None) == 0
    assert _safe_len(float("nan")) == 0
    assert _safe_len("abc") == 3
