import os
import unittest
from unittest.mock import patch

from field_observer.detector import resolve_device


class DeviceTests(unittest.TestCase):
    def test_explicit_devices_are_kept(self):
        self.assertEqual(resolve_device("cpu"), "cpu")
        self.assertEqual(resolve_device("cuda"), "cuda")

    def test_unknown_device_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "auto, cpu or cuda"):
            resolve_device("gpu")

    def test_auto_uses_the_gpu_only_when_pytorch_can_reach_it(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FIELD_OBSERVER_DEVICE", None)
            with patch("torch.cuda.is_available", return_value=True):
                self.assertEqual(resolve_device("auto"), "cuda")
            with patch("torch.cuda.is_available", return_value=False):
                self.assertEqual(resolve_device("auto"), "cpu")

    def test_environment_setting_can_force_the_cpu(self):
        with patch.dict(os.environ, {"FIELD_OBSERVER_DEVICE": "cpu"}), patch("torch.cuda.is_available", return_value=True):
            self.assertEqual(resolve_device("auto"), "cpu")


if __name__ == "__main__":
    unittest.main()
