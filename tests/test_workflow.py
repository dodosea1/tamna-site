import unittest
from pathlib import Path

WF = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "pages.yml"


class WorkflowTest(unittest.TestCase):
    def test_pages_are_enabled_on_first_run_and_deploys_are_not_cancelled(self):
        text = WF.read_text(encoding="utf-8")
        self.assertIn("enablement: true", text)
        self.assertIn("cancel-in-progress: false", text)


if __name__ == "__main__":
    unittest.main()
