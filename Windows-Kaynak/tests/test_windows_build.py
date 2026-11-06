from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class WindowsBuildScriptTests(unittest.TestCase):
    def test_portable_packaging_retries_locked_files(self) -> None:
        script = (
            PROJECT_ROOT / "build" / "windows" / "build_windows.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("Copy-DirectoryWithRetry", script)
        self.assertIn("robocopy.exe", script)
        self.assertIn("/R:10", script)
        self.assertIn("New-PortableArchive", script)
        self.assertIn("[int]$MaxAttempts = 8", script)
        self.assertIn("Start-Sleep -Seconds 2", script)
        self.assertIn("portable-stage", script)
        self.assertIn('"--source", "winget"', script)
        self.assertIn('"--disable-interactivity"', script)
        self.assertIn('Join-Path $env:TEMP "RCB"', script)
        self.assertIn('"--distpath", $DistRoot', script)
        self.assertIn('"/DMySourceDir=$ApplicationDirectory"', script)
        self.assertIn('"/DMyOutputDir=$TempRelease"', script)
        self.assertIn("Test-SetupExe", script)
        self.assertIn("RIGEL-COST-PRO-BASLAT.bat", script)
        self.assertIn("KALDIR.bat", script)

    def test_windows_package_versions_match(self) -> None:
        builder = (
            PROJECT_ROOT / "build" / "windows" / "build_windows.ps1"
        ).read_text(encoding="utf-8")
        installer = (
            PROJECT_ROOT / "build" / "windows" / "installer.iss"
        ).read_text(encoding="utf-8")
        version_info = (
            PROJECT_ROOT / "build" / "windows" / "version_info.txt"
        ).read_text(encoding="utf-8")

        self.assertIn("RigelCost-Pro-v4.0.0-Portable.zip", builder)
        self.assertIn('#define MyAppVersion "4.0.0"', installer)
        self.assertIn("RigelCost-Pro-v4.0.0-Setup", installer)
        self.assertIn("4.0.0.0", version_info)
        self.assertIn('#ifndef MySourceDir', installer)
        self.assertIn('#ifndef MyOutputDir', installer)
        self.assertIn('OutputDir={#MyOutputDir}', installer)

    def test_installer_supports_clean_uninstall(self) -> None:
        installer = (
            PROJECT_ROOT / "build" / "windows" / "installer.iss"
        ).read_text(encoding="utf-8")
        kaldir = (
            PROJECT_ROOT / "build" / "windows" / "KALDIR.bat"
        ).read_text(encoding="utf-8")
        guide = (
            PROJECT_ROOT / "WINDOWS-KURULUM-REHBERI.md"
        ).read_text(encoding="utf-8")

        self.assertIn("UninstallDisplayName", installer)
        self.assertIn("CreateUninstallRegKey=yes", installer)
        self.assertIn("{uninstallexe}", installer)
        self.assertIn("InitializeUninstall", installer)
        self.assertIn("WipeUserData", installer)
        self.assertIn("Temiz kaldır", installer)
        self.assertIn("Normal kaldır", installer)
        self.assertIn(r"%LOCALAPPDATA%", installer)
        self.assertIn("Rigel Alüminyum", installer)
        self.assertIn("KALDIR.bat", installer)

        self.assertIn("Temiz kaldir", kaldir)
        self.assertIn("Normal kaldir", kaldir)
        self.assertIn(r"%LOCALAPPDATA%\Rigel Alüminyum\Rigel Cost Pro", kaldir)
        self.assertIn(r"%USERPROFILE%\.rigelcost", kaldir)

        self.assertIn("Programı kaldırma", guide)
        self.assertIn("Temiz kaldır", guide)
        self.assertIn("KALDIR.bat", guide)

    def test_installer_createcustomform_is_inno66_compatible(self) -> None:
        """Inno Setup 6.6+ requires CreateCustomForm(w, h, keepX, keepY)."""
        installer = (
            PROJECT_ROOT / "build" / "windows" / "installer.iss"
        ).read_text(encoding="utf-8")
        code = installer.split("[Code]", 1)[-1]

        self.assertNotRegex(
            code,
            r"CreateCustomForm\s*\(\s*\)",
            "CreateCustomForm() is invalid on Inno Setup 6.6+",
        )
        self.assertRegex(
            code,
            r"CreateCustomForm\s*\(\s*ScaleX\s*\(\s*\d+\s*\)\s*,\s*ScaleY\s*\(\s*\d+\s*\)\s*,\s*(True|False)\s*,\s*(True|False)\s*\)",
        )
        self.assertNotRegex(
            code,
            r"\.ClientWidth\s*:=",
            "ClientWidth is read-only after CreateCustomForm in Inno 6.6+",
        )
        self.assertNotRegex(
            code,
            r"\.ClientHeight\s*:=",
            "ClientHeight is read-only after CreateCustomForm in Inno 6.6+",
        )
        self.assertIn("MsgBox(", code)
        self.assertRegex(
            code,
            r"MsgBox\s*\([^;]+,\s*mbConfirmation\s*,\s*MB_YESNO\s*\)",
        )
        self.assertIn("DelTree(Path, True, True, True)", code)
        self.assertIn("RegDeleteKeyIncludingSubkeys(HKCU,", code)


if __name__ == "__main__":
    unittest.main()
