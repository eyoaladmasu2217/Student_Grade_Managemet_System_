import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_env_example_documents_every_application_setting() -> None:
    documented = {
        line.split("=", 1)[0]
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    used = set()
    for source in (ROOT / "backend" / "app").glob("*.py"):
        used.update(re.findall(r'os\.getenv\(\s*"(SGMS_[A-Z_]+)"', source.read_text(encoding="utf-8")))

    assert used
    assert used <= documented


def test_security_workflow_is_present() -> None:
    workflow = (ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")

    assert "bandit" in workflow
    assert "pip-audit" in workflow
    assert "npm audit" in workflow
