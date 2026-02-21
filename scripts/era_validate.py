from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import uuid
from pathlib import Path
from urllib import request


def _multipart_body(file_path: Path) -> tuple[bytes, str]:
    boundary = f"----vehr-era-{uuid.uuid4().hex}"
    ctype = mimetypes.guess_type(str(file_path))[0] or "application/pdf"
    file_bytes = file_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    return body, boundary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ERA PDF with VEHR API")
    parser.add_argument("--file", required=True, help="Path to ERA PDF")
    parser.add_argument("--base-url", required=True, help="Base API URL, e.g. http://127.0.0.1:8000")
    parser.add_argument("--token", required=False, help="Bearer token")
    args = parser.parse_args()

    file_path = Path(args.file).expanduser().resolve()
    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        return 1

    body, boundary = _multipart_body(file_path)
    req = request.Request(
        f"{args.base_url.rstrip('/')}/api/v1/era/validate",
        data=body,
        method="POST",
    )
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Accept", "application/json")
    if args.token:
        req.add_header("Authorization", f"Bearer {args.token}")

    try:
        with request.urlopen(req) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"Validation request failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2))
    return 0 if payload.get("era_file_id") else 1


if __name__ == "__main__":
    raise SystemExit(main())
