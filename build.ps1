$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$javaCompiler = 'D:\tools\DevEco Studio\jbr\bin\javac.exe'
if (-not (Test-Path -LiteralPath $javaCompiler)) {
    $javaCompiler = (Get-Command javac -ErrorAction Stop).Source
}
& $javaCompiler -encoding UTF-8 -Xlint:-options --release 8 -cp vendor/hosScrcpy-1.0.18-beta.jar -d bridge/out bridge/CastBridge.java
if ($LASTEXITCODE -ne 0) { throw 'Java bridge build failed' }
$originalPath = $env:PATH
try {
    # Avoid resolving Windows ICU against unrelated SDK/Poppler DLLs on PATH.
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot;$PSScriptRoot\.venv\Scripts;$PSScriptRoot\.venv\Lib\site-packages\PySide6"
    & $python -m PyInstaller --noconfirm --clean --windowed --name MirrorStage --icon assets/jixfit.png --add-data 'vendor;vendor' --add-data 'bridge/out;bridge/out' --add-data 'assets;assets' --add-data 'README.md;.' --add-data 'THIRD_PARTY_NOTICES.md;.' --copy-metadata PySide6-Essentials --copy-metadata shiboken6 --copy-metadata av main.py
    if ($LASTEXITCODE -ne 0) { throw 'Windows app build failed' }
} finally {
    $env:PATH = $originalPath
}
Write-Output (Join-Path $PSScriptRoot 'dist\MirrorStage\MirrorStage.exe')
