import os
from pathlib import Path

from vaulty.config import load_config, load_environment


def test_load_environment_reads_dotenv_without_overriding_host_value(
    tmp_path, monkeypatch
):
    env_file = tmp_path / ".env"
    env_file.write_text("GH_TOKEN=from-test-file\n", encoding="utf-8")

    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert load_environment(env_file)
    assert os.environ["GH_TOKEN"] == "from-test-file"

    monkeypatch.setenv("GH_TOKEN", "from-host")
    assert load_environment(env_file)
    assert os.environ["GH_TOKEN"] == "from-host"


def test_load_config_prefers_yml(tmp_path: Path):
    yml = tmp_path / "vaulty.yml"
    yaml = tmp_path / "vaulty.yaml"
    yaml.write_text(f"root: {tmp_path / 'legacy'}\n", encoding="utf-8")
    yml.write_text(f"root: {tmp_path / 'new'}\n", encoding="utf-8")

    config = load_config(yml)
    assert config.root == tmp_path / "new"


def test_load_config_falls_back_to_legacy_yaml(tmp_path: Path):
    legacy = tmp_path / "vaulty.yaml"
    legacy.write_text(f"root: {tmp_path / 'legacy'}\n", encoding="utf-8")
    missing = tmp_path / "vaulty.yml"

    config = load_config(missing)
    assert config.root == tmp_path / "legacy"
