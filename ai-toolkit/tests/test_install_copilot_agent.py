import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class InstallerTests(unittest.TestCase):
    components = {
        ".github/skills/pn-infra/SKILL.md": "# Fixture skill\n",
        ".github/agents/pn-infra.agent.md": "# Fixture agent\n",
        ".github/instructions/pn-infra-ai-toolkit.instructions.md": "# Fixture instructions\n",
        ".github/prompts/pn-infra-agent-plan.prompt.md": "# Fixture plan prompt\n",
        ".github/prompts/pn-infra-agent-implement.prompt.md": "# Fixture implement prompt\n",
    }

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="pn-infra-installer-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = self.root / "source repository"
        self.workspace = self.root / "target workspace"
        self.workspace.mkdir()
        self.installer = self.repository / "ai-toolkit/scripts/install-copilot-agent.sh"
        self.installer.parent.mkdir(parents=True)
        source = Path(__file__).resolve().parents[1] / "scripts/install-copilot-agent.sh"
        shutil.copyfile(source, self.installer)
        for relative, content in self.components.items():
            self.write_file(self.repository / relative, content)

    def write_file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def run_installer(self, success: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["bash", str(self.installer), str(self.workspace)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        if success:
            self.assertEqual(result.returncode, 0, output)
        else:
            self.assertNotEqual(result.returncode, 0, output)
            self.assertFalse((self.workspace / ".pn-infra-toolkit-backups").exists())
            self.assertFalse((self.workspace / ".github/skills").exists())
        return result

    def test_fresh_install_preserves_unrelated_content(self) -> None:
        unrelated = {
            ".github/prompts/other.prompt.md": "Existing unrelated prompt\n",
            ".github/skills/other/SKILL.md": "Existing unrelated skill\n",
            ".vscode/settings.json": '{"existing": true}\n',
        }
        for relative, content in unrelated.items():
            self.write_file(self.workspace / relative, content)

        self.run_installer()

        for relative, content in {**self.components, **unrelated}.items():
            with self.subTest(path=relative):
                self.assertEqual(
                    (self.workspace / relative).read_text(encoding="utf-8"), content
                )

    def test_update_backs_up_each_owned_prompt(self) -> None:
        prompts = [path for path in self.components if path.startswith(".github/prompts/")]
        for relative in prompts:
            self.write_file(self.workspace / relative, "Old prompt\n")

        self.run_installer()

        backups = list((self.workspace / ".pn-infra-toolkit-backups").glob("install-*"))
        self.assertEqual(len(backups), 1)
        for relative in prompts:
            with self.subTest(path=relative):
                self.assertEqual(
                    (backups[0] / "previous" / relative).read_text(encoding="utf-8"),
                    "Old prompt\n",
                )
                self.assertEqual(
                    (self.workspace / relative).read_text(encoding="utf-8"),
                    self.components[relative],
                )

    def test_unchanged_install_does_not_create_another_backup(self) -> None:
        self.run_installer()
        backup_root = self.workspace / ".pn-infra-toolkit-backups"
        before = sorted(backup_root.iterdir())

        result = self.run_installer()

        self.assertEqual(sorted(backup_root.iterdir()), before)
        for relative in self.components:
            component = (
                ".github/skills/pn-infra"
                if relative.endswith("/SKILL.md")
                else relative
            )
            self.assertIn(f"Already current: {component}", result.stdout)

    def test_missing_prompt_fails_before_writes(self) -> None:
        for relative, content in self.components.items():
            if not relative.startswith(".github/prompts/"):
                continue
            with self.subTest(path=relative):
                source = self.repository / relative
                source.unlink()
                result = self.run_installer(success=False)
                self.assertIn("Missing source", result.stderr)
                self.assertFalse((self.workspace / ".github").exists())
                self.write_file(source, content)

    def test_prompt_directory_symlink_is_rejected(self) -> None:
        external = self.root / "external prompts"
        external.mkdir()
        prompts = self.workspace / ".github/prompts"
        prompts.parent.mkdir()
        prompts.symlink_to(external, target_is_directory=True)

        result = self.run_installer(success=False)

        self.assertIn("Unsupported directory or symbolic link", result.stderr)
        self.assertEqual(list(external.iterdir()), [])
        self.assertTrue(prompts.is_symlink())

    def test_owned_prompt_symlink_is_rejected(self) -> None:
        external = self.root / "external prompt.md"
        external.write_text("Keep me\n", encoding="utf-8")
        prompt = self.workspace / ".github/prompts/pn-infra-agent-plan.prompt.md"
        prompt.parent.mkdir(parents=True)
        prompt.symlink_to(external)

        result = self.run_installer(success=False)

        self.assertIn("unsupported symbolic link", result.stderr)
        self.assertEqual(external.read_text(encoding="utf-8"), "Keep me\n")
        self.assertTrue(prompt.is_symlink())

    def test_prompt_source_must_be_a_file(self) -> None:
        prompt = self.repository / ".github/prompts/pn-infra-agent-plan.prompt.md"
        prompt.unlink()
        prompt.mkdir()

        result = self.run_installer(success=False)

        self.assertIn("Unexpected source type", result.stderr)
        self.assertFalse((self.workspace / ".github").exists())

    def test_prompt_destination_must_be_a_file(self) -> None:
        prompt = self.workspace / ".github/prompts/pn-infra-agent-plan.prompt.md"
        prompt.mkdir(parents=True)

        result = self.run_installer(success=False)

        self.assertIn("Unexpected destination type", result.stderr)
        self.assertTrue(prompt.is_dir())


if __name__ == "__main__":
    unittest.main(verbosity=2)
