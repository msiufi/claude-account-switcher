"""Tests for the profile-switching logic. Run from the python/ folder:

    python -m unittest discover tests

Claude's process control is stubbed and HOME/APPDATA point at a temporary folder.
"""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


class SwitcherTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA")}
        os.environ.update(HOME=str(root), USERPROFILE=str(root),
                          APPDATA=str(root / "Roaming"), LOCALAPPDATA=str(root / "Local"))
        sys.path.insert(0, str(HERE))
        sys.modules.pop("claude_switcher", None)
        self.cs = importlib.import_module("claude_switcher")
        self.cs.launch_claude = lambda state: None
        self.cs.quit_claude = lambda timeout=20: True
        self.cs.claude_running = lambda: False

        self.data = self.cs.claude_data_dir(self.cs.load_state())
        self.data.mkdir(parents=True)
        (self.data / "Cookies").write_text("session-A")
        (self.data / "claude_desktop_config.json").write_text('{"mcpServers":{}}')

    def tearDown(self):
        sys.path.remove(str(HERE))
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def st(self):
        return self.cs.load_state()

    def test_round_trip(self):
        cs = self.cs
        cs.save_current_as(self.st(), "personal")
        cs.switch_to(self.st(), "work", fresh=True)
        self.assertFalse((self.data / "Cookies").exists())
        self.assertEqual((self.data / "claude_desktop_config.json").read_text(), '{"mcpServers":{}}')

        (self.data / "Cookies").write_text("session-B")
        cs.switch_to(self.st(), "personal")
        self.assertEqual((self.data / "Cookies").read_text(), "session-A")
        cs.switch_to(self.st(), "work")
        self.assertEqual((self.data / "Cookies").read_text(), "session-B")

    def test_guards_and_management(self):
        cs = self.cs
        cs.save_current_as(self.st(), "personal")
        cs.switch_to(self.st(), "work", fresh=True)
        with self.assertRaises(ValueError):
            cs.switch_to(self.st(), "work", fresh=True)
        with self.assertRaises(ValueError):
            cs.delete_profile(self.st(), "work")
        with self.assertRaises(ValueError):
            cs.save_current_as(self.st(), "../escape")

        cs.rename_profile(self.st(), "personal", "home")
        cs.switch_to(self.st(), "home")
        self.assertEqual((self.data / "Cookies").read_text(), "session-A")
        cs.delete_profile(self.st(), "work")
        self.assertEqual(cs.list_profiles(self.st()), ["home"])


if __name__ == "__main__":
    unittest.main()
