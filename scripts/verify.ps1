[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$agentSource = Join-Path $repoRoot "agent\src"
$previousPythonPath = $env:PYTHONPATH

function Invoke-NativeStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host "==> $Name"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

Push-Location $repoRoot
try {
    if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
        $env:PYTHONPATH = $agentSource
    }
    else {
        $env:PYTHONPATH = "$agentSource;$previousPythonPath"
    }

    Invoke-NativeStep "Python tests" { python -m pytest agent\tests -q }
    Invoke-NativeStep "Offline demo smoke" {
        python -m ppt_agent_studio.runtime.demo --artifact-dir artifacts\verify-demo --follow-up "Add a risk mitigation slide"
    }
    Invoke-NativeStep "Desktop tests" { dotnet test desktop\PptAgentStudio.App.Tests\PptAgentStudio.App.Tests.csproj }
    Invoke-NativeStep "Desktop build" { dotnet build desktop\PptAgentStudio.App\PptAgentStudio.App.csproj }

    Write-Host "==> WinUI startup smoke"
    $project = Join-Path $repoRoot "desktop\PptAgentStudio.App\PptAgentStudio.App.csproj"
    $startupCommand = "dotnet run --project $project"
    Write-Host $startupCommand

    $proc = Start-Process `
        -FilePath "dotnet" `
        -ArgumentList @("run", "--project", $project) `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -PassThru

    try {
        Start-Sleep -Seconds 8
        $running = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
        if (-not $running) {
            throw "startup-smoke: process exited early."
        }

        Write-Host "startup-smoke: process stayed alive for 8 seconds"
    }
    finally {
        $running = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
        if ($running) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
