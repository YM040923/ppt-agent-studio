param(
    [string]$PythonVersion = "3.13.13",
    [string]$Architecture = "amd64"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $repoRoot "desktop\PptAgentStudio.App\AgentRuntime"
$pythonRoot = Join-Path $runtimeRoot "python"
$stagingRoot = Join-Path $repoRoot "artifacts\runtime-staging"
$wheelhouseRoot = Join-Path $stagingRoot "wheelhouse"
$pythonZip = Join-Path $stagingRoot "python-$PythonVersion-embed-$Architecture.zip"
$pythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-$Architecture.zip"
$pythonTag = "cp$($PythonVersion.Split('.')[0])$($PythonVersion.Split('.')[1])"
$platformTag = "win_$Architecture"
$runtimeDependencies = @(
    "httpx>=0.27",
    "python-pptx>=1.0.0",
    "websockets>=12.0"
)

New-Item -ItemType Directory -Force $stagingRoot | Out-Null
Remove-Item -LiteralPath $pythonRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $wheelhouseRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $pythonRoot | Out-Null
New-Item -ItemType Directory -Force $wheelhouseRoot | Out-Null

if (-not (Test-Path $pythonZip)) {
    Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonZip
}

Expand-Archive -Path $pythonZip -DestinationPath $pythonRoot -Force

$pthName = "python$($PythonVersion.Split('.')[0])$($PythonVersion.Split('.')[1])._pth"
$pthPath = Join-Path $pythonRoot $pthName
@(
    "python$($PythonVersion.Split('.')[0])$($PythonVersion.Split('.')[1]).zip",
    ".",
    "Lib\site-packages",
    "..\agent\src",
    "import site"
) | Set-Content -Path $pthPath -Encoding ASCII

$pythonExe = Join-Path $pythonRoot "python.exe"
$sitePackages = Join-Path $pythonRoot "Lib\site-packages"
New-Item -ItemType Directory -Force $sitePackages | Out-Null

python -m pip download `
    --only-binary=:all: `
    --implementation cp `
    --python-version "$($PythonVersion.Split('.')[0]).$($PythonVersion.Split('.')[1])" `
    --abi $pythonTag `
    --platform $platformTag `
    --dest $wheelhouseRoot `
    $runtimeDependencies
if ($LASTEXITCODE -ne 0) {
    throw "runtime dependency wheel download failed with exit code $LASTEXITCODE."
}

$wheels = Get-ChildItem -Path $wheelhouseRoot -Filter *.whl
foreach ($wheel in $wheels) {
    $wheelZip = Join-Path $stagingRoot "$($wheel.BaseName).zip"
    Copy-Item -LiteralPath $wheel.FullName -Destination $wheelZip -Force
    Expand-Archive -Path $wheelZip -DestinationPath $sitePackages -Force
    Remove-Item -LiteralPath $wheelZip -Force
}

Get-ChildItem -Path $sitePackages -Recurse -Force -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force
Get-ChildItem -Path $sitePackages -Recurse -Force -File -Filter "*.pyc" |
    Remove-Item -Force
Get-ChildItem -Path $sitePackages -Force -Directory -Filter "*.dist-info" |
    Remove-Item -Recurse -Force

$nativeExtensions = Get-ChildItem -Path $sitePackages -Recurse -Force -File -Filter "*.$pythonTag-win_$Architecture.pyd"
foreach ($extension in $nativeExtensions) {
    $normalizedName = $extension.Name.Replace(".$pythonTag-win_$Architecture.pyd", ".pyd")
    Rename-Item -LiteralPath $extension.FullName -NewName $normalizedName -Force
}

$env:PYTHONDONTWRITEBYTECODE = "1"
& $pythonExe -c "import httpx, pptx, websockets"
if ($LASTEXITCODE -ne 0) {
    throw "staged runtime import smoke failed with exit code $LASTEXITCODE."
}
Remove-Item Env:\PYTHONDONTWRITEBYTECODE

Get-ChildItem -Path $sitePackages -Recurse -Force -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force
Get-ChildItem -Path $sitePackages -Recurse -Force -File -Filter "*.pyc" |
    Remove-Item -Force

Write-Host "Staged bundled Python runtime at $pythonRoot"
