[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$runtimeRoot = Join-Path $repoRoot "desktop\PptAgentStudio.App\AgentRuntime"
$pythonExe = Join-Path $runtimeRoot "python\python.exe"
$agentSource = Join-Path $runtimeRoot "agent\src"
$sourceRuntime = Join-Path $repoRoot "agent\src"
$smokeScript = New-TemporaryFile

if (-not (Test-Path $pythonExe)) {
    throw "Staged Python runtime was not found. Run scripts\stage-agent-runtime.ps1 first."
}

Remove-Item -LiteralPath $agentSource -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $agentSource | Out-Null
Copy-Item -Path (Join-Path $sourceRuntime "*") -Destination $agentSource -Recurse -Force

$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PPT_AGENT_ARTIFACTS_DIR = Join-Path $repoRoot "artifacts\staged-runtime-smoke"
try {
    @'
import asyncio
import json

from ppt_agent_studio.runtime.websocket_server import handle_client_message

responses = asyncio.run(
    handle_client_message(json.dumps({"type": "runtime.config", "session_id": "smoke"}))
)
payload = json.loads(responses[0])["payload"]

assert payload["runtime"]["name"] == "ppt-agent-studio"
assert "directory" in payload["artifacts"]
print("staged-runtime-smoke: runtime.config ok")
'@ | Set-Content -LiteralPath $smokeScript -Encoding UTF8
    & $pythonExe $smokeScript
    if ($LASTEXITCODE -ne 0) {
        throw "staged runtime smoke failed with exit code $LASTEXITCODE."
    }
}
finally {
    Remove-Item Env:\PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue
    Remove-Item Env:\PPT_AGENT_ARTIFACTS_DIR -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $smokeScript -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $agentSource -Recurse -Force -ErrorAction SilentlyContinue
}
