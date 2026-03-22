"""Human: a Pelican plugin for the human.json protocol."""

import argparse
from datetime import date
import json
import logging
from pathlib import Path
import sys
import tomllib
from urllib.parse import urlparse

from rich import print as rprint

from pelican import signals

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "0.1.1"


def validate_url(url):
    """Validate that a URL has a proper scheme and network location."""
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def generate_human_json(pelican):
    """Generate human.json from human.toml after site generation."""
    content_path = Path(pelican.settings["PATH"])
    output_path = Path(pelican.settings["OUTPUT_PATH"])
    site_url = pelican.settings.get("SITEURL", "")

    toml_path = content_path / "data" / "human.toml"
    if not toml_path.exists():
        logger.info(
            "human.toml not found at %s; skipping human.json generation",
            toml_path,
        )
        return

    if not site_url or not validate_url(site_url):
        logger.info("SITEURL is missing or invalid; skipping human.json generation")
        return

    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    vouches = []
    errors = []
    for name, entry in data.items():
        missing = [k for k in ("url", "date") if k not in entry]
        if missing:
            errors.append((name, missing))
        else:
            vouches.append({"url": entry["url"], "vouched_at": entry["date"]})
    if errors:
        for name, missing in errors:
            logger.warning(
                "Vouch entry %r is missing required field(s): %s",
                name,
                ", ".join(missing),
            )
        logger.warning("Malformed human.toml; skipping human.json generation")
        return

    human_data = {
        "version": PROTOCOL_VERSION,
        "url": site_url,
        "vouches": vouches,
    }

    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / "human.json"
    with open(output_file, "w") as f:
        json.dump(human_data, f, indent=2)
        f.write("\n")

    logger.info("Generated human.json with %d vouches", len(vouches))


def register():
    """Register the plugin with Pelican."""
    signals.finalized.connect(generate_human_json)


# --- vouchfor CLI ---


def prompt_url(input_fn=input):
    """Interactively prompt for a URL, re-prompting on invalid input."""
    while True:
        try:
            url = input_fn("URL: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(1)
        if validate_url(url):
            return url
        rprint(
            "[red]Invalid URL. Please enter a valid URL with a scheme"
            " (e.g., https://example.com)[/red]"
        )


def prompt_name(input_fn=input):
    """Interactively prompt for an optional vouch entry name."""
    try:
        return input_fn("Name (optional): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def vouchfor_cli(argv=None, input_fn=input, base_path=None):
    """Add a vouch entry to human.toml."""
    parser = argparse.ArgumentParser(
        description=(
            "Vouch for a human website by adding an entry to human.toml."
            " A URL can be passed as a positional argument or with --url."
        ),
    )
    parser.add_argument(
        "url_positional",
        nargs="?",
        default=None,
        metavar="URL",
        help="URL to vouch for",
    )
    parser.add_argument("--url", help="URL to vouch for (alternative to positional)")
    parser.add_argument("--name", help="Name for the vouch entry")
    args = parser.parse_args(argv)

    if args.url is not None and args.url_positional is not None:
        parser.error("provide URL as a positional argument or with --url, not both")
    raw_url = args.url or args.url_positional

    if raw_url is not None:
        if not validate_url(raw_url):
            rprint(
                "[red]Invalid URL. Please enter a valid URL with a scheme"
                " (e.g., https://example.com)[/red]"
            )
            sys.exit(1)
        url = raw_url
    else:
        url = prompt_url(input_fn=input_fn)

    if args.name is not None:
        name = args.name
    elif raw_url is not None:
        name = ""
    else:
        name = prompt_name(input_fn=input_fn)

    try:
        write_vouch_entry(url, name, input_fn=input_fn, base_path=base_path)
    except MkdirDeclinedError:
        rprint("Not creating content/data/ -- exiting.")
        sys.exit(0)
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)
    rprint(f"[green]Vouched for {url}[/green]")


class MkdirDeclinedError(Exception):
    """Raised when the user declines to create the content/data/ directory."""


def write_vouch_entry(url, name, input_fn=input, base_path=None):
    """Write a vouch entry to the human.toml file.

    Raises:
        MkdirDeclinedError: If the user declines to create content/data/.
        EOFError: If input is closed while prompting for directory creation.
        KeyboardInterrupt: If the user interrupts the directory creation prompt.

    """
    today = date.today().isoformat()
    toml_path = (base_path or Path("content")) / "data" / "human.toml"
    if not toml_path.parent.exists():
        answer = input_fn("content/data/ does not exist. Create it? (Y/n) ").strip()
        if answer.lower() in ("", "y", "yes"):
            toml_path.parent.mkdir(parents=True)
        else:
            raise MkdirDeclinedError

    if toml_path.exists() and toml_path.stat().st_size > 0:
        existing = toml_path.read_text()
        separator = (
            ""
            if existing.endswith("\n\n")
            else "\n"
            if existing.endswith("\n")
            else "\n\n"
        )
    else:
        separator = ""

    entry = f'{separator}["{name}"]\nurl="{url}"\ndate="{today}"\n'

    with open(toml_path, "a") as f:
        f.write(entry)
