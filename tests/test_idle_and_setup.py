import os
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import patch, Mock

from vk03_appearance_editor import preview_renderer
from vk03_config import empty_bindings, save_config

ROOT = Path(__file__).resolve().parents[1]


class IdleTests(unittest.TestCase):
    def test_actual_loop_wake_consumed_and_30_second_idle(self):
        ns = preview_renderer(ROOT)
        ns["appearance"].close()
        class Clock:
            now = 0
            def monotonic(self): return self.now
            def time(self): return 100 + self.now
        clock = Clock()
        events = iter([(0, [0, 1, 0, 0, 0, 0, 0]), (1, [0, 0, 0, 0, 0, 0, 0]),
                       (2, [0, 1, 0, 0, 0, 0, 0]), (3, [0, 0, 0, 0, 0, 0, 0]),
                       (31, []), (32, []), (33, [0, 1, 0, 0, 0, 0, 0])])
        observed, actions = [], []
        class Touch:
            def read(self, *args):
                observed.append((clock.now, ns["page"]))
                try:
                    clock.now, data = next(events)
                    return data
                except StopIteration:
                    raise KeyboardInterrupt
        class Theme:
            animated = False
            media = None
            settings = {"animation_fps": 15}
            def refresh(self): return False
            def content_changed(self): return False
            def close(self): pass
        class Collector:
            def __init__(self, *args): pass
            def start(self): pass
            def close(self): pass
            def snapshot(self): return {}
        with tempfile.TemporaryDirectory() as directory:
            cleaned = []
            ns.update(os=os, time=clock, print=Mock(), PCMonitor=Collector, page="monitor", touch=Touch(),
                      appearance=Theme(), ha_worker=lambda: None, ha_results=queue.Queue(),
                      APP_DIR=Path(directory), current_frame=b"initial", fid=0,
                      send_frame=lambda *args: None, render_ui=lambda: None, encode_frame=lambda img: b"frame",
                      decode_touch=lambda raw: (100, 100, 0, 0), hit_test=lambda *args: "light_1",
                      handle_action=lambda action: actions.append(action) or True,
                      cleanup_hardware=lambda: cleaned.append(True))
            source = (ROOT / "vk03_home_panel_daily.py").read_text(encoding="utf-8")
            exec(source[source.index("KEEPALIVE_SECONDS = 1.0"):], ns)
            self.assertEqual(actions, ["light_1"])
            self.assertIn((31, "home"), observed)
            self.assertIn((32, "monitor"), observed)
            self.assertEqual(ns["page"], "home")
            self.assertEqual(cleaned, [True])


@unittest.skipUnless(os.name == "nt", "Windows control center")
class SetupTests(unittest.TestCase):
    def test_installed_venv_precedes_global_python(self):
        import vk03_app
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            runtime=root/".venv"/"Scripts"/"pythonw.exe"
            runtime.parent.mkdir(parents=True)
            runtime.touch()
            with patch("vk03_app.ROOT",root), patch("vk03_app.subprocess.run") as run:
                self.assertEqual(vk03_app.find_python(),str(runtime))
                run.assert_not_called()

    def test_first_start_opens_wizard_without_starting_hardware(self):
        import vk03_app
        app = vk03_app.App.__new__(vk03_app.App)
        app.stopping = False
        app.open_device_setup = Mock()
        with tempfile.TemporaryDirectory() as directory, patch("vk03_app.ROOT", Path(directory)), patch("vk03_app.subprocess.Popen") as popen:
            app.start_panel()
            app.open_device_setup.assert_called_once()
            popen.assert_not_called()

    def test_mapping_save_requests_stop_before_restart(self):
        import vk03_app
        app = vk03_app.App.__new__(vk03_app.App)
        app.stop_panel = Mock()
        app.configuration_saved()
        self.assertTrue(app.restart_after_stop)
        app.stop_panel.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
