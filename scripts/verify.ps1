[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

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
    Invoke-NativeStep "Python tests" { python -m pytest agent\tests -q }
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
    Pop-Location
}
