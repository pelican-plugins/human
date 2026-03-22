Human: A Plugin for Pelican
===========================

[![Build Status](https://img.shields.io/github/actions/workflow/status/pelican-plugins/human/main.yml?branch=main)](https://github.com/pelican-plugins/human/actions)
[![PyPI Version](https://img.shields.io/pypi/v/pelican-human)](https://pypi.org/project/pelican-human/)
[![Downloads](https://img.shields.io/pypi/dm/pelican-human)](https://pypi.org/project/pelican-human/)
![License](https://img.shields.io/pypi/l/pelican-human?color=blue)

Human is a Pelican plugin that uses the [`human.json` protocol](https://codeberg.org/robida/human.json) to vouch for human web sites, creating a web of trust, as described on the project web site:

> `human.json` is a light-weight protocol for humans to assert authorship of their site content and vouch for the humanity of others. It uses URL ownership as identity, and trust propagates through a crawlable web of vouches between sites.

Installation
------------

This plugin can be installed via:

    python -m pip install pelican-human

As long as you have not explicitly added a `PLUGINS` setting to your Pelican settings file, then the newly-installed plugin should be automatically detected and enabled. Otherwise, you must add `human` to your existing `PLUGINS` list. For more information, please see the [How to Use Plugins](https://docs.getpelican.com/en/latest/plugins.html#how-to-use-plugins) documentation.

Usage
-----

First, inside your content folder, create a sub-folder called `data` and inside that folder create a `human.toml` file that should contain the humans for whom you want to vouch. For example, feel free to use the following sites to vouch for me, the very human author of this plugin: 😁

```toml
["Justin Mayer"]
url="https://justinmayer.com"
date="2026-03-22"

["Justin Mayer on the Fediverse"]
url="https://ramble.space/@justin"
date="2026-03-22"

["Justin Mayer on GitHub"]
url="https://github.com/justinmayer"
date="2026-03-22"

["Abstractions Podcast"]
url="https://shows.arrowloop.com/@abstractions"
date="2026-03-22"

["Hacker Codex"]
url="https://hackercodex.com"
date="2026-03-22"
```

When Pelican generates your web site, this plugin will extract the URL and date information from the aforementioned TOML file and save it in the `human.json` format in your output folder.

The second step is to add a link (relative or absolute) to that generated `human.json` file inside your Pelican theme’s base template:

```html
<link rel=human-json href=/human.json>
```

That’s it — just those two steps!

Vouch from the Command Line
---------------------------

This plugin includes a `vouchfor` command that makes it easy to add entries to your `human.toml` file without having to edit it by hand. Run it without arguments to be prompted for a URL and an optional name for the link.

You can pass a URL as a positional argument…

    vouchfor https://justinmayer.com

… or explicitly via the `--url` option flag:

    vouchfor --url https://justinmayer.com

You can also specify a name for the entry via `--name`:

    vouchfor https://justinmayer.com --name "Justin Mayer"

Run `vouchfor --help` for the full list of options. Happy vouching! 🌟

Troubleshooting
---------------

Add the `--verbose` option to your `pelican` invocation in order to see if there are any INFO-level messages related to this plugin.

Note that this plugin will use your `SITEURL` setting to determine the canonical URL of your site, which is a required field in `human.json`. In order to avoid generating an invalid `human.json` file, the plugin will not generate it if `SITEURL` is an empty string or does not contain a valid URL. So if you don’t see a `human.json` file after your site is generated, that may be because you need to explicitly specify the settings file that contains your production `SITEURL` (for example, via: `pelican --settings publishconf.py content`).

Contributing
------------

Contributions are welcome and much appreciated. Every little bit helps. You can contribute by improving the documentation, adding missing features, and fixing bugs. You can also help out by reviewing and commenting on [existing issues][].

To start contributing to this plugin, review the [Contributing to Pelican][] documentation, beginning with the **Contributing Code** section.

[existing issues]: https://github.com/pelican-plugins/human/issues
[Contributing to Pelican]: https://docs.getpelican.com/en/latest/contribute.html

License
-------

This project is licensed under the AGPL-3.0 license.
