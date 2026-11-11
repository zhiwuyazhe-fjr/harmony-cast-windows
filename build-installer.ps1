param([switch]$SkipAppBuild)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$cacheRoot = Join-Path $PSScriptRoot '.packaging'
$toolchain = Get-Content -LiteralPath 'installer/toolchain.json' -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Force $cacheRoot | Out-Null

function Get-VerifiedDownload($Url, $Destination, $Sha256) {
    if (-not (Test-Path -LiteralPath $Destination)) {
        Invoke-WebRequest -Uri $Url -OutFile $Destination
    }
    $actualHash = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash
    if ($actualHash -ne $Sha256) {
        throw "Checksum mismatch for $Destination"
    }
}

$runtime = Join-Path $cacheRoot 'runtime'
if (-not (Test-Path -LiteralPath (Join-Path $runtime 'bin/java.exe'))) {
    $archive = Join-Path $cacheRoot 'temurin-jre.zip'
    Get-VerifiedDownload $toolchain.java.url $archive $toolchain.java.sha256
    $extracted = Join-Path $cacheRoot 'jre'
    Expand-Archive -LiteralPath $archive -DestinationPath $extracted -Force
    Copy-Item -LiteralPath (Join-Path $extracted $toolchain.java.directory) -Destination $runtime -Recurse -Force
}

$compiler = Join-Path $cacheRoot 'InnoSetup/ISCC.exe'
if (-not (Test-Path -LiteralPath $compiler)) {
    $bootstrap = Join-Path $cacheRoot 'innosetup.exe'
    Get-VerifiedDownload $toolchain.inno.url $bootstrap $toolchain.inno.sha256
    $compilerDirectory = Join-Path $cacheRoot 'InnoSetup'
    $setupArguments = @('/CURRENTUSER', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/PORTABLE=1', '/NOICONS', '/TASKS=""', ('/DIR="{0}"' -f $compilerDirectory))
    $setupProcess = Start-Process -FilePath $bootstrap -ArgumentList $setupArguments -WindowStyle Hidden -Wait -PassThru
    if ($setupProcess.ExitCode -ne 0) { throw 'Inno Setup compiler installation failed' }
}

if (-not $SkipAppBuild) { & (Join-Path $PSScriptRoot 'build.ps1') }
$application = Join-Path $PSScriptRoot 'dist/MirrorStage'
if (-not (Test-Path -LiteralPath (Join-Path $application 'MirrorStage.exe'))) {
    throw 'Build the desktop app before creating the installer'
}
$bundledRuntime = Join-Path $application '_internal/runtime'
New-Item -ItemType Directory -Force $bundledRuntime | Out-Null
Get-ChildItem -LiteralPath $runtime | Copy-Item -Destination $bundledRuntime -Recurse -Force

& $compiler /Qp 'installer/JixFitCast.iss'
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
$installer = Join-Path $PSScriptRoot 'release/JixFit-Cast-Setup-1.0.0-x64.exe'
$hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath ($installer + '.sha256') -Value "$hash  JixFit-Cast-Setup-1.0.0-x64.exe" -Encoding ascii
Write-Output $installer
