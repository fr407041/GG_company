from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class DashboardLauncherTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "PowerShell launcher regression is Windows-specific")
    def test_start_dashboard_normalizes_duplicate_path_environment(self) -> None:
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if not powershell:
            self.skipTest("PowerShell is not available")

        script = ROOT / "agent_os_mvp" / "start-dashboard.ps1"
        completed = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-SelfTestEnvironmentNormalization",
            ],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
        self.assertEqual(0, completed.returncode, completed.stdout)
        self.assertIn("Environment normalization self-test passed.", completed.stdout)


if __name__ == "__main__":
    unittest.main()
