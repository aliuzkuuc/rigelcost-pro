$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BuildRoot = Join-Path $env:TEMP "RCB"
$VenvRoot = Join-Path $BuildRoot "venv"
$VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
$DistRoot = Join-Path $BuildRoot "dist"
$TempRelease = Join-Path $BuildRoot "release"
$ReleaseRoot = Join-Path $ProjectRoot "release"
$PortableZipName = "RigelCost-Pro-v4.0.0-Portable.zip"
$SetupExeName = "RigelCost-Pro-v4.0.0-Setup.exe"
$PortableZip = Join-Path $ReleaseRoot $PortableZipName
$ApplicationDirectory = Join-Path $DistRoot "RigelCost-Pro"
$ApplicationExe = Join-Path $ApplicationDirectory "RigelCostPro.exe"
$PortableStage = Join-Path $BuildRoot "portable-stage"
$MinimumSetupBytes = 40MB

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-Checked {
    param([string]$FilePath, [string[]]$ArgumentList)
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $FilePath"
    }
}

function Copy-DirectoryWithRetry {
    param([string]$Source, [string]$Destination)
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    & robocopy.exe $Source $Destination /E /R:10 /W:2 /NFL /NDL /NJH /NJS /NP
    $RobocopyExitCode = $LASTEXITCODE
    if ($RobocopyExitCode -ge 8) {
        throw "Portable files could not be copied (robocopy exit code: $RobocopyExitCode)."
    }
}

function Test-PortableExe {
    param([string]$PortableExePath)
    if (-not (Test-Path $PortableExePath)) {
        throw "Portable RigelCostPro.exe was not found."
    }
    $PortableSize = (Get-Item $PortableExePath).Length
    if ($PortableSize -lt 5MB) {
        throw "Portable RigelCostPro.exe looks incomplete ($PortableSize bytes)."
    }
}

function Test-SetupExe {
    param([string]$SetupPath)
    if (-not (Test-Path $SetupPath)) {
        throw "Setup.exe was not produced."
    }
    $SetupSize = (Get-Item $SetupPath).Length
    if ($SetupSize -lt $MinimumSetupBytes) {
        throw "Setup.exe looks incomplete ($SetupSize bytes)."
    }
    $Header = Get-Content -LiteralPath $SetupPath -Encoding Byte -TotalCount 2
    if ($Header.Count -lt 2 -or $Header[0] -ne 0x4D -or $Header[1] -ne 0x5A) {
        throw "Setup.exe is not a valid Windows program file."
    }
}

function Publish-ReleaseArtifact {
    param([string]$SourcePath, [string]$DestinationDirectory)
    New-Item -ItemType Directory -Force -Path $DestinationDirectory | Out-Null
    Copy-Item -LiteralPath $SourcePath -Destination $DestinationDirectory -Force
}

function New-PortableArchive {
    param(
        [string]$SourceDirectory,
        [string]$DestinationPath,
        [int]$MaxAttempts = 8
    )
    for ($Attempt = 1; $Attempt -le $MaxAttempts; $Attempt++) {
        try {
            if (Test-Path $DestinationPath) {
                Remove-Item -LiteralPath $DestinationPath -Force
            }
            Compress-Archive `
                -Path (Join-Path $SourceDirectory "*") `
                -DestinationPath $DestinationPath `
                -CompressionLevel Optimal `
                -ErrorAction Stop
            if (-not (Test-Path $DestinationPath)) {
                throw "Portable ZIP was not produced."
            }
            return
        }
        catch {
            if ($Attempt -ge $MaxAttempts) { throw }
            Write-Warning "A Windows process is temporarily using a build file. Portable ZIP will be retried ($Attempt/$MaxAttempts)."
            Start-Sleep -Seconds 2
        }
    }
}

function Test-Python {
    param([string]$Candidate)
    if (-not $Candidate -or -not (Test-Path $Candidate)) { return $false }
    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & $Candidate -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)" *> $null
        return $LASTEXITCODE -eq 0
    }
    catch { return $false }
    finally { $ErrorActionPreference = $PreviousPreference }
}

function Find-Python {
    $Candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
        (Join-Path $env:ProgramFiles "Python312\python.exe")
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Python $Candidate) { return $Candidate }
    }
    $PythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($PythonCommand -and (Test-Python $PythonCommand.Source)) {
        return $PythonCommand.Source
    }
    $Launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($Launcher) {
        $PreviousPreference = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        try {
            $Resolved = & $Launcher.Source -3.12 -c "import sys; print(sys.executable)" 2>$null
            $LauncherExitCode = $LASTEXITCODE
        }
        catch {
            $Resolved = $null
            $LauncherExitCode = 1
        }
        finally { $ErrorActionPreference = $PreviousPreference }
        if ($LauncherExitCode -eq 0 -and $Resolved) {
            $ResolvedPath = [string]$Resolved
            if (Test-Python $ResolvedPath.Trim()) { return $ResolvedPath.Trim() }
        }
    }
    return $null
}

