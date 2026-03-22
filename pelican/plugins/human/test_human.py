"""Tests for the Human plugin."""

from datetime import date
import json
import logging
from pathlib import Path
import tomllib

import pytest

from pelican import Pelican
from pelican.plugins.human.human import (
    generate_human_json,
    validate_url,
    vouchfor_cli,
)
from pelican.settings import read_settings

TEST_DATA_DIR = Path(__file__).parent / "test_data"
EXPECTED_OUTPUT = TEST_DATA_DIR / "human.json"


@pytest.fixture(autouse=True, scope="session")
def _disable_pelican_log_dedup():
    """Disable Pelican's LimitFilter so repeated log messages aren't suppressed."""
    logger = logging.getLogger("pelican.plugins.human.human")
    logger.disable_filter()


# === Unit tests: URL validation ===


class TestValidateUrl:
    """Tests for URL validation logic."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com",
            "http://example.com",
            "https://example.com/path/to/page",
            "https://example.com/@user",
        ],
    )
    def test_valid_urls(self, url):
        assert validate_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "example.com",
            "ftp://example.com",
            "",
            "https://",
            "https:",
        ],
    )
    def test_invalid_urls(self, url):
        assert validate_url(url) is False


# === Unit tests: human.json generation ===


class TestGenerateHumanJson:
    """Tests for the Pelican signal handler that generates human.json."""

    @staticmethod
    def _make_pelican(content_path, output_path, site_url=""):
        class PelicanTest:
            def __init__(self):
                self.settings = {
                    "PATH": str(content_path),
                    "OUTPUT_PATH": str(output_path),
                    "SITEURL": site_url,
                }

        return PelicanTest()

    @staticmethod
    def _write_toml(content_path, toml_text):
        data_dir = content_path / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "human.toml").write_text(toml_text)

    def test_generates_correct_output(self, tmp_path):
        content = tmp_path / "content"
        self._write_toml(
            content,
            '["Alice"]\nurl="https://alice.example.com"\ndate="2026-01-01"\n\n'
            '["Bob"]\nurl="https://bob.example.com"\ndate="2026-02-15"\n',
        )
        output = tmp_path / "output"

        generate_human_json(self._make_pelican(content, output, "https://mysite.com"))

        result = json.loads((output / "human.json").read_text())
        assert result["version"] == "0.1.1"
        assert result["url"] == "https://mysite.com"
        assert len(result["vouches"]) == 2
        assert result["vouches"][0] == {
            "url": "https://alice.example.com",
            "vouched_at": "2026-01-01",
        }
        assert result["vouches"][1] == {
            "url": "https://bob.example.com",
            "vouched_at": "2026-02-15",
        }

    def test_skips_when_no_toml(self, tmp_path, caplog):
        content = tmp_path / "content"
        content.mkdir()
        output = tmp_path / "output"
        output.mkdir()

        with caplog.at_level(logging.INFO):
            generate_human_json(self._make_pelican(content, output))

        assert not (output / "human.json").exists()
        assert "human.toml not found" in caplog.text

    def test_skips_when_siteurl_empty(self, tmp_path, caplog):
        content = tmp_path / "content"
        self._write_toml(
            content, '["Test"]\nurl="https://test.com"\ndate="2026-01-01"\n'
        )
        output = tmp_path / "output"

        with caplog.at_level(logging.INFO):
            generate_human_json(self._make_pelican(content, output, ""))

        assert not (output / "human.json").exists()
        assert "SITEURL is missing or invalid" in caplog.text

    def test_skips_when_siteurl_invalid(self, tmp_path, caplog):
        content = tmp_path / "content"
        self._write_toml(
            content, '["Test"]\nurl="https://test.com"\ndate="2026-01-01"\n'
        )
        output = tmp_path / "output"

        with caplog.at_level(logging.INFO):
            generate_human_json(self._make_pelican(content, output, "not-a-url"))

        assert not (output / "human.json").exists()
        assert "SITEURL is missing or invalid" in caplog.text

    def test_creates_output_directory(self, tmp_path):
        content = tmp_path / "content"
        self._write_toml(
            content, '["Test"]\nurl="https://test.com"\ndate="2026-01-01"\n'
        )
        output = tmp_path / "output" / "nested"

        generate_human_json(self._make_pelican(content, output, "https://mysite.com"))

        assert (output / "human.json").exists()

    def test_skips_when_entry_missing_date(self, tmp_path, caplog):
        content = tmp_path / "content"
        self._write_toml(content, '["NoDate"]\nurl="https://nodate.com"\n')
        output = tmp_path / "output"

        with caplog.at_level(logging.WARNING):
            generate_human_json(
                self._make_pelican(content, output, "https://mysite.com")
            )

        assert not (output / "human.json").exists()
        assert "missing required field(s): date" in caplog.text

    def test_skips_when_entry_missing_url(self, tmp_path, caplog):
        content = tmp_path / "content"
        self._write_toml(content, '["NoURL"]\ndate="2026-01-01"\n')
        output = tmp_path / "output"

        with caplog.at_level(logging.WARNING):
            generate_human_json(
                self._make_pelican(content, output, "https://mysite.com")
            )

        assert not (output / "human.json").exists()
        assert "missing required field(s): url" in caplog.text

    def test_reports_all_malformed_entries(self, tmp_path, caplog):
        content = tmp_path / "content"
        self._write_toml(
            content,
            '["NoDate"]\nurl="https://nodate.com"\n\n["NoURL"]\ndate="2026-01-01"\n',
        )
        output = tmp_path / "output"

        with caplog.at_level(logging.WARNING):
            generate_human_json(
                self._make_pelican(content, output, "https://mysite.com")
            )

        assert not (output / "human.json").exists()
        assert "'NoDate'" in caplog.text
        assert "missing required field(s): date" in caplog.text
        assert "'NoURL'" in caplog.text
        assert "missing required field(s): url" in caplog.text


# === Unit tests: vouchfor CLI ===


@pytest.fixture()
def run_cli(tmp_path):
    """Return a helper that runs the `vouchfor` CLI.

    Runs vouchfor with given arguments and optional interactive inputs,
    inside a temporary directory with content/data/ created.
    """
    base_path = tmp_path / "content"
    (base_path / "data").mkdir(parents=True)

    def _run(argv, inputs=None):
        if inputs is not None:
            responses = iter(inputs)
            input_fn = lambda prompt: next(responses)  # noqa: E731
        else:
            input_fn = input
        vouchfor_cli(argv=argv, input_fn=input_fn, base_path=base_path)
        return (base_path / "data" / "human.toml").read_text()

    return _run


class TestVouchforCli:
    """Tests for the vouchfor command-line tool."""

    def test_with_url_and_name(self, run_cli):
        content = run_cli(["--url", "https://example.com", "--name", "Example"])
        assert '["Example"]' in content
        assert 'url="https://example.com"' in content
        assert f'date="{date.today().isoformat()}"' in content

    def test_with_url_only_defaults_to_empty_name(self, run_cli):
        content = run_cli(["--url", "https://example.com"])
        assert '[""]' in content
        assert 'url="https://example.com"' in content

    def test_name_only_prompts_for_url(self, run_cli):
        content = run_cli(["--name", "My Site"], inputs=["https://mysite.com"])
        assert '["My Site"]' in content
        assert 'url="https://mysite.com"' in content

    def test_interactive_prompts_for_url_and_name(self, run_cli):
        content = run_cli([], inputs=["https://example.com", "Example Site"])
        assert '["Example Site"]' in content
        assert 'url="https://example.com"' in content

    def test_interactive_retries_on_invalid_url(self, run_cli, capsys):
        content = run_cli(
            [], inputs=["not-a-url", "also bad", "https://example.com", "Name"]
        )
        assert 'url="https://example.com"' in content
        captured = capsys.readouterr()
        assert captured.out.count("Invalid URL") == 2

    def test_interactive_empty_name_on_enter(self, run_cli):
        content = run_cli([], inputs=["https://example.com", ""])
        assert '[""]' in content

    def test_invalid_url_arg_exits(self, run_cli):
        with pytest.raises(SystemExit) as exc_info:
            run_cli(["--url", "not-a-url"])
        assert exc_info.value.code == 1

    def test_appends_to_existing_file(self, tmp_path, run_cli):
        toml = tmp_path / "content" / "data" / "human.toml"
        toml.write_text('["Existing"]\nurl="https://existing.com"\ndate="2026-01-01"\n')

        content = run_cli(["--url", "https://new.com", "--name", "New"])
        assert '["Existing"]' in content
        assert '["New"]' in content
        assert 'url="https://new.com"' in content
        data = tomllib.loads(content)
        assert "Existing" in data
        assert "New" in data

    def test_creates_directory_when_confirmed(self, tmp_path):
        # content/data/ intentionally not created
        base_path = tmp_path / "content"

        vouchfor_cli(
            argv=["--url", "https://example.com", "--name", "Test"],
            input_fn=lambda prompt: "Y",
            base_path=base_path,
        )

        assert (base_path / "data").is_dir()
        content = (base_path / "data" / "human.toml").read_text()
        assert 'url="https://example.com"' in content

    def test_creates_directory_on_default_answer(self, tmp_path):
        base_path = tmp_path / "content"

        vouchfor_cli(
            argv=["--url", "https://example.com", "--name", "Test"],
            input_fn=lambda prompt: "",
            base_path=base_path,
        )

        assert (base_path / "data" / "human.toml").exists()

    def test_declines_directory_creation(self, tmp_path, capsys):
        base_path = tmp_path / "content"

        with pytest.raises(SystemExit) as exc_info:
            vouchfor_cli(
                argv=["--url", "https://example.com", "--name", "Test"],
                input_fn=lambda prompt: "n",
                base_path=base_path,
            )
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "Not creating content/data/ -- exiting." in captured.out
        assert not (base_path / "data").exists()

    def test_positional_url(self, run_cli):
        content = run_cli(["https://example.com"])
        assert '[""]' in content
        assert 'url="https://example.com"' in content

    def test_positional_url_with_name_flag(self, run_cli):
        content = run_cli(["https://example.com", "--name", "Ex"])
        assert '["Ex"]' in content
        assert 'url="https://example.com"' in content

    def test_positional_url_invalid_exits(self, run_cli):
        with pytest.raises(SystemExit) as exc_info:
            run_cli(["not-a-url"])
        assert exc_info.value.code == 1

    def test_both_positional_and_flag_url_exits(self, run_cli):
        with pytest.raises(SystemExit) as exc_info:
            run_cli(["https://a.com", "--url", "https://b.com"])
        assert exc_info.value.code == 2


# === Functional tests: Compare Pelican-generated human.json to expected file ===


class TestFunctional:
    """Functional tests that run Pelican with the test site data."""

    def test_pelican_generates_human_json(self, tmp_path):
        # Load pelicanconf first so publishconf's `from pelicanconf import *` works
        read_settings(path=str(TEST_DATA_DIR / "pelicanconf.py"))
        settings = read_settings(
            path=str(TEST_DATA_DIR / "publishconf.py"),
            override={
                "OUTPUT_PATH": str(tmp_path),
                "PLUGINS": ["pelican.plugins.human"],
                "CACHE_CONTENT": False,
            },
        )
        pelican = Pelican(settings)
        pelican.run()

        output_file = tmp_path / "human.json"
        assert output_file.exists(), "human.json was not generated"

        result = json.loads(output_file.read_text())
        expected = json.loads(EXPECTED_OUTPUT.read_text())

        assert result == expected

    def test_pelican_with_empty_siteurl(self, tmp_path):
        settings = read_settings(
            path=str(TEST_DATA_DIR / "pelicanconf.py"),
            override={
                "OUTPUT_PATH": str(tmp_path),
                "PLUGINS": ["pelican.plugins.human"],
                "CACHE_CONTENT": False,
            },
        )
        pelican = Pelican(settings)
        pelican.run()

        assert not (tmp_path / "human.json").exists()
