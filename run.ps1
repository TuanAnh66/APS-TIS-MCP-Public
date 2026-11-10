param(
    [switch]$Check,
    [switch]$Inventory
)
$ErrorActionPreference = 'Stop'
$env:PYTHONDONTWRITEBYTECODE = '1'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Dedicated Python virtual environment is missing. Install requirements into C:\APS-TIS-MCP\.venv.'
}
Set-Location -LiteralPath $PSScriptRoot
if ($Check) {
    & $python -B -m app.server --check
} elseif ($Inventory) {
    & $python -B -m app.server --inventory
} else {
    & $python -B -m app.server
}
exit $LASTEXITCODE
