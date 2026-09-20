"""Run with python3 tests/test_integrate.py; requires Git and Backlog.md."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]
INTEGRATE = SOURCE / ".workflow/bin/integrate"


class IntegrateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="loom-integrate-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "main"
        (self.repo / ".backlog").mkdir(parents=True)
        shutil.copyfile(SOURCE / ".backlog/config.yml", self.repo / ".backlog/config.yml")
        (self.repo / ".gitignore").write_text(".backlog/*\n!.backlog/config.yml\n")
        self.env = {**os.environ, "BACKLOG_CWD": str(self.repo)}
        self.run_command("git", "init", "-q", "-b", "main")
        self.run_command("git", "config", "user.name", "Integration Test")
        self.run_command("git", "config", "user.email", "test@example.invalid")
        self.run_command("git", "config", "commit.gpgsign", "false")
        self.run_command("git", "config", "core.hooksPath", "/dev/null")
        self.run_command("git", "add", ".")
        self.run_command("git", "commit", "-qm", "Initial commit")
        self.original_head = self.run_command("git", "rev-parse", "HEAD").stdout
        self.run_command("backlog", "task", "create", "Add login", "--plain")

    def run_command(self, *args, cwd=None, check=True):
        return subprocess.run(
            args, cwd=cwd or self.repo, env=self.env, check=check,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def make_worker(self, branch):
        worker = Path(self.temp.name) / "worker"
        self.run_command("git", "worktree", "add", "-qb", branch, str(worker), "main")
        (worker / "feature.txt").write_text("login\n")
        self.run_command("git", "add", "feature.txt", cwd=worker)
        self.run_command("git", "commit", "-qm", "feat(auth): 添加登录", cwd=worker)
        return worker

    def status(self, task="task-1"):
        result = self.run_command("backlog", "task", "view", task, "--json")
        return json.loads(result.stdout)["task"]["status"]

    def assert_main_unchanged(self):
        self.assertEqual(self.original_head, self.run_command("git", "rev-parse", "HEAD").stdout)
        self.assertEqual("", self.run_command("git", "status", "--porcelain").stdout)
        self.assertEqual("To Do", self.status())

    def assert_integrated(self, branch, number="1"):
        worker = self.make_worker(branch)
        result = self.run_command(str(INTEGRATE), number, "--", "test", "-f", "feature.txt")
        self.assertIn(f"integrated {branch} ", result.stdout)
        self.assertEqual("login\n", (self.repo / "feature.txt").read_text())
        self.assertEqual("Done", self.status(f"task-{number}"))
        self.assertFalse(worker.exists())
        self.assertEqual("", self.run_command("git", "branch", "--list", branch).stdout)
        self.assertEqual("", self.run_command("git", "status", "--porcelain").stdout)
        self.assertEqual("1", self.run_command("git", "rev-list", "--count", f"{self.original_head.strip()}..HEAD").stdout.strip())

    def test_descriptive_branch_and_exact_task_number(self):
        for branch in ("task/10-other", "task/1.1-child"):
            self.run_command("git", "branch", branch)
        self.assert_integrated("task/1-add-login")
        for branch in ("task/10-other", "task/1.1-child"):
            self.assertIn(branch, self.run_command("git", "branch", "--list", branch).stdout)

    def test_legacy_branch(self):
        self.assert_integrated("task/1")

    def test_subtask_branch(self):
        self.run_command("backlog", "task", "create", "Login form", "-p", "task-1", "--plain")
        self.run_command("git", "branch", "task/1-add-login")
        self.assert_integrated("task/1.1-login-form", "1.1")

    def test_ambiguous_branches_are_rejected(self):
        self.run_command("git", "branch", "task/1-add-login")
        for other in ("task/1", "task/1-fix-login"):
            with self.subTest(other=other):
                self.run_command("git", "branch", other)
                result = self.run_command(str(INTEGRATE), "1", check=False)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("multiple branches for task-1", result.stderr)
                self.assert_main_unchanged()
                self.run_command("git", "branch", "-D", other)

    def test_missing_branch_does_not_match_other_tasks(self):
        for branch in ("task/10-other", "task/1.1-child", "task/1-"):
            self.run_command("git", "branch", branch)
        result = self.run_command(str(INTEGRATE), "1", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("no branch found for task-1", result.stderr)
        self.assert_main_unchanged()

    def test_failed_check_preserves_descriptive_branch(self):
        worker = self.make_worker("task/1-add-login")
        result = self.run_command(str(INTEGRATE), "1", "--", "false", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("check failed on the merged tree", result.stderr)
        self.assert_main_unchanged()
        self.assertTrue(worker.exists())
        self.assertIn("task/1-add-login", self.run_command("git", "branch", "--list", "task/1-add-login").stdout)


if __name__ == "__main__":
    unittest.main()
