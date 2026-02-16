## ERA Extract (Azure Document Intelligence)

### Required environment variables
- `AZURE_DOCINTEL_ENDPOINT`
- `AZURE_DOCINTEL_KEY`

Put them in a local `.env` at the repo root (already gitignored).

### Run once
```powershell
.\.venv313\Scripts\python.exe -m scripts.era_extract.extract_era --pdf "inputs/eras\\your-era.pdf"
```

### Offline parse (no Azure SDK)
Parse from a saved Azure DI JSON response or plain text. This mode does not import any `azure.*` modules.

```powershell
.\.venv313\Scripts\python.exe -m scripts.era_extract.parse_content --doc-type era --analyze-json "outputs\\eras\\era_di_output.json" --out-xlsx "outputs\\eras\\era_lines.xlsx"
```

```powershell
.\.venv313\Scripts\python.exe -m scripts.era_extract.parse_content --doc-type era --content-txt "outputs\\eras\\era_content.txt" --out-xlsx "outputs\\eras\\era_lines.xlsx"
```

### Offline billed parse (no Azure SDK)
```powershell
.\.venv313\Scripts\python.exe -m scripts.era_extract.parse_content --doc-type billed --billed-track billing --analyze-json "outputs\\eras\\billed_di_output.json" --out-xlsx "outputs\\eras\\billed_lines.xlsx"
```

```powershell
.\.venv313\Scripts\python.exe -m scripts.era_extract.parse_content --doc-type billed --billed-track chpw --content-txt "outputs\\eras\\billed_content.txt" --out-xlsx "outputs\\eras\\billed_lines.xlsx"
```

### Golden path workflow (Azure once, then offline)
Step 1: Run Azure DI once and save JSON + content.
```powershell
.\.venv313\Scripts\python.exe -m scripts.era_extract.extract_era --pdf "inputs\\eras\\sample.pdf" --save-analyze-json "outputs\\eras\\era_di_output.json" --save-content-txt "outputs\\eras\\era_content.txt"
```

Step 2: Run offline parser any time.
```powershell
.\.venv313\Scripts\python.exe -m scripts.era_extract.parse_content --analyze-json "outputs\\eras\\era_di_output.json" --out-xlsx "outputs\\eras\\era_lines.xlsx"
```

Step 3: If you don't know the JSON path, search for candidates.
```powershell
.\.venv313\Scripts\python.exe -m scripts.era_extract.parse_content --find-analyze-json --search-root .
```

### Watch folder
```powershell
.\.venv313\Scripts\python.exe -m scripts.era_extract.watcher
```
