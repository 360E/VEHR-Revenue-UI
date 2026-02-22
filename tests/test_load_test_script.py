from __future__ import annotations

from pathlib import Path

from scripts import load_test


def test_percentile_handles_empty_and_interpolated_values() -> None:
    assert load_test._percentile([], 95) == 0
    assert load_test._percentile([10], 95) == 10
    assert load_test._percentile([10, 20, 30, 40], 50) == 25


def test_extract_stage_durations_reads_duration_only() -> None:
    rows = [
        {"stage": "EXTRACTED", "message": "model_id=di; duration_ms=101"},
        {"stage": "STRUCTURED", "message": "claim_count=1; duration_ms=202"},
        {"stage": "NORMALIZED", "message": "claim_count=1"},
        {"stage": "STRUCTURED", "message": "duration_ms=abc"},
    ]
    assert load_test._extract_stage_durations(rows) == {"extracted": 101, "structured": 202}


def test_required_stress_fixtures_exist() -> None:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / "era"
    required = {
        "large_20p.pdf",
        "large_50p.pdf",
        "large_100p.pdf",
        "malformed_truncated.pdf",
        "malformed_not_pdf.pdf",
        "encrypted.pdf",
    }
    assert required.issubset({path.name for path in fixture_dir.iterdir() if path.is_file()})


def test_main_supports_concurrency_matrix(tmp_path, monkeypatch, capsys) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(load_test, "_login", lambda *args, **kwargs: "tok")
    monkeypatch.setattr(
        load_test,
        "_run_one",
        lambda *args, **kwargs: {
            "ok": True,
            "error_code": "",
            "request_id": "req-1",
            "duration_ms": 10,
            "stage_durations": {"extracted": 5, "structured": 4, "normalized": 1},
            "db_invariant_ok": True,
        },
    )
    monkeypatch.setattr(load_test, "_rss_mb", lambda: 64.0)

    for workers in (5, 20, 50):
        rc = load_test.main(
            [
                "--dir",
                str(tmp_path),
                "--base-url",
                "http://127.0.0.1:8000",
                "--workers",
                str(workers),
                "--iterations",
                "1",
                "--memory-ceiling-mb",
                "128",
            ]
        )
        assert rc == 0
    assert '"db_invariant": "pass"' in capsys.readouterr().out
