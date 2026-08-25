import os

from vaulty.config import load_environment


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
