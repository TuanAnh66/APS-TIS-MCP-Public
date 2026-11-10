param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^tunnel_[A-Za-z0-9]+$')]
    [string]$TunnelId
)
$ErrorActionPreference = 'Stop'
$client = Join-Path $PSScriptRoot 'bin\tunnel-client.exe'
$profileDir = Join-Path $PSScriptRoot 'tunnel-profiles'
if (-not (Test-Path -LiteralPath $client -PathType Leaf)) {
    throw 'The verified tunnel-client binary is missing.'
}
New-Item -Path $profileDir -ItemType Directory -Force | Out-Null
$mcpCommand = 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:/APS-TIS-MCP/run.ps1'
& $client init --sample sample_mcp_stdio_local --profile aps-tis --profile-dir $profileDir --tunnel-id $TunnelId --mcp-command $mcpCommand --control-plane-api-key-ref env:CONTROL_PLANE_API_KEY --health-listen-addr '127.0.0.1:0'
if ($LASTEXITCODE -ne 0) {
    throw 'Tunnel profile creation failed. Check tunnel-client init --help.'
}
Write-Output 'Profile configured with an environment reference. No runtime API key was saved.'
