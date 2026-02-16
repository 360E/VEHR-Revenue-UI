from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from scripts.era_extract.docintel_client import create_document_intelligence_client
from scripts.era_extract.docintel_client import load_repo_dotenv
from scripts.era_extract.docintel_client import verify_env as verify_env
from scripts.era_extract.excel_writer import write_claim_lines_xlsx
from scripts.era_extract.table_selector import table_header_text_by_col


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _config_path() -> Path:
    return Path(__file__).resolve().with_name("config.json")


def _default_out_for(pdf_path: Path) -> Path:
    return _repo_root() / "outputs" / "eras" / f"{pdf_path.stem}__extracted.xlsx"


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _load_config() -> dict[str, Any]:
    return json.loads(_config_path().read_text(encoding="utf-8"))


def _debug_enabled() -> bool:
    val = (os.getenv("EXTRACT_DEBUG", "") or "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _emit_docintel_diag(result: Any, *, label: str = "DOCINTEL DIAG") -> None:
    if not _debug_enabled():
        return

    pages = list(getattr(result, "pages", []) or [])
    tables = list(getattr(result, "tables", []) or [])
    print(f"{label}: Pages returned: {len(pages)}")
    print(f"{label}: Tables detected: {len(tables)}")

    page_table_counts: dict[int, int] = {}
    for t in tables:
        regions = list(getattr(t, "bounding_regions", []) or [])
        seen_pages: set[int] = set()
        for r in regions:
            pnum = int(getattr(r, "page_number", 0) or 0)
            if pnum > 0:
                seen_pages.add(pnum)
        if not seen_pages:
            # Unknown page assignment; keep table in summary without PHI.
            page_table_counts[0] = page_table_counts.get(0, 0) + 1
        else:
            for pnum in seen_pages:
                page_table_counts[pnum] = page_table_counts.get(pnum, 0) + 1

    for p in pages:
        pnum = int(getattr(p, "page_number", 0) or 0)
        if pnum > 0:
            print(f"{label}: Page {pnum}: {page_table_counts.get(pnum, 0)} tables")
    if page_table_counts.get(0):
        print(f"{label}: Page ?: {page_table_counts.get(0, 0)} tables")

    for i, t in enumerate(tables[:100], start=1):
        # Cap detailed table lines to keep logs readable on very large files.
        rc = int(getattr(t, "row_count", 0) or 0)
        cc = int(getattr(t, "column_count", 0) or 0)
        regions = list(getattr(t, "bounding_regions", []) or [])
        pnum = int(getattr(regions[0], "page_number", 0) or 0) if regions else 0
        page_label = str(pnum) if pnum > 0 else "?"
        print(f"{label}: Table {i}: page={page_label} rows={rc} cols={cc}")
    if len(tables) > 100:
        print(f"{label}: Table details truncated at 100 of {len(tables)}")

    if len(pages) <= 2 or len(tables) <= 2:
        print(
            f"{label}: WARNING unexpectedly low result size "
            f"(pages={len(pages)}, tables={len(tables)}). "
            "Check model_id/pages args and API response handling."
        )


@dataclass
class ParseStats:
    total_tables_iterated: int = 0
    tables_matched_schema: int = 0
    tables_skipped_no_header: int = 0
    tables_skipped_header_mismatch: int = 0
    tables_skipped_not_line_table: int = 0
    tables_skipped_parse_exception: int = 0
    claim_rows_extracted: int = 0
    line_rows_extracted: int = 0
    unique_claim_keys: int = 0
    key_collisions: int = 0

    def add(self, other: "ParseStats") -> None:
        self.total_tables_iterated += other.total_tables_iterated
        self.tables_matched_schema += other.tables_matched_schema
        self.tables_skipped_no_header += other.tables_skipped_no_header
        self.tables_skipped_header_mismatch += other.tables_skipped_header_mismatch
        self.tables_skipped_not_line_table += other.tables_skipped_not_line_table
        self.tables_skipped_parse_exception += other.tables_skipped_parse_exception
        self.claim_rows_extracted += other.claim_rows_extracted
        self.line_rows_extracted += other.line_rows_extracted
        self.key_collisions += other.key_collisions
        self.unique_claim_keys = max(self.unique_claim_keys, other.unique_claim_keys)


def _emit_parser_diag(stats: ParseStats, *, label: str = "PARSER DIAG") -> None:
    if not _debug_enabled():
        return
    print(f"{label}: Tables iterated: {stats.total_tables_iterated}")
    print(f"{label}: Tables matched schema: {stats.tables_matched_schema}")
    print(f"{label}: Skipped no header: {stats.tables_skipped_no_header}")
    print(f"{label}: Skipped header mismatch: {stats.tables_skipped_header_mismatch}")
    print(f"{label}: Skipped not line table: {stats.tables_skipped_not_line_table}")
    print(f"{label}: Skipped parse exception: {stats.tables_skipped_parse_exception}")
    print(f"{label}: Claim rows extracted: {stats.claim_rows_extracted}")
    print(f"{label}: Line rows extracted: {stats.line_rows_extracted}")
    print(f"{label}: Unique claim keys: {stats.unique_claim_keys}")
    print(f"{label}: Key collisions: {stats.key_collisions}")


def _iter_kvpairs(result: Any):
    for kv in getattr(result, "key_value_pairs", []) or []:
        key = getattr(kv, "key", None)
        val = getattr(kv, "value", None)
        ktxt = (getattr(key, "content", "") or "").strip()
        vtxt = (getattr(val, "content", "") or "").strip()
        if ktxt or vtxt:
            yield ktxt, vtxt


def _extract_patient_fields(result: Any, cfg: dict[str, Any]) -> tuple[str, str]:
    name_hints = [h.lower() for h in (cfg.get("patient_name_key_hints") or [])]
    id_hints = [h.lower() for h in (cfg.get("patient_id_key_hints") or [])]

    patient_name = ""
    patient_id = ""

    for k, v in _iter_kvpairs(result):
        nk = _norm(k)
        if not patient_name and any(h in nk for h in name_hints):
            patient_name = v.strip()
        if not patient_id and any(h in nk for h in id_hints):
            patient_id = v.strip()
        if patient_name and patient_id:
            return patient_name, patient_id

    # Fallback: regex over full OCR content. This is intentionally conservative.
    content = (getattr(result, "content", "") or "").strip()
    if content:
        m = re.search(r"(?im)^\s*patient\s+name\s*[:\-]?\s*(.+?)\s*$", content)
        if m:
            patient_name = patient_name or m.group(1).strip()
        m = re.search(r"(?im)^\s*patient\s+id\s*[:\-]?\s*([A-Za-z0-9\-]+)\s*$", content)
        if m:
            patient_id = patient_id or m.group(1).strip()

    return patient_name, patient_id


def _cell_text_grid(table: Any) -> list[list[str]]:
    row_count = int(getattr(table, "row_count", 0) or 0)
    col_count = int(getattr(table, "column_count", 0) or 0)
    grid = [["" for _ in range(col_count)] for _ in range(row_count)]
    for cell in getattr(table, "cells", []) or []:
        r = int(getattr(cell, "row_index", 0))
        c = int(getattr(cell, "column_index", 0))
        txt = (getattr(cell, "content", "") or "").strip()
        if 0 <= r < row_count and 0 <= c < col_count and txt:
            if not grid[r][c]:
                grid[r][c] = txt
    return grid


def _pick_modifier_units_col(table: Any, required_cols: set[int], hints: list[str], header_by_col: dict[int, str]) -> Optional[int]:
    norm_hints = [_norm(h) for h in hints]
    for c, hdr in header_by_col.items():
        if c in required_cols:
            continue
        nh = _norm(hdr)
        if any(h in nh for h in norm_hints):
            return c
    return None


def _analyze_with_retries(client: Any, model_id: str, pdf_path: Path, pages: Optional[str] = None) -> Any:
    max_attempts = int(os.getenv("AZURE_DOCINTEL_RETRY_ATTEMPTS", "4") or "4")
    base_sleep = float(os.getenv("AZURE_DOCINTEL_RETRY_BASE_SECONDS", "2") or "2")
    attempt = 0
    while True:
        attempt += 1
        try:
            with pdf_path.open("rb") as f:
                kwargs = {"model_id": model_id, "body": f}
                if pages:
                    kwargs["pages"] = pages
                poller = client.begin_analyze_document(**kwargs)
                return poller.result()
        except Exception:
            if attempt >= max_attempts:
                raise
            sleep_s = base_sleep * (2 ** (attempt - 1))
            print(
                f"[era_extract] analyze attempt {attempt}/{max_attempts} failed"
                + (f" (pages={pages})" if pages else "")
                + f"; retrying in {sleep_s:.1f}s"
            )
            time.sleep(sleep_s)


def _build_page_ranges(total_pages: int, chunk_size: int) -> list[str]:
    ranges: list[str] = []
    start = 1
    while start <= total_pages:
        end = min(total_pages, start + chunk_size - 1)
        ranges.append(f"{start}-{end}")
        start = end + 1
    return ranges


def _table_page_number(table: Any) -> int:
    regions = list(getattr(table, "bounding_regions", []) or [])
    if not regions:
        return 0
    return int(getattr(regions[0], "page_number", 0) or 0)


def _extract_rows_from_tables(
    tables: list[Any],
    *,
    required_headers: list[str],
    cfg: dict[str, Any],
    patient_name: str,
    patient_id: str,
) -> tuple[list[dict[str, Any]], ParseStats]:
    req_norm = [_norm(x) for x in required_headers]
    seen_claim_keys: set[str] = set()
    seen_line_keys: set[tuple[str, str, str, str, str]] = set()
    stats = ParseStats()
    rows_out: list[dict[str, Any]] = []

    for t_idx, table in enumerate(tables, start=1):
        stats.total_tables_iterated += 1
        page_num = _table_page_number(table)
        header_by_col = table_header_text_by_col(table)
        if not header_by_col:
            stats.tables_skipped_no_header += 1
            continue

        norm_headers = {c: _norm(txt) for c, txt in header_by_col.items()}
        cols: dict[str, int] = {}
        for want in req_norm:
            found_col = None
            for c, htxt in norm_headers.items():
                if want and want in htxt:
                    found_col = c
                    break
            if found_col is not None:
                cols[want] = found_col

        if len(cols) < len(req_norm):
            stats.tables_skipped_header_mismatch += 1
            continue

        stats.tables_matched_schema += 1
        try:
            line_ctrl_col = cols[req_norm[0]]
            dos_col = cols[req_norm[1]]
            charge_col = cols[req_norm[2]]
            payment_col = cols[req_norm[3]]

            modifier_col = _pick_modifier_units_col(
                table,
                required_cols={line_ctrl_col, dos_col, charge_col, payment_col},
                hints=list(cfg.get("modifier_units_header_hints") or []),
                header_by_col=header_by_col,
            )
            if modifier_col is None:
                for c in sorted(header_by_col.keys()):
                    if c not in {line_ctrl_col, dos_col, charge_col, payment_col}:
                        modifier_col = c
                        break
            if modifier_col is None:
                stats.tables_skipped_not_line_table += 1
                continue

            grid = _cell_text_grid(table)
            rows_before = len(rows_out)
            for r in range(1, len(grid)):
                row = grid[r]
                if not any(x.strip() for x in row):
                    continue
                claim_id = row[line_ctrl_col].strip() if line_ctrl_col < len(row) else ""
                dos = row[dos_col].strip() if dos_col < len(row) else ""
                modifier_units = row[modifier_col].strip() if modifier_col < len(row) else ""
                charge = row[charge_col].strip() if charge_col < len(row) else ""
                payment = row[payment_col].strip() if payment_col < len(row) else ""
                if not claim_id and not (dos or charge or payment):
                    continue

                # Collision guard for key-based pipelines.
                line_key = (claim_id, dos, modifier_units, charge, payment)
                if line_key in seen_line_keys:
                    stats.key_collisions += 1
                else:
                    seen_line_keys.add(line_key)

                if claim_id:
                    seen_claim_keys.add(claim_id)

                rows_out.append(
                    {
                        "Patient Name": patient_name,
                        "Patient ID": patient_id,
                        "Claim Line ID": claim_id,
                        "Dates of Service": dos,
                        "Modifier/Units": modifier_units,
                        "Charge": charge,
                        "Payment": payment,
                    }
                )

            table_rows = len(rows_out) - rows_before
            if _debug_enabled():
                print(
                    f"PARSER DIAG: Table {t_idx} page={page_num or '?'} "
                    f"matched schema; extracted_rows={table_rows}"
                )
            if table_rows == 0:
                stats.tables_skipped_not_line_table += 1
        except Exception:
            stats.tables_skipped_parse_exception += 1
            if _debug_enabled():
                print(f"PARSER DIAG: Table {t_idx} page={page_num or '?'} parse exception")

    stats.line_rows_extracted = len(rows_out)
    stats.claim_rows_extracted = len(rows_out)
    stats.unique_claim_keys = len(seen_claim_keys)
    return rows_out, stats


def extract_era_lines(pdf_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = _load_config()
    required_headers = cfg.get("detail_table_required_headers") or []
    if not required_headers:
        raise RuntimeError("config.json missing detail_table_required_headers")

    load_repo_dotenv()
    model_id = (os.getenv("AZURE_DOCINTEL_MODEL") or "prebuilt-layout").strip() or "prebuilt-layout"
    chunk_size = int(os.getenv("AZURE_DOCINTEL_PAGE_CHUNK_SIZE", "0") or "0")

    client, doc_cfg = create_document_intelligence_client()
    overall_stats = ParseStats()
    all_rows: list[dict[str, Any]] = []
    patient_name = ""
    patient_id = ""

    if chunk_size > 0:
        # First pass to discover total pages, then chunk for resiliency on large PDFs.
        full = _analyze_with_retries(client, model_id, pdf_path, pages=None)
        _emit_docintel_diag(full, label="DOCINTEL DIAG (full)")
        pages = list(getattr(full, "pages", []) or [])
        total_pages = len(pages)
        if total_pages <= chunk_size:
            patient_name, patient_id = _extract_patient_fields(full, cfg)
            rows, stats = _extract_rows_from_tables(
                list(getattr(full, "tables", []) or []),
                required_headers=list(required_headers),
                cfg=cfg,
                patient_name=patient_name,
                patient_id=patient_id,
            )
            all_rows.extend(rows)
            overall_stats.add(stats)
            _emit_parser_diag(stats, label="PARSER DIAG (full)")
        else:
            page_ranges = _build_page_ranges(total_pages, chunk_size)
            print(f"[era_extract] large PDF detected ({total_pages} pages), chunking into {len(page_ranges)} calls")
            for i, rng in enumerate(page_ranges, start=1):
                t0 = time.perf_counter()
                chunk = _analyze_with_retries(client, model_id, pdf_path, pages=rng)
                dt = time.perf_counter() - t0
                print(f"[era_extract] chunk {i}/{len(page_ranges)} pages={rng} done in {dt:.1f}s")
                _emit_docintel_diag(chunk, label=f"DOCINTEL DIAG (chunk {i}/{len(page_ranges)})")
                p_name, p_id = _extract_patient_fields(chunk, cfg)
                if not patient_name and p_name:
                    patient_name = p_name
                if not patient_id and p_id:
                    patient_id = p_id

                chunk_rows, chunk_stats = _extract_rows_from_tables(
                    list(getattr(chunk, "tables", []) or []),
                    required_headers=list(required_headers),
                    cfg=cfg,
                    patient_name=patient_name,
                    patient_id=patient_id,
                )
                all_rows.extend(chunk_rows)
                overall_stats.add(chunk_stats)
                _emit_parser_diag(chunk_stats, label=f"PARSER DIAG (chunk {i}/{len(page_ranges)})")
                if _debug_enabled():
                    chunk_pages = len(list(getattr(chunk, "pages", []) or []))
                    chunk_tables = len(list(getattr(chunk, "tables", []) or []))
                    print(
                        f"PARSER DIAG (chunk {i}/{len(page_ranges)}): pages={chunk_pages} "
                        f"tables={chunk_tables} extracted_rows={len(chunk_rows)} cumulative_rows={len(all_rows)}"
                    )
    else:
        result = _analyze_with_retries(client, model_id, pdf_path, pages=None)
        _emit_docintel_diag(result)
        patient_name, patient_id = _extract_patient_fields(result, cfg)
        rows, stats = _extract_rows_from_tables(
            list(getattr(result, "tables", []) or []),
            required_headers=list(required_headers),
            cfg=cfg,
            patient_name=patient_name,
            patient_id=patient_id,
        )
        all_rows.extend(rows)
        overall_stats.add(stats)
        _emit_parser_diag(stats, label="PARSER DIAG (full)")

    if not all_rows:
        return (
            [],
            {
                "patient_name": patient_name,
                "patient_id": patient_id,
                "table_count": overall_stats.total_tables_iterated,
                "error": "No ERA detail rows found",
            },
        )

    meta = {
        "model_id": model_id,
        "patient_name": patient_name,
        "patient_id": patient_id,
        "table_count": overall_stats.total_tables_iterated,
        "extracted_lines": len(all_rows),
        "unique_claim_keys": overall_stats.unique_claim_keys,
        "tables_matched_schema": overall_stats.tables_matched_schema,
        "tables_skipped_no_header": overall_stats.tables_skipped_no_header,
        "tables_skipped_header_mismatch": overall_stats.tables_skipped_header_mismatch,
        "tables_skipped_not_line_table": overall_stats.tables_skipped_not_line_table,
        "tables_skipped_parse_exception": overall_stats.tables_skipped_parse_exception,
        "key_collisions": overall_stats.key_collisions,
    }
    _emit_parser_diag(overall_stats, label="PARSER DIAG (overall)")
    return all_rows, meta


def run(pdf_path: Path, out_path: Optional[Path] = None) -> Path:
    pdf_path = pdf_path.resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(str(pdf_path))
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file, got: {pdf_path.name}")

    out_path = (out_path or _default_out_for(pdf_path)).resolve()

    verify_env()
    model_id = (os.getenv("AZURE_DOCINTEL_MODEL") or "prebuilt-layout").strip() or "prebuilt-layout"
    print(f"[era_extract] analyzing: {pdf_path.name} (model={model_id})")
    t0 = time.perf_counter()
    lines, meta = extract_era_lines(pdf_path)

    if not lines:
        print(
            "[era_extract] No ERA detail table found — check scripts/era_extract/config.json keywords. "
            f"(tables_detected={meta.get('table_count')})"
        )
    else:
        print(f"[era_extract] extracted_lines={meta.get('extracted_lines')}")

    write_claim_lines_xlsx(out_path, lines)
    elapsed = time.perf_counter() - t0
    print(f"[era_extract] wrote: {out_path} (elapsed={elapsed:.1f}s)")
    return out_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Extract ERA patient + claim lines to Excel (sheet: ClaimLines).")
    p.add_argument("--pdf", required=True, help="Path to an ERA PDF")
    p.add_argument("--out", required=False, help="Output .xlsx path (default: outputs/eras/<pdf>__extracted.xlsx)")
    p.add_argument("--save-analyze-json", required=False, help="Save full Azure DI JSON response to this path")
    p.add_argument(
        "--save-content-txt",
        required=False,
        help="Save analyzeResult.content text to this path (only when --save-analyze-json is used)",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    out_path = run(Path(args.pdf), Path(args.out) if args.out else None)
    if args.save_analyze_json:
        # Re-run analysis with a single call to capture the raw response for offline reuse.
        pdf_path = Path(args.pdf).resolve()
        if not pdf_path.exists():
            raise FileNotFoundError(str(pdf_path))

        verify_env()
        model_id = (os.getenv("AZURE_DOCINTEL_MODEL") or "prebuilt-layout").strip() or "prebuilt-layout"
        client, _ = create_document_intelligence_client()
        result = _analyze_with_retries(client, model_id, pdf_path, pages=None)

        raw = None
        if hasattr(result, "to_dict"):
            raw = result.to_dict()
        if raw is None:
            try:
                raw = json.loads(json.dumps(result, default=lambda o: o.__dict__))
            except Exception:
                raw = {"content": getattr(result, "content", "")}

        save_path = Path(args.save_analyze_json)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

        if args.save_content_txt:
            content = ""
            if isinstance(raw, dict):
                analyze = raw.get("analyzeResult")
                if isinstance(analyze, dict):
                    content = analyze.get("content") or ""
                if not content:
                    content = raw.get("content") or ""
            Path(args.save_content_txt).parent.mkdir(parents=True, exist_ok=True)
            Path(args.save_content_txt).write_text(content, encoding="utf-8")

        print(f"[era_extract] saved analyze JSON: {save_path}")
        if args.save_content_txt:
            print(f"[era_extract] saved content text: {Path(args.save_content_txt)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
