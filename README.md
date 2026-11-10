# APS-TIS read-only MCP server

Local Windows MCP server for the fixed private repository APS-TIS/APS-TIS. The server uses stdio and exposes eight read-only tools. All repository and issue API calls use GET. GitHub App authentication must POST to the fixed installation-token endpoint; this POST cannot modify repository content.

## Current installation

- App ID: 5692993
- Repository: APS-TIS/APS-TIS
- Python environment: C:\APS-TIS-MCP\.venv
- Key file: C:\APS-TIS-MCP\credentials\aps-tis-readonly.pem
- Tunnel client: C:\APS-TIS-MCP\bin\tunnel-client.exe
- No public listener, Windows service, scheduled task, or automatic startup is configured.

The key directory and key file have inheritance disabled and allow only the owning Windows account. Keep the original downloaded PEM in a protected location or remove it yourself after confirming a backup policy. Do not paste keys, JWTs, tokens, or runtime API keys into chat.

## Start and verify the MCP server

In PowerShell:

    & 'C:\APS-TIS-MCP\run.ps1' -Check
    & 'C:\APS-TIS-MCP\run.ps1' -Inventory

The check authenticates to GitHub and reports only App/installation/repository metadata. The default command starts a stdio server and waits for an MCP client:

    & 'C:\APS-TIS-MCP\run.ps1'

Stop a foreground server with Ctrl+C.

## Install or repair dependencies

Use only the dedicated virtual environment:

    & 'C:\APS-TIS-MCP\.venv\Scripts\python.exe' -m pip install -r 'C:\APS-TIS-MCP\requirements.txt'

The installed Python SDK is MCP 2.3.0. This installation uses Python 3.12.14.

## Secure MCP Tunnel

Tunnel-client 0.0.20 is installed from the official Windows amd64 release and its SHA-256 was checked against the release SHA256SUMS.txt. Check current CLI help before configuration:

    & 'C:\APS-TIS-MCP\bin\tunnel-client.exe' help quickstart
    & 'C:\APS-TIS-MCP\bin\tunnel-client.exe' init --help

No runtime API key is stored in this application. Inspect Platform Tunnels management for an existing suitable tunnel associated with the intended ChatGPT workspace; reuse it if present. The runtime principal needs Tunnels Read + Use. Tunnel creation needs Read + Manage. A runtime API key is distinct from an admin key.

Once the owner provides the non-secret tunnel ID, create a profile under C:\APS-TIS-MCP\tunnel-profiles:

    & 'C:\APS-TIS-MCP\configure-tunnel.ps1' -TunnelId 'tunnel_...'

The profile stores the tunnel ID and env:CONTROL_PLANE_API_KEY reference, never the literal key. The fixed stdio command uses forward-slash Windows paths because the current CLI parser treats backslashes as escapes.

Start the separate foreground tunnel script. It prompts for the runtime API key with hidden local input if the environment variable is absent, runs doctor, and starts the client:

    & 'C:\APS-TIS-MCP\start-tunnel.ps1'

Keep it running during ChatGPT discovery and tool calls. Check its local /healthz, /readyz, /health/mcp, and /ui surfaces. Stop with Ctrl+C. No inbound firewall rule is required.
OpenAI Help currently says Pro users may connect custom MCP servers with read/fetch permissions; confirm that the intended account exposes Tunnel in the Plugins flow. In ChatGPT web, open Plugins, add a custom MCP server, choose Tunnel, select the same tunnel, review the eight read-only tools and authentication, create the plugin, install it, and make a real read_file call. Do not consider deployment complete until that call succeeds.

## Security behavior and limits

- Fixed App ID, organization, and repository; no MCP argument can change them.
- Paths must be repository relative. Absolute paths, backslashes, traversal, and percent escapes are rejected.
- Optional ref accepts only a full commit SHA. Reads resolve and report the actual commit SHA.
- File reads are capped at 512 KiB; binary and non-UTF-8 files are not returned. Git LFS pointer text is labeled as a pointer.
- Search scans at most 25 candidate files per page and returns at most 20 matches. It reports partial results, skipped files, and GitHub tree truncation.
- Listing and issue tools are paginated. Comment bodies are capped at 16 KiB; issue descriptions at 64 KiB.
- Credential-shaped text is redacted and common credential file paths are blocked. This is a conservative safeguard, not a guarantee against every possible secret format.
- GitHub authentication tokens live only in process memory and refresh before expiration. No secret is logged by the application.
- The server has no generic HTTP proxy or source-writing tool. MCP read-only annotations are descriptive; fixed API methods and GitHub permissions are the enforcement layers.

## Tests

    $env:PYTHONDONTWRITEBYTECODE = '1'
    & 'C:\APS-TIS-MCP\.venv\Scripts\python.exe' -m pytest -q -p no:cacheprovider 'C:\APS-TIS-MCP\tests'

Tests do not write to GitHub. For source protection, inspect GitHub App and token permissions, MCP tool inventory, and the GET-only repository client. The one authentication POST is required by GitHub and fixed to the token endpoint.

## Maintenance

Restart: stop the foreground server/tunnel processes and rerun the commands above. The next process mints a fresh installation token.

Private key rotation: owner approval is required. Generate a replacement key in the existing GitHub App, replace only the protected PEM in credentials, reapply the restrictive ACL, restart, verify readback, then revoke the old key through GitHub. Never paste either key into chat.

Revoke access: an authorized organization administrator can remove the App installation in GitHub settings. The application will then fail its readiness check. Do not alter App permissions or installation scope without owner approval.

Back up non-secret configuration: copy app/, tests/, requirements.txt, .gitignore, README.md, and run.ps1. Exclude credentials/, .venv/, logs/, tunnel profiles containing environment references, and any runtime key material.

Official references:
- https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app
- https://docs.github.com/en/rest/apps/apps
- https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
- https://github.com/openai/tunnel-client/blob/master/docs/end-user-guide.md
