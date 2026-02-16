from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def table_header_text_by_col(table: Any) -> dict[int, str]:
    # Build header (row 0) text per column; joins multi-cell headers.
    col_text: dict[int, list[str]] = {}
    for cell in getattr(table, "cells", []) or []:
        r = int(getattr(cell, "row_index", 0))
        c = int(getattr(cell, "column_index", 0))
        if r != 0:
            continue
        txt = (getattr(cell, "content", "") or "").strip()
        if not txt:
            continue
        col_text.setdefault(c, []).append(txt)
    return {c: " ".join(v).strip() for c, v in col_text.items()}


@dataclass(frozen=True)
class DetailTableMatch:
    table: Any
    cols_by_required_header_norm: dict[str, int]
    match_count: int


def find_detail_table(tables: list[Any], required_headers: list[str]) -> Optional[DetailTableMatch]:
    req = [_norm(x) for x in required_headers]
    best: Optional[DetailTableMatch] = None

    for t in tables:
        headers = table_header_text_by_col(t)
        norm_headers = {c: _norm(txt) for c, txt in headers.items()}

        cols: dict[str, int] = {}
        match_count = 0
        for want in req:
            found_col = None
            for c, htxt in norm_headers.items():
                if want and want in htxt:
                    found_col = c
                    break
            if found_col is not None:
                match_count += 1
                cols[want] = found_col

        if best is None or match_count > best.match_count:
            best = DetailTableMatch(table=t, cols_by_required_header_norm=cols, match_count=match_count)

    if best is None or best.match_count < len(req):
        return None
    return best

