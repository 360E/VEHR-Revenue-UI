from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Optional

from scripts.era_extract.docintel_client import verify_env as verify_env
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from scripts.era_extract.extract_era import run


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_in_dir() -> Path:
    return _repo_root() / "inputs" / "eras"


def _wait_for_stable_file(path: Path, settle_seconds: float = 1.0, timeout_seconds: float = 60.0) -> None:
    start = time.time()
    last_size = -1
    stable_for = 0.0
    while True:
        if not path.exists():
            time.sleep(0.25)
            continue

        size = path.stat().st_size
        if size == last_size and size > 0:
            stable_for += 0.25
        else:
            stable_for = 0.0
        last_size = size

        if stable_for >= settle_seconds:
            return
        if time.time() - start > timeout_seconds:
            raise TimeoutError(f"File did not stabilize in time: {path}")
        time.sleep(0.25)


class _Handler(FileSystemEventHandler):
    def __init__(self, settle_seconds: float):
        self.settle_seconds = settle_seconds

    def _process(self, path: Path) -> None:
        if path.suffix.lower() != ".pdf":
            return
        try:
            _wait_for_stable_file(path, settle_seconds=self.settle_seconds)
            out = run(path)
            print(str(out))
        except Exception as e:
            # No silent failures; watcher keeps running.
            print(f"[era_extract] failed for {path.name}: {e}")

    def on_created(self, event):
        if getattr(event, "is_directory", False):
            return
        self._process(Path(getattr(event, "src_path", "")))

    def on_moved(self, event):
        if getattr(event, "is_directory", False):
            return
        self._process(Path(getattr(event, "dest_path", "")))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Watch inputs/eras and auto-extract new PDFs to outputs/eras.")
    p.add_argument("--dir", dest="watch_dir", required=False, help="Directory to watch (default: inputs/eras)")
    p.add_argument(
        "--settle",
        dest="settle",
        required=False,
        type=float,
        default=1.0,
        help="Seconds file must be stable before processing",
    )
    p.add_argument(
        "--once",
        dest="once_pdf",
        nargs="?",
        const="__ALL__",
        help="Run once then exit. Optional value: a specific PDF path to process.",
    )
    return p


def _run_once(watch_dir: Path, settle_seconds: float, once_pdf: str | None = None) -> int:
    if once_pdf and once_pdf != "__ALL__":
        single = Path(once_pdf).resolve()
        if not single.exists() or single.suffix.lower() != ".pdf":
            print(f"[era_extract] invalid --once PDF path: {single}")
            return 1
        try:
            _wait_for_stable_file(single, settle_seconds=settle_seconds)
            run(single)
            return 0
        except Exception as e:
            print(f"[era_extract] failed for {single.name}: {e}")
            return 1

    pdfs = sorted([p for p in watch_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"])
    if not pdfs:
        print(f"[era_extract] no PDFs found in {watch_dir}")
        return 0
    for pdf in pdfs:
        try:
            _wait_for_stable_file(pdf, settle_seconds=settle_seconds)
            run(pdf)
        except Exception as e:
            print(f"[era_extract] failed for {pdf.name}: {e}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    verify_env()
    args = build_parser().parse_args(argv)
    watch_dir = Path(args.watch_dir).resolve() if args.watch_dir else _default_in_dir().resolve()
    watch_dir.mkdir(parents=True, exist_ok=True)

    if args.once_pdf:
        return _run_once(watch_dir, float(args.settle), args.once_pdf)

    handler = _Handler(settle_seconds=float(args.settle))
    observer = Observer()
    observer.schedule(handler, str(watch_dir), recursive=False)
    observer.start()

    print(f"[era_extract] watching: {watch_dir}")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
