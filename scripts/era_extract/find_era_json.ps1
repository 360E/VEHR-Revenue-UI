param(
    [string]$SearchRoot = "."
)

$root = Resolve-Path -Path $SearchRoot
$patterns = @("era", "docintel", "analyze")

$files = Get-ChildItem -Path $root -Recurse -Filter *.json -ErrorAction SilentlyContinue
$candidates = @()

foreach ($f in $files) {
    $nameMatch = $false
    $lname = $f.Name.ToLowerInvariant()
    foreach ($p in $patterns) {
        if ($lname.Contains($p)) { $nameMatch = $true; break }
    }

    $contentMatch = $false
    if (-not $nameMatch) {
        try {
            $raw = Get-Content -Path $f.FullName -Raw -ErrorAction Stop
            $obj = $raw | ConvertFrom-Json -ErrorAction Stop
            if ($null -ne $obj.analyzeResult -and $null -ne $obj.analyzeResult.content) {
                $contentMatch = $true
            } elseif ($null -ne $obj.content) {
                $contentMatch = $true
            }
        } catch {
            $contentMatch = $false
        }
    }

    if ($nameMatch -or $contentMatch) {
        $candidates += $f
    }
}

if ($candidates.Count -eq 0) {
    Write-Output "No analyze JSON candidates found under $root"
    exit 2
}

Write-Output "Analyze JSON candidates:"
$idx = 1
foreach ($c in $candidates) {
    $rel = Resolve-Path -Path $c.FullName -Relative -ErrorAction SilentlyContinue
    if (-not $rel) { $rel = $c.FullName }
    Write-Output ("{0}. {1} ({2} bytes)" -f $idx, $rel, $c.Length)
    $idx++
}
