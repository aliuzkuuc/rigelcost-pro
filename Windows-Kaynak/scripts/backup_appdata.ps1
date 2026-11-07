#Requires -Version 5.1
<#
.SYNOPSIS
  Backs up the Rigel Cost Pro Roaming AppData folder to a timestamped Desktop folder.

.DESCRIPTION
  Source (Qt AppDataLocation on Windows):
    %APPDATA%\Rigel Alüminyum\Rigel Cost Pro

  Default destination:
    %USERPROFILE%\Desktop\RigelCost-Backup-yyyyMMdd-HHmmss\

  Copies the whole folder (SQLite DBs + JSON caches). Close the app first when
  possible so files are not locked.

.PARAMETER DestinationRoot
  Parent folder for the timestamped backup. Defaults to the current user's Desktop.

.PARAMETER DryRun
  Show what would be copied without writing files.

.EXAMPLE
  .\scripts\backup_appdata.ps1

.EXAMPLE
  .\scripts\backup_appdata.ps1 -DryRun
#>
[CmdletBinding()]
param(
    [string]$DestinationRoot = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$source = Join-Path $env:APPDATA "Rigel Alüminyum\Rigel Cost Pro"

if (-not (Test-Path -LiteralPath $source)) {
    Write-Error "Source folder not found: $source"
    exit 1
}

if ([string]::IsNullOrWhiteSpace($DestinationRoot)) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    if ([string]::IsNullOrWhiteSpace($desktop)) {
        $desktop = Join-Path $env:USERPROFILE "Desktop"
    }
    $DestinationRoot = $desktop
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $DestinationRoot "RigelCost-Backup-$stamp"

Write-Host "Source:      $source"
Write-Host "Destination: $dest"
if ($DryRun) {
    Write-Host "Mode:        DRY-RUN (no files written)"
}

$items = Get-ChildItem -LiteralPath $source -Force -Recurse -ErrorAction SilentlyContinue
$fileCount = @($items | Where-Object { -not $_.PSIsContainer }).Count
$dirCount = @($items | Where-Object { $_.PSIsContainer }).Count
Write-Host "Contents:    $fileCount file(s), $dirCount subfolder(s)"

if ($DryRun) {
    Get-ChildItem -LiteralPath $source -Force | ForEach-Object {
        Write-Host ("  would copy: " + $_.Name)
    }
    Write-Host "Dry-run OK — no backup created."
    exit 0
}

New-Item -ItemType Directory -Path $dest -Force | Out-Null
Copy-Item -LiteralPath $source -Destination $dest -Recurse -Force

$copied = Get-ChildItem -LiteralPath $dest -Force -Recurse -ErrorAction SilentlyContinue |
    Where-Object { -not $_.PSIsContainer }
Write-Host ("Backup OK — {0} file(s) under {1}" -f @($copied).Count, $dest)
exit 0
