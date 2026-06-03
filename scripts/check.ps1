Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root

try {
    python -m unittest discover -s tests
    python -m compileall socrates
    git diff --check
}
finally {
    Pop-Location
}
