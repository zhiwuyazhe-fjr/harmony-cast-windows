param([switch]$BridgeOnly)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$javaCompiler = @(
    if ($env:JAVA_HOME) { Join-Path $env:JAVA_HOME 'bin/javac.exe' }
    (Get-Command javac -ErrorAction SilentlyContinue).Source
    'D:\tools\DevEco Studio\jbr\bin\javac.exe'
    'C:\Program Files\Huawei\DevEco Studio\jbr\bin\javac.exe'
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $javaCompiler) { throw 'Set JAVA_HOME to a JDK or add javac to PATH' }
New-Item -ItemType Directory -Force 'bridge/out' | Out-Null
& $javaCompiler -encoding UTF-8 -Xlint:-options --release 8 -cp vendor/hosScrcpy-1.0.18-beta.jar -d bridge/out bridge/CastBridge.java
if ($LASTEXITCODE -ne 0) { throw 'Java bridge build failed' }
if ($BridgeOnly) { return }
$originalPath = $env:PATH
try {
    # Avoid resolving Windows ICU against unrelated SDK/Poppler DLLs on PATH.
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot;$PSScriptRoot\.venv\Scripts;$PSScriptRoot\.venv\Lib\site-packages\PySide6"
    & $python -m PyInstaller --noconfirm --clean --windowed --name HarmonyCast --icon installer/harmony-cast.ico --add-data 'vendor;vendor' --add-data 'bridge/out;bridge/out' --add-data 'installer/harmony-cast.ico;installer' --add-data 'docs/connection.png;docs' --add-data 'README.md;.' --add-data 'THIRD_PARTY_NOTICES.md;.' --copy-metadata PySide6-Essentials --copy-metadata shiboken6 --copy-metadata av main.py
    if ($LASTEXITCODE -ne 0) { throw 'Windows app build failed' }
} finally {
    $env:PATH = $originalPath
}
Write-Output (Join-Path $PSScriptRoot 'dist\HarmonyCast\HarmonyCast.exe')
