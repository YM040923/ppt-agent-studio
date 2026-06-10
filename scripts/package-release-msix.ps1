[CmdletBinding()]
param(
    [switch]$Sign,
    [switch]$TrustCertificate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$appProject = Join-Path $repoRoot "desktop\PptAgentStudio.App\PptAgentStudio.App.csproj"
$appPackagesRoot = Join-Path $repoRoot "desktop\PptAgentStudio.App\AppPackages"
$archiveRelativePath = "artifacts\msix\ppt-agent-studio-msix.zip"
$archivePath = Join-Path $repoRoot $archiveRelativePath
$archiveRoot = Split-Path -Parent $archivePath

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
    Invoke-NativeStep "Stage bundled runtime" { & .\scripts\stage-agent-runtime.ps1 }
    Invoke-NativeStep "Smoke bundled runtime" { & .\scripts\test-staged-agent-runtime.ps1 }
    Invoke-NativeStep "Package unsigned MSIX" {
        dotnet build $appProject `
            -c Release `
            -p:GenerateAppxPackageOnBuild=true `
            -p:AppxPackageSigningEnabled=false `
            -p:UapAppxPackageBuildMode=SideloadOnly `
            -p:AppxBundle=Never `
            -p:PublishTrimmed=false
    }
    Invoke-NativeStep "Verify unsigned MSIX contents" { & .\scripts\test-msix-package.ps1 }

    if ($Sign) {
        if ($TrustCertificate) {
            Invoke-NativeStep "Sign MSIX package" { & .\scripts\sign-msix-package.ps1 -TrustCertificate }
        }
        else {
            Invoke-NativeStep "Sign MSIX package" { & .\scripts\sign-msix-package.ps1 }
        }
    }

    New-Item -ItemType Directory -Force $archiveRoot | Out-Null
    Compress-Archive -Path (Join-Path $appPackagesRoot "*") -DestinationPath $archivePath -Force
    Write-Host "package-release: archive ready at $archivePath"
}
finally {
    Pop-Location
}
