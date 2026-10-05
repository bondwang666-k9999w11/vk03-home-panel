import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest

from vk03_monitor import cpu_temperature, shared_stats, EMPTY

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("public_audit", ROOT / "tools" / "check_public_tree.py")
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


class PrivacyAndTelemetryTests(unittest.TestCase):
    def test_public_tree_has_no_runtime_or_personal_data(self):
        self.assertEqual(audit_module.audit(ROOT), [])

    def test_audit_detects_private_artifact_without_printing_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "vk03_config.json").write_text("test-only-private-value")
            findings = audit_module.audit(Path(directory))
            self.assertTrue(findings)
            self.assertNotIn("test-only-private-value", " ".join(findings))

    def test_live_and_stale_metrics_and_self_test_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(shared_stats(root), EMPTY)
            pc = root / "vk03_pc_sensor.json"
            pc.write_text(json.dumps(dict(timestamp=time.time(), values=dict(cpu_temp=52, memory_usage=25))))
            self.assertEqual(shared_stats(root)["cpu_temp"], 52)
            pc.write_text(json.dumps(dict(timestamp=time.time() - 6, values=dict(cpu_temp=52))))
            self.assertIsNone(shared_stats(root)["cpu_temp"])
            cpu = root / "vk03_cpu_sensor.json"
            cpu.write_text(json.dumps(dict(timestamp=100, cpu_temp=42.5, error="self-test")))
            self.assertIsNone(cpu_temperature(root, 100))
            cpu.write_text(json.dumps(dict(timestamp=100, cpu_temp=42.5, error="")))
            self.assertEqual(cpu_temperature(root, 100), 42.5)
            self.assertIsNone(cpu_temperature(root, 106))


if __name__ == "__main__":
    unittest.main()
