import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import kilo_manager


class KiloManagerCoreTests(unittest.TestCase):
    def test_resolve_config_path_prefers_cli_then_env_then_xdg(self):
        with mock.patch.dict(os.environ, {"KILO_CONFIG_PATH": "/tmp/env.jsonc", "XDG_CONFIG_HOME": "/tmp/xdg"}, clear=False):
            self.assertEqual(kilo_manager.resolve_config_path("/tmp/cli.jsonc"), Path("/tmp/cli.jsonc"))
            self.assertEqual(kilo_manager.resolve_config_path(None), Path("/tmp/env.jsonc"))
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/xdg"}, clear=True):
            os.environ.pop("KILO_CONFIG_PATH", None)
            self.assertEqual(kilo_manager.resolve_config_path(None), Path("/tmp/xdg/kilo/kilo.jsonc"))

    def test_resolve_skills_dir_env_then_home(self):
        with mock.patch.dict(os.environ, {"KILO_SKILLS_DIR": "/tmp/skills"}, clear=False):
            self.assertEqual(kilo_manager.resolve_skills_dir(), Path("/tmp/skills"))
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("KILO_SKILLS_DIR", None)
            self.assertEqual(kilo_manager.resolve_skills_dir(), Path.home() / ".agents" / "skills")

    def _manager(self, config_path, skills_dir):
        mgr = kilo_manager.KiloManager.__new__(kilo_manager.KiloManager)
        mgr.config_path = Path(config_path)
        mgr.skills_dir = Path(skills_dir)
        mgr.config = {"mcp": {"servers": {}}, "permission": {"bash": {}, "external_directory": {}}}
        mgr._config_readonly = False
        return mgr

    def test_load_config_missing_returns_default_not_readonly(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = self._manager(Path(td) / "missing.jsonc", Path(td) / "skills")
            with mock.patch.object(kilo_manager.Messagebox, "show_error") as show_error:
                cfg = kilo_manager.KiloManager.load_config(mgr)
            self.assertEqual(cfg["mcp"]["servers"], {})
            self.assertFalse(mgr._config_readonly)
            show_error.assert_not_called()

    def test_load_config_corrupt_marks_readonly_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "kilo.jsonc"
            path.write_text("{ not: valid json", encoding="utf-8")
            mgr = self._manager(path, Path(td) / "skills")
            with mock.patch.object(kilo_manager.Messagebox, "show_error") as show_error:
                cfg = kilo_manager.KiloManager.load_config(mgr)
            self.assertTrue(mgr._config_readonly)
            self.assertEqual(cfg["mcp"]["servers"], {})
            show_error.assert_called()

    def test_save_config_atomic_replace_and_valid_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "kilo.jsonc"
            mgr = self._manager(path, Path(td) / "skills")
            mgr.config["mcp"]["servers"]["s1"] = {"type": "local", "command": ["echo", "hi"], "enabled": True}
            with mock.patch.object(kilo_manager.Messagebox, "show_info"):
                ok = kilo_manager.KiloManager.save_config(mgr)
            self.assertTrue(ok)
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["mcp"]["servers"]["s1"]["command"], ["echo", "hi"])
            leftovers = [p for p in Path(td).iterdir() if p.name != path.name]
            self.assertEqual(leftovers, [])

    def test_save_config_readonly_refuses(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "kilo.jsonc"
            path.write_text("{bad", encoding="utf-8")
            mgr = self._manager(path, Path(td) / "skills")
            mgr._config_readonly = True
            with mock.patch.object(kilo_manager.Messagebox, "show_error") as show_error:
                ok = kilo_manager.KiloManager.save_config(mgr)
            self.assertFalse(ok)
            self.assertEqual(path.read_text(encoding="utf-8"), "{bad")
            show_error.assert_called()

    def test_save_config_failure_leaves_original_intact(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "kilo.jsonc"
            original = json.dumps({"mcp": {"servers": {"x": {"type": "remote", "url": "http://a"}}}}, indent=2)
            path.write_text(original, encoding="utf-8")
            mgr = self._manager(path, Path(td) / "skills")
            mgr.config = {"mcp": {"servers": {"x": {"type": "remote", "url": "http://a"}}}}
            with mock.patch("kilo_manager.json.dump", side_effect=TypeError("serialization failure")):
                with mock.patch.object(kilo_manager.Messagebox, "show_error"):
                    ok = kilo_manager.KiloManager.save_config(mgr)
            self.assertFalse(ok)
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            leftovers = [p for p in Path(td).iterdir() if p.name != path.name]
            self.assertEqual(leftovers, [])

    def test_get_skills_uses_instance_dir(self):
        with tempfile.TemporaryDirectory() as td:
            skills_dir = Path(td) / "skills"
            (skills_dir / "skill-a").mkdir(parents=True)
            (skills_dir / "skill-a" / "SKILL.md").write_text("# A\n\nDesc", encoding="utf-8")
            (skills_dir / "skill-b").mkdir(parents=True)
            mgr = self._manager(Path(td) / "kilo.jsonc", skills_dir)
            skills = kilo_manager.KiloManager.get_skills(mgr)
            by_name = {s["name"]: s for s in skills}
            self.assertTrue(by_name["skill-a"]["enabled"])
            self.assertFalse(by_name["skill-b"]["enabled"])


if __name__ == "__main__":
    unittest.main()
