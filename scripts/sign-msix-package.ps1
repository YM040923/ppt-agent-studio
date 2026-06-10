[CmdletBinding()]
param(
    [string]$PackagePath,
    [string]$CertificateOutputPath,
    [switch]$TrustCertificate
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

if ([string]::IsNullOrWhiteSpace($CertificateOutputPath)) {
    $CertificateOutputPath = Join-Path $repoRoot "artifacts\certificates\PPT Agent Studio Open Source.cer"
}

$resolvedPackage = Resolve-Path $PackagePath
$resolvedManifest = Resolve-Path $manifestPath
$manifest = [xml](Get-Content -Raw -LiteralPath $resolvedManifest)
$publisher = $manifest.Package.Identity.Publisher

if ([string]::IsNullOrWhiteSpace($publisher)) {
    throw "Package.appxmanifest Identity Publisher is empty."
}

$certificate = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object { $_.Subject -eq $publisher -and $_.HasPrivateKey } |
    Sort-Object NotAfter -Descending |
    Select-Object -First 1

if (-not $certificate) {
    $certificate = New-SelfSignedCertificate `
        -Type Custom `
        -Subject $publisher `
        -KeyUsage DigitalSignature `
        -FriendlyName "PPT Agent Studio local MSIX signing" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3")
}

$certificateDirectory = Split-Path -Parent $CertificateOutputPath
New-Item -ItemType Directory -Force $certificateDirectory | Out-Null
Export-Certificate -Cert $certificate -FilePath $CertificateOutputPath -Force | Out-Null

if ($TrustCertificate) {
    Import-Certificate -FilePath $CertificateOutputPath -CertStoreLocation "Cert:\CurrentUser\Root" | Out-Null
}

$signtool = Get-Command "signtool.exe" -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty Source

if (-not $signtool) {
    $windowsKitsRoot = "${env:ProgramFiles(x86)}\Windows Kits\10\bin"
    $signtool = Get-ChildItem -Path $windowsKitsRoot -Recurse -Filter "signtool.exe" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -like "*\x64\signtool.exe" } |
        Sort-Object FullName -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}

if (-not $signtool) {
    throw "signtool.exe was not found. Install the Windows SDK signing tools."
}

& $signtool sign /fd SHA256 /sha1 $certificate.Thumbprint $resolvedPackage
if ($LASTEXITCODE -ne 0) {
    throw "signtool sign failed with exit code $LASTEXITCODE."
}

if ($TrustCertificate) {
    & $signtool verify /pa $resolvedPackage
    if ($LASTEXITCODE -ne 0) {
        throw "signtool verify failed with exit code $LASTEXITCODE."
    }
}

Write-Host "msix-signing: signed package ok"
if ($TrustCertificate) {
    Write-Host "msix-signing: signature verified with trusted test certificate"
}
else {
    Write-Host "msix-signing: trust $CertificateOutputPath on test machines before installing"
}
