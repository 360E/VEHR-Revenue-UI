from __future__ import annotations

import argparse
import json
import mimetypes
import platform
import resource
import statistics
import sys
import threading
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter
from urllib import error, request
from urllib.parse import urlparse


def _percentile(values: list[int], pct: int) -> int:
    if not values:
        return 0
    if len(values) == 1:
        return values[0]
    rank = (len(values) - 1) * (pct / 100)
    lower = int(rank)
    upper = min(lower + 1, len(values) - 1)
    frac = rank - lower
    ordered = sorted(values)
    return int(ordered[lower] + (ordered[upper] - ordered[lower]) * frac)


def _rss_mb() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if platform.system() == "Darwin":
        return value / (1024.0 * 1024.0)
    return value / 1024.0


def _json_request(method: str, url: str, *, token: str | None = None, body: bytes | None = None, content_type: str | None = None):
    req = request.Request(url, method=method.upper(), data=body)
    req.add_header("Accept", "application/json")
    req.add_header("x-request-id", f"load-{uuid.uuid4().hex}")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with request.urlopen(req) as response:  # noqa: S310
            payload_raw = response.read().decode("utf-8")
            payload = json.loads(payload_raw) if payload_raw else {}
            return response.status, payload
    except error.HTTPError as exc:
        payload_raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(payload_raw) if payload_raw else {}
        except json.JSONDecodeError:
            payload = {"error": "invalid_json_response"}
        return exc.code, payload


def _login(base_url: str, *, email: str, password: str) -> str | None:
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    status, data = _json_request(
        "POST",
        f"{base_url.rstrip('/')}/api/v1/auth/login",
        body=payload,
        content_type="application/json",
    )
    if status != 200 or not isinstance(data, dict):
        return None
    token = data.get("access_token")
    return token if isinstance(token, str) and token else None


def _multipart_pdf(file_path: Path) -> tuple[bytes, str]:
    boundary = f"----vehr-era-load-{uuid.uuid4().hex}"
    ctype = mimetypes.guess_type(str(file_path))[0] or "application/pdf"
    content = file_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="{file_path.name}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
    return body, boundary


def _extract_stage_durations(logs: list[dict]) -> dict[str, int]:
    stage_durations: dict[str, int] = {}
    for row in logs:
        stage = row.get("stage")
        message = row.get("message")
        if not isinstance(stage, str) or not isinstance(message, str):
            continue
        for part in message.split(";"):
            key, _, value = part.strip().partition("=")
            if key == "duration_ms" and value.isdigit():
                stage_durations[stage.lower()] = int(value)
    return stage_durations


def _run_one(base_url: str, *, token: str, pdf_path: Path) -> dict:
    started = perf_counter()
    body, boundary = _multipart_pdf(pdf_path)
    upload_status, upload_payload = _json_request(
        "POST",
        f"{base_url.rstrip('/')}/api/v1/revenue/era-pdfs/upload",
        token=token,
        body=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    duration_ms = int((perf_counter() - started) * 1000)
    if upload_status != 200 or not isinstance(upload_payload, list) or not upload_payload:
        return {
            "ok": False,
            "error_code": "upload_failed",
            "request_id": "-",
            "duration_ms": duration_ms,
            "stage_durations": {},
            "db_invariant_ok": False,
        }

    row = upload_payload[0] if isinstance(upload_payload[0], dict) else {}
    era_file_id = row.get("id") if isinstance(row.get("id"), str) else None
    if not era_file_id:
        return {
            "ok": False,
            "error_code": "missing_era_file_id",
            "request_id": "-",
            "duration_ms": duration_ms,
            "stage_durations": {},
            "db_invariant_ok": False,
        }

    process_started = perf_counter()
    process_status, process_payload = _json_request(
        "POST",
        f"{base_url.rstrip('/')}/api/v1/revenue/era-pdfs/{era_file_id}/process",
        token=token,
    )
    process_duration_ms = int((perf_counter() - process_started) * 1000)
    request_id = process_payload.get("request_id") if isinstance(process_payload, dict) else None

    debug_status, debug_payload = _json_request(
        "GET",
        f"{base_url.rstrip('/')}/api/v1/revenue/era-pdfs/{era_file_id}/debug",
        token=token,
    )
    row_counts = {}
    latest_logs = []
    if debug_status == 200 and isinstance(debug_payload, dict):
        row_counts = debug_payload.get("row_counts") if isinstance(debug_payload.get("row_counts"), dict) else {}
        latest_logs = debug_payload.get("latest_processing_logs") if isinstance(debug_payload.get("latest_processing_logs"), list) else []

    db_invariant_ok = True
    if process_status != 200:
        db_invariant_ok = (row_counts.get("claim_lines", 0) == 0) and (row_counts.get("work_items", 0) == 0)
    if process_status == 200:
        db_invariant_ok = row_counts.get("extract_results", 0) <= 1 and row_counts.get("structured_results", 0) <= 1

    error_code = None
    if process_status != 200 and isinstance(process_payload, dict):
        error_code = process_payload.get("error_code") or process_payload.get("detail", {}).get("error_code")

    return {
        "ok": process_status == 200,
        "error_code": error_code or "unknown_error",
        "request_id": request_id or "-",
        "duration_ms": process_duration_ms,
        "stage_durations": _extract_stage_durations(latest_logs),
        "db_invariant_ok": db_invariant_ok,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="load-test", description="ERA stress and concurrency runner")
    parser.add_argument("--dir", required=True, help="Directory of test PDF fixtures")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password", default="ChangeMeNow!")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--memory-ceiling-mb", type=float, default=1024.0)
    return parser


