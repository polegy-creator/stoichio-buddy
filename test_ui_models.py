import unittest

from stoichio.ui_models import target_lifecycle_status


class UiModelTests(unittest.TestCase):
    def test_target_lifecycle_status_uses_lab_filter_labels(self):
        self.assertEqual(
            target_lifecycle_status({"recipes": [{}], "densities": [{}]}),
            "Completed",
        )
        self.assertEqual(
            target_lifecycle_status({"recipes": [{}], "densities": []}),
            "Powder masses",
        )
        self.assertEqual(
            target_lifecycle_status({"recipes": [], "densities": [{}]}),
            "Density",
        )


if __name__ == "__main__":
    unittest.main()
