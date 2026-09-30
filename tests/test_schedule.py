"""以純文字檢查 GitHub Actions 設定（不依賴 YAML 套件，也不連網）。"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAILY = (ROOT / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
COLLECT = (ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")


def job_block(text, name):
    m = re.search(rf"(?ms)^  {name}:\n(.*?)(?=^  \S|\Z)", text)
    assert m, f"job {name} missing"
    return m.group(1)


def step_index(block, needle):
    i = block.find(needle)
    assert i >= 0, f"{needle!r} missing"
    return i


class TestR1DailyOrder(unittest.TestCase):
    def test_R1_cron_and_manual(self):
        self.assertIn('cron: "45 0 * * *"', DAILY)
        self.assertIn("workflow_dispatch:", DAILY)

    def test_R1_command_order_in_build(self):
        build = job_block(DAILY, "build")
        order = [step_index(build, s) for s in (
            "python -m ai_daily fetch", "python -m ai_daily digest", "python -m ai_daily render",
            "git add data", "upload-pages-artifact")]
        self.assertEqual(order, sorted(order))

    def test_R1_digest_retried_once(self):
        build = job_block(DAILY, "build")
        seg = build[step_index(build, "name: Digest"):step_index(build, "name: Render")]
        self.assertIn("python -m ai_daily digest || {", seg)
        self.assertIn("sleep 300; python -m ai_daily digest; }", seg)

    def test_R1_deploy_before_push(self):
        self.assertIn("needs: build", job_block(DAILY, "deploy"))
        notify = job_block(DAILY, "notify")
        self.assertIn("needs: deploy", notify)
        self.assertLess(step_index(notify, "python -m ai_daily push"), step_index(notify, "git add data/push"))
        self.assertNotIn("ai_daily push", job_block(DAILY, "build"))

    def test_R1_digest_failure_keeps_raw_data(self):
        build = job_block(DAILY, "build")
        commit = build[step_index(build, "name: Commit data"):]
        self.assertIn("if: always() && steps.fetch.outcome == 'success'", commit.split("run:")[0])
        for step in ("name: Render", "actions/configure-pages", "actions/upload-pages-artifact"):
            seg = build[step_index(build, step):][:200]
            self.assertIn("steps.digest.outcome == 'success'", seg)


class TestR2Collect(unittest.TestCase):
    def test_R2_schedule_and_private_repo(self):
        self.assertIn('cron: "15 */6 * * *"', COLLECT)
        self.assertIn("repository: arku02/ai-daily-feedback", COLLECT)
        self.assertIn("token: ${{ secrets.FEEDBACK_REPO_TOKEN }}", COLLECT)
        self.assertIn("FEEDBACK_DIR: feedback-repo", COLLECT)
        commit = COLLECT[step_index(COLLECT, "name: Commit feedback"):]
        self.assertIn("working-directory: feedback-repo", commit.split("run:")[0])

    def test_R2_feedback_not_written_to_public_repo(self):
        self.assertNotIn("git add data", COLLECT)
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("feedback/", lines)


class TestR3Concurrency(unittest.TestCase):
    def test_R3_shared_group_no_cancel(self):
        for text in (DAILY, COLLECT):
            self.assertIn("group: ai-daily", text)
            self.assertIn("cancel-in-progress: false", text)


class TestR4Secrets(unittest.TestCase):
    def test_R4_only_known_secrets(self):
        used = set(re.findall(r"secrets\.([A-Z_]+)", DAILY + COLLECT))
        self.assertEqual(used, {"GITHUB_TOKEN", "GEMINI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                                "PROFILE_TOML", "FEEDBACK_REPO_TOKEN"})

    def test_R4_profile_written_not_committed(self):
        self.assertIn('printf \'%s\\n\' "$PROFILE_TOML" > profile.toml', DAILY)
        self.assertIn("profile.toml", (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())
        self.assertNotRegex(DAILY, r"git add[^\n]*(profile|\.env|feedback)")

    def test_R4_minimal_permissions(self):
        perms = re.search(r"(?m)^permissions:\n((?:  [^\n]*\n)+)", DAILY).group(1)
        self.assertEqual(sorted(l.strip() for l in perms.splitlines()),
                         ["contents: write", "id-token: write", "pages: write"])
        perms = re.search(r"(?m)^permissions:\n((?:  [^\n]*\n)+)", COLLECT).group(1)
        self.assertEqual([l.strip() for l in perms.splitlines()], ["contents: read"])


class TestR5FailureNotice(unittest.TestCase):
    def test_R5_every_job_notifies(self):
        for text, jobs in ((DAILY, ("build", "deploy", "notify")), (COLLECT, ("collect",))):
            for job in jobs:
                block = job_block(text, job)
                seg = block[step_index(block, "name: Notify failure"):]
                self.assertIn("if: failure()", seg)
                self.assertIn("sendMessage", seg)
                self.assertIn("RUN_URL", seg)


class TestR6SafeCommits(unittest.TestCase):
    def test_R6_commit_steps(self):
        for text in (DAILY, COLLECT):
            blocks = re.findall(r"(?s)git config user\.name.*?git push", text)
            self.assertTrue(blocks)
            for b in blocks:
                self.assertIn("github-actions[bot]", b)
                self.assertIn("if git diff --cached --quiet; then", b)
                self.assertIn("git pull --rebase", b)
                self.assertNotIn("git add .\n", b)


class TestD1StaticChecks(unittest.TestCase):
    def test_D1_pinned_major_versions(self):
        uses = re.findall(r"uses: (\S+)", DAILY + COLLECT)
        self.assertTrue(uses)
        for u in uses:
            self.assertRegex(u, r"^actions/[a-z-]+@v\d+$")

    def test_D1_test_file_registered(self):
        cfg = json.loads((ROOT / "workflow.config.json").read_text(encoding="utf-8"))
        self.assertIn("tests/test_schedule.py", cfg["testFiles"])


if __name__ == "__main__":
    unittest.main()
