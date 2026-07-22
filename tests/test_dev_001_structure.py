import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_FOLDERS = ["ui", "backend", "database", "secrets", "images", "docs", "tests"]

REQUIRED_DOCS = [
    "problemStatement.md",
    "architecture.md",
    "context.md",
    "Implementation_plan.md",
    "edge_case.md",
    "deployment.md",
]


class TestDev001Structure(unittest.TestCase):
    def test_required_folders_exist(self):
        for folder in REQUIRED_FOLDERS:
            path = os.path.join(ROOT, folder)
            self.assertTrue(os.path.isdir(path), f"Missing folder: {folder}")

    def test_required_doc_files_exist(self):
        for doc in REQUIRED_DOCS:
            path = os.path.join(ROOT, "docs", doc)
            self.assertTrue(os.path.isfile(path), f"Missing doc: docs/{doc}")

    def test_problem_statement_contains_strategic_goal(self):
        path = os.path.join(ROOT, "docs", "problemStatement.md")
        with open(path, "r") as f:
            content = f.read()
        self.assertIn(
            "Strategic goal", content,
            "problemStatement.md missing 'Strategic goal'"
        )
        self.assertIn(
            "AI-Powered Discovery Engine", content,
            "problemStatement.md missing 'AI-Powered Discovery Engine'"
        )

    def test_context_md_exists_and_has_content(self):
        path = os.path.join(ROOT, "docs", "context.md")
        with open(path, "r") as f:
            content = f.read()
        self.assertTrue(len(content.strip()) > 0, "context.md is empty")

    def test_implementation_plan_has_phases(self):
        path = os.path.join(ROOT, "docs", "Implementation_plan.md")
        with open(path, "r") as f:
            content = f.read()
        self.assertIn("Phase 1", content)
        self.assertIn("Phase 2", content)


if __name__ == "__main__":
    unittest.main()
