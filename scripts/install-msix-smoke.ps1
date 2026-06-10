[CmdletBinding()]
param(
    [string]$PackagePath,
    [int]$StartupTimeoutSeconds = 8,
    [switch]$ReplaceExisting,
    [switch]$Cleanup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$manifestPath = Join-Path $repoRoot "desktop\PptAgentStudio.App\Package.appxmanifest"

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
$manifest = [xml](Get-Content -Raw -LiteralPath (Resolve-Path $manifestPath))
$packageName = $manifest.Package.Identity.Name
$publisher = $manifest.Package.Identity.Publisher
$applicationId = $manifest.Package.Applications.Application.Id
$processName = "PptAgentStudio.App"

$trustedRoot = Get-ChildItem "Cert:\LocalMachine\Root" -ErrorAction SilentlyContinue |
    Where-Object { $_.Subject -eq $publisher } |
    Select-Object -First 1
$trustedPublisher = Get-ChildItem "Cert:\LocalMachine\TrustedPeople" -ErrorAction SilentlyContinue |
    Where-Object { $_.Subject -eq $publisher } |
    Select-Object -First 1

if (-not $trustedRoot -or -not $trustedPublisher) {
    throw "MSIX install smoke requires an elevated PowerShell session to trust the test certificate in Cert:\LocalMachine\Root and Cert:\LocalMachine\TrustedPeople before Add-AppxPackage."
}

$existingPackage = Get-AppxPackage -Name $packageName -ErrorAction SilentlyContinue
if ($existingPackage) {
    if (-not $ReplaceExisting) {
        throw "Package $packageName is already installed. Re-run with -ReplaceExisting to replace it for this smoke."
    }

    Stop-Process -Name $processName -Force -ErrorAction SilentlyContinue
    foreach ($package in @($existingPackage)) {
        Remove-AppxPackage -Package $package.PackageFullName
    }
}

Add-AppxPackage -Path $resolvedPackage
$installedPackage = Get-AppxPackage -Name $packageName -ErrorAction Stop
$aumid = "$($installedPackage.PackageFamilyName)!$applicationId"

Start-Process "shell:AppsFolder\$aumid"

$deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
$process = $null
while ((Get-Date) -lt $deadline) {
    $process = Get-Process -Name $processName -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($process) {
        break
    }

    Start-Sleep -Milliseconds 500
}

if (-not $process) {
    throw "msix-install-smoke: process did not start within $StartupTimeoutSeconds seconds."
}

Write-Host "msix-install-smoke: process stayed alive for $StartupTimeoutSeconds seconds"

Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue

if ($Cleanup) {
    $installedPackage = Get-AppxPackage -Name $packageName -ErrorAction SilentlyContinue
    if ($installedPackage) {
        Remove-AppxPackage -Package $installedPackage.PackageFullName
    }
}
