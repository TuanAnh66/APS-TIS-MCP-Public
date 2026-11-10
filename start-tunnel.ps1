param(
    [switch]$DoctorOnly
)
$ErrorActionPreference = 'Stop'
$client = Join-Path $PSScriptRoot 'bin\tunnel-client.exe'
$profileDir = Join-Path $PSScriptRoot 'tunnel-profiles'
if (-not (Test-Path -LiteralPath $client -PathType Leaf)) {
    throw 'The verified tunnel-client binary is missing.'
}
if (-not (Test-Path -LiteralPath $profileDir -PathType Container)) {
    throw 'Tunnel profile is missing. Run configure-tunnel.ps1 with the non-secret tunnel ID.'
}
$prompted = $false
if (-not $env:CONTROL_PLANE_API_KEY) {
    $secret = Read-Host 'Enter tunnel runtime API key locally (input hidden)' -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    try {
        $env:CONTROL_PLANE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
        $secret.Dispose()
    }
    $prompted = $true
}
try {
    & $client doctor --profile aps-tis --profile-dir $profileDir --explain
    if ($LASTEXITCODE -ne 0) {
        throw 'Tunnel diagnostics failed. Check the safe doctor output above.'
    }
    if (-not $DoctorOnly) {
        & $client run --profile aps-tis --profile-dir $profileDir
        if ($LASTEXITCODE -ne 0) {
            throw 'Tunnel client exited with an error.'
        }
    }
} finally {
    if ($prompted) {
        Remove-Item Env:\CONTROL_PLANE_API_KEY -ErrorAction SilentlyContinue
    }
}
