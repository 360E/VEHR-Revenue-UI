import os
import subprocess
import sys
from pathlib import Path

DB_NAME = "vehr_dev"
DB_USER = "postgres"  # change if different

PG_BIN = Path(r"C:\Program Files\PostgreSQL\18\bin")
DROPDB = PG_BIN / "dropdb.exe"
CREATEDB = PG_BIN / "createdb.exe"

def run(cmd):
    print(f"\n>> {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)

def main():
    print("Resetting local Postgres database...")

    env = os.environ.copy()
    env["PGUSER"] = DB_USER

    run([str(DROPDB), "--if-exists", DB_NAME, "-U", DB_USER])
    run([str(CREATEDB), DB_NAME, "-U", DB_USER])
    run(["alembic", "upgrade", "head"])

    print("\n✅ Database reset complete.")

if __name__ == "__main__":
    main()
