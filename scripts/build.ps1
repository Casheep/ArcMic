[CmdletBinding()]
param(
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython)) {
    python -m venv (Join-Path $projectRoot '.venv')
}

if (-not $SkipDependencyInstall) {
    & $venvPython -m pip install --disable-pip-version-check -r (Join-Path $projectRoot 'requirements-build.txt')
}

$requiredVendorFiles = @(
    'vendor\engine\EqualizerAPO.dll',
    'vendor\engine\fftw3f.dll',
    'vendor\engine\sndfile.dll',
    'vendor\rnnoise\rnnoise_mono.dll'
)
foreach ($relativePath in $requiredVendorFiles) {
    $absolutePath = Join-Path $projectRoot $relativePath
    if (-not (Test-Path -LiteralPath $absolutePath)) {
        throw "Missing vendored runtime: $relativePath"
    }
}

& $venvPython (Join-Path $projectRoot 'scripts\generate_icon.py')
$env:PYTHONPATH = Join-Path $projectRoot 'src'
& $venvPython -m unittest discover -s (Join-Path $projectRoot 'tests') -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }

Push-Location $projectRoot
try {
    & $venvPython -m PyInstaller --noconfirm --clean (Join-Path $projectRoot 'ArcMic.spec')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    $artifactDir = Join-Path $projectRoot 'artifacts'
    New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
    Copy-Item -LiteralPath (Join-Path $projectRoot 'dist\ArcMic.exe') -Destination (Join-Path $artifactDir 'ArcMic.exe') -Force
    Get-FileHash -LiteralPath (Join-Path $artifactDir 'ArcMic.exe') -Algorithm SHA256 |
        Format-List Algorithm,Hash,Path
}
finally {
    Pop-Location
}