def _valid_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not _valid_base_url(args.base_url):
        print("error=invalid_base_url", file=sys.stderr)
        return 1
    pdf_dir = Path(args.dir).expanduser().resolve()
    if not pdf_dir.exists() or not pdf_dir.is_dir():
        print(f"error=invalid_dir path={pdf_dir}", file=sys.stderr)
        return 1
    pdfs = sorted(path for path in pdf_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf")
    if not pdfs:
        print("error=no_pdf_fixtures", file=sys.stderr)
        return 1

    token = _login(args.base_url, email=args.email, password=args.password)
    if not token:
        print("error=login_failed", file=sys.stderr)
        return 1

    tasks: list[Path] = []
    for _ in range(max(args.iterations, 1)):
        tasks.extend(pdfs)

    failures_by_code: Counter[str] = Counter()
    stage_durations: dict[str, list[int]] = defaultdict(list)
    total_durations: list[int] = []
    results = {"ok": 0, "failed": 0}
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=max(args.workers, 1)) as pool:
        futures = [pool.submit(_run_one, args.base_url, token=token, pdf_path=path) for path in tasks]
        for future in as_completed(futures):
            try:
                outcome = future.result()
            except Exception as exc:
                print(f"failed error_code=load_runner_{type(exc).__name__} request_id=-", file=sys.stderr)
                return 1
            with lock:
                total_durations.append(outcome["duration_ms"])
                if outcome["ok"]:
                    results["ok"] += 1
                else:
                    results["failed"] += 1
                    failures_by_code[outcome["error_code"]] += 1
                    print(
                        f"failed error_code={outcome['error_code']} request_id={outcome['request_id']}",
                        file=sys.stderr,
                    )
                for stage, duration in outcome["stage_durations"].items():
                    stage_durations[stage].append(duration)
                if not outcome["db_invariant_ok"]:
                    print("db_invariant=failed", file=sys.stderr)
                    return 1

    max_memory = _rss_mb()
    if max_memory > args.memory_ceiling_mb:
        print(f"memory_ceiling_exceeded max_memory_mb={max_memory:.2f}", file=sys.stderr)
        return 1

    summary = {
        "success_rate": round(results["ok"] / len(tasks), 4) if tasks else 0.0,
        "failure_rate": round(results["failed"] / len(tasks), 4) if tasks else 0.0,
        "failure_rate_by_error_code": dict(failures_by_code),
        "latency_ms": {
            "p50": _percentile(total_durations, 50),
            "p95": _percentile(total_durations, 95),
            "p99": _percentile(total_durations, 99),
            "mean": int(statistics.mean(total_durations)) if total_durations else 0,
        },
        "stage_latency_ms": {
            stage: {
                "p50": _percentile(values, 50),
                "p95": _percentile(values, 95),
                "p99": _percentile(values, 99),
            }
            for stage, values in stage_durations.items()
        },
        "max_memory_mb": round(max_memory, 2),
        "db_invariant": "pass",
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