function Install-BuildTools {
    param([string]$PackageId)
    $Winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $Winget) {
        throw "winget was not found. Install Python 3.12 and Inno Setup 6, then run this file again."
    }
    Invoke-Checked $Winget.Source @(
        "install", "--exact", "--id", $PackageId,
        "--source", "winget",
        "--accept-package-agreements", "--accept-source-agreements",
        "--disable-interactivity", "--silent"
    )
}

function Find-InnoCompiler {
    $Candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    )
    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-Path $Candidate)) { return $Candidate }
    }
    return $null
}

Set-Location $ProjectRoot
Write-Host "Rigel Cost Pro v4.0.0 - Windows EXE builder" -ForegroundColor White
Write-Host "This window can stay open for several minutes on the first build."

$Python = Find-Python
if (-not $Python) {
    Write-Step "Python 3.12 build tool is being installed"
    Install-BuildTools "Python.Python.3.12"
    $Python = Find-Python
}
if (-not $Python) {
    throw "Python installation completed but python.exe could not be located. Restart Windows and try again."
}

Write-Step "Old partial build files are being cleaned"
if (Test-Path $BuildRoot) {
    Remove-Item -LiteralPath $BuildRoot -Recurse -Force
}

Write-Step "Clean Python 3.12 build environment is being prepared"
Invoke-Checked $Python @("-m", "venv", $VenvRoot)
Invoke-Checked $VenvPython @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Checked $VenvPython @(
    "-m", "pip", "install",
    "-r", (Join-Path $ProjectRoot "requirements.txt"),
    "-r", (Join-Path $ProjectRoot "build\windows\requirements-build.txt")
)

Write-Step "RigelCostPro.exe is being compiled"
Invoke-Checked $VenvPython @(
    "-m", "PyInstaller", "--clean", "--noconfirm",
    "--workpath", (Join-Path $BuildRoot "pyinstaller"),
    "--distpath", $DistRoot,
    (Join-Path $ProjectRoot "build\windows\RigelCostPro.spec")
)
if (-not (Test-Path $ApplicationExe)) { throw "RigelCostPro.exe was not produced." }

Write-Step "Compiled application is being smoke-tested"
$SmokeData = Join-Path $BuildRoot "smoke-data"
New-Item -ItemType Directory -Force -Path $SmokeData | Out-Null
$PreviousDataDirectory = $env:RIGELCOST_DATA_DIR
$env:RIGELCOST_DATA_DIR = $SmokeData
try { Invoke-Checked $ApplicationExe @("--build-smoke-test") }
finally { $env:RIGELCOST_DATA_DIR = $PreviousDataDirectory }

Write-Step "Portable ZIP is being created"
New-Item -ItemType Directory -Force -Path $TempRelease | Out-Null
Copy-DirectoryWithRetry $ApplicationDirectory $PortableStage
Copy-Item -LiteralPath (Join-Path $ProjectRoot "build\windows\RIGEL-COST-PRO-BASLAT.bat") -Destination $PortableStage -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "build\windows\KALDIR.bat") -Destination $PortableStage -Force
Test-PortableExe (Join-Path $PortableStage "RigelCostPro.exe")
$PortableZipTemp = Join-Path $TempRelease $PortableZipName
New-PortableArchive $PortableStage $PortableZipTemp

$InnoCompiler = Find-InnoCompiler
if (-not $InnoCompiler) {
    Write-Step "Inno Setup 6 is being installed"
    Install-BuildTools "JRSoftware.InnoSetup"
    $InnoCompiler = Find-InnoCompiler
}

if ($InnoCompiler) {
    Write-Step "Windows setup file is being created"
    Invoke-Checked $InnoCompiler @(
        "/DMySourceDir=$ApplicationDirectory",
        "/DMyOutputDir=$TempRelease",
        (Join-Path $ProjectRoot "build\windows\installer.iss")
    )
    Test-SetupExe (Join-Path $TempRelease $SetupExeName)
}
else {
    Write-Warning "Inno Setup compiler was not found. Portable ZIP is ready, but Setup.exe could not be produced."
}

Write-Step "Release files are being copied to the project folder"
Publish-ReleaseArtifact $PortableZipTemp $ReleaseRoot
if (Test-Path (Join-Path $TempRelease $SetupExeName)) {
    Publish-ReleaseArtifact (Join-Path $TempRelease $SetupExeName) $ReleaseRoot
}

Write-Host ""
Write-Host "BUILD COMPLETED" -ForegroundColor Green
Write-Host "Output folder: $ReleaseRoot"
Get-ChildItem $ReleaseRoot | Select-Object Name, Length, LastWriteTime
Write-Host ""
Write-Host "Quick test: extract the portable ZIP and run RIGEL-COST-PRO-BASLAT.bat"
