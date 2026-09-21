"""Run with python3 tests/test_integrate.py; requires Git and Backlog.md."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
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
        self.run_command("git", "config", "core.hooksPath", str(self.repo / ".git/disabled-hooks"))
        self.run_command("git", "add", ".")
        self.run_command("git", "commit", "-qm", "Initial commit")
        self.original_head = self.run_command("git", "rev-parse", "HEAD").stdout
        self.run_command("backlog", "task", "create", "Add login", "--plain")

    def run_command(self, *args, cwd=None, check=True):
        if args[0] == str(INTEGRATE):
            args = (sys.executable, *args)
        else:
            args = (shutil.which(args[0]) or args[0], *args[1:])
        return subprocess.run(
            args, cwd=cwd or self.repo, env=self.env, check=check,
            encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def make_worker(self, branch, name="feature.txt"):
        worker = Path(self.temp.name) / "worker"
        self.run_command("git", "worktree", "add", "-qb", branch, str(worker), "main")
        (worker / name).write_text("login\n")
        self.run_command("git", "add", name, cwd=worker)
        self.run_command("git", "commit", "-qm", "feat(auth): 添加登录", cwd=worker)
        return worker

    def status(self, task="task-1"):
        result = self.run_command("backlog", "task", "view", task, "--json")
        return json.loads(result.stdout)["task"]["status"]

    def assert_main_unchanged(self):
        self.assertEqual(self.original_head, self.run_command("git", "rev-parse", "HEAD").stdout)
        self.assertEqual("", self.run_command("git", "status", "--porcelain").stdout)
        self.assertEqual("To Do", self.status())

    def assert_integrated(self, branch, number="1", prepare=None, checks=None):
        worker = self.make_worker(branch)
        if prepare:
            prepare(worker)
        if checks is None:
            checks = [sys.executable, "-c", "from pathlib import Path; assert Path('feature.txt').is_file()"]
        result = self.run_command(str(INTEGRATE), number, "--", *checks)
        self.assertIn(f"integrated {branch} ", result.stdout)
        self.assertEqual("login\n", (self.repo / "feature.txt").read_text())
        self.assertEqual("feat(auth): 添加登录\n", self.run_command("git", "log", "-1", "--format=%s").stdout)
        self.assertEqual("Done", self.status(f"task-{number}"))
        self.assertTrue(list((self.repo / ".backlog/completed").glob(f"task-{number} - *")))
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

    def test_completed_dependency_does_not_block(self):
        self.run_command("backlog", "task", "create", "Add logout", "--dep", "task-1", "--plain")
        self.assert_integrated("task/1-add-login")
        self.make_worker("task/2-add-logout", "logout.txt")
        result = self.run_command(str(INTEGRATE), "2")
        self.assertIn("integrated task/2-add-logout ", result.stdout)

    def test_read_only_tree_in_worktree_is_cleaned_up(self):
        # Go's module cache is written read-only inside the worktree.
        (self.repo / ".git/info").mkdir(exist_ok=True)
        (self.repo / ".git/info/exclude").write_text("cache/\n")

        def add_read_only_cache(worker):
            cache = worker / "cache"
            cache.mkdir()
            (cache / "module.txt").write_text("cached\n")
            (cache / "module.txt").chmod(0o444)
            cache.chmod(0o555)

        self.assert_integrated("task/1-add-login", prepare=add_read_only_cache)

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

    def test_conflict_leaves_main_unchanged(self):
        worker = self.make_worker("task/1-add-login")
        (self.repo / "feature.txt").write_text("other\n")
        self.run_command("git", "add", "feature.txt")
        self.run_command("git", "commit", "-qm", "Add feature on main")
        self.original_head = self.run_command("git", "rev-parse", "HEAD").stdout
        result = self.run_command(str(INTEGRATE), "1", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("conflicts with main in: feature.txt ", result.stderr)
        self.assert_main_unchanged()
        self.assertTrue(worker.exists())

    def test_failed_check_preserves_descriptive_branch(self):
        worker = self.make_worker("task/1-add-login")
        first = Path(self.temp.name) / "first-check"
        last = Path(self.temp.name) / "last-check"
        touch = "from pathlib import Path; import sys; Path(sys.argv[1]).touch()"
        result = self.run_command(
            str(INTEGRATE), "1", "--", sys.executable, "-c", touch, str(first),
            "--next-check", sys.executable, "-c", "import sys; sys.exit(23)",
            "--next-check", sys.executable, "-c", touch, str(last), check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("check failed on the merged tree", result.stderr)
        self.assertTrue(first.exists())
        self.assertFalse(last.exists())
        self.assert_main_unchanged()
        self.assertTrue(worker.exists())
        self.assertIn("task/1-add-login", self.run_command("git", "branch", "--list", "task/1-add-login").stdout)

    def test_check_arguments_are_passed_literally(self):
        arguments = ["two words", 'a "quote"', "", "中文", ";", "&&", "|", ">", "$HOME", "*.txt", "--", "--runInBand"]
        code = f"import sys; assert sys.argv[1:] == {arguments!r}, sys.argv"
        self.assert_integrated("task/1-add-login", checks=[sys.executable, "-c", code, *arguments])

    def test_checks_run_in_order_before_commit(self):
        marker = Path(self.temp.name) / "check order.txt"
        first = "from pathlib import Path; import sys; assert Path('feature.txt').is_file(); Path(sys.argv[1]).write_text('checked')"
        second = "from pathlib import Path; import sys; assert Path(sys.argv[1]).read_text() == 'checked'"
        self.assert_integrated("task/1-add-login", checks=[
            sys.executable, "-c", first, str(marker),
            "--next-check", sys.executable, "-c", second, str(marker),
        ])

    def test_invalid_check_executable_restores_main(self):
        worker = self.make_worker("task/1-add-login")
        for executable in ("loom-check-does-not-exist", "echo checking; false"):
            with self.subTest(executable=executable):
                result = self.run_command(str(INTEGRATE), "1", "--", executable, check=False)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("check executable not found", result.stderr)
                self.assert_main_unchanged()
                self.assertTrue(worker.exists())

    def test_empty_check_is_rejected(self):
        self.make_worker("task/1-add-login")
        for checks in (
            ["--"],
            ["--", "--next-check", sys.executable, "--version"],
            ["--", sys.executable, "--version", "--next-check"],
            ["--", sys.executable, "--version", "--next-check", "--next-check", sys.executable, "--version"],
        ):
            with self.subTest(checks=checks):
                result = self.run_command(str(INTEGRATE), "1", *checks, check=False)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("empty check command", result.stderr)
                self.assert_main_unchanged()


if __name__ == "__main__":
    unittest.main()
