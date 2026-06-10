[CmdletBinding()]
param(
    [string]$PackagePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

if ([string]::IsNullOrWhiteSpace($PackagePath)) {
    $packageRoot = Join-Path $repoRoot "desktop\PptAgentStudio.App\AppPackages"
    $package = Get-ChildItem -Path $packageRoot -Recurse -Filter "*.msix" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $package) {
        throw "No MSIX package was found under $packageRoot."
    }

    $PackagePath = $package.FullName
}

$resolvedPackage = Resolve-Path $PackagePath
Add-Type -AssemblyName System.IO.Compression.FileSystem

$zip = [System.IO.Compression.ZipFile]::OpenRead($resolvedPackage)
try {
    $entries = @($zip.Entries | ForEach-Object { $_.FullName })

    $requiredFiles = @(
        "AgentRuntime/python/python.exe",
        "AgentRuntime/agent/src/ppt_agent_studio/runtime/websocket_server.py"
    )

    foreach ($requiredFile in $requiredFiles) {
        if ($entries -notcontains $requiredFile) {
            throw "MSIX package is missing required file: $requiredFile"
        }
    }

    $requiredPrefixes = @(
        "AgentRuntime/python/Lib/site-packages/httpx/",
        "AgentRuntime/python/Lib/site-packages/pptx/",
        "AgentRuntime/python/Lib/site-packages/websockets/"
    )

    foreach ($requiredPrefix in $requiredPrefixes) {
        $match = $entries | Where-Object { $_.StartsWith($requiredPrefix, [System.StringComparison]::Ordinal) } | Select-Object -First 1
        if (-not $match) {
            throw "MSIX package is missing required directory: $requiredPrefix"
        }
    }

    $forbiddenPatterns = @(
        "*__pycache__*",
        "*.pyc",
        "*.dist-info*",
        "*cp313*",
        "*cpython*"
    )

    foreach ($forbiddenPattern in $forbiddenPatterns) {
        $match = $entries | Where-Object { $_ -like $forbiddenPattern } | Select-Object -First 1
        if ($match) {
            throw "MSIX package contains forbidden entry matching $forbiddenPattern`: $match"
        }
    }

    Write-Host "msix-package-smoke: bundled runtime contents ok"
}
finally {
    $zip.Dispose()
}
