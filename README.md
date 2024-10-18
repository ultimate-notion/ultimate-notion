<div align="center">
<img
src="https://raw.githubusercontent.com/ultimate-notion/ultimate-notion/master/docs/assets/images/logo_with_text.svg"
alt="Ultimate-Notion logo" width="500" role="img">
</div>
<br/>

Ultimate Notion is the ultimate Python client for [Notion]! It allows you to access, create and change your
Notion databases and pages in the most convenient and pythonic way.

|         |                                    |
|---------|------------------------------------|
| CI/CD   | [![Tests][Tests-image]][Tests-link] [![Coverage][Coverage-image]][Coverage-link] [![Publish Package][Publish-image]][Publish-link] [![Build Docs][Docs-image]][Docs-link] |
| Package | [![PyPI - Version][PyPI_ver-image]][PyPI_ver-link] [![PyPI - Downloads][PyPI_down-image]][PyPI_down-link] [![PyPI - Python Version][PyPI_py-image]][PyPI_py-link] [![GitHub Sponsors][sponsor-image]][sponsor-link] |
| Details | [![Hatch project][hatch-image]][hatch-link] [![Linting - Ruff][ruff-image]][ruff-link] [![Pre-Commit][precommit-image]][precommit-link] [![test - pytest][pytest-image]][pytest-link] [![Types - Mypy][mypy-image]][mypy-link] [![License - MIT][MIT-image]][MIT-link] [![Docs - mkdocs][mkdocs-image]][mkdocs-link] |

## Installation

Install the most recent release using [PyPI] with:

```console
pip install ultimate-notion
```

or to install all additional dependencies, use:

```console
pip install 'ultimate-notion[all]'
```

## Usage

Make sure you have set the environment variable `NOTION_TOKEN` to your Notion
integration token. Then it's as simple as:

```python
import ultimate_notion as uno

PAGE_TITLE = 'Getting Started'

with uno.Session() as notion:
    page = notion.search_page(PAGE_TITLE).item()
    page.show()

# Alternatively, without a context manager:
notion = uno.Session()
page = notion.search_page(PAGE_TITLE).item()
page.show()
notion.close()
```

Check out the official [Ultimate Notion documentation] for more details.
Especially the page about [creating a Notion integration] to get the token.
The documentation is made with [Material for MkDocs] and is hosted on [GitHub Pages].

## Getting help

If you are stuck with a problem and need help or just want to brag about what you did,
the [Discussion] area is the right place for you. Here, you can ask questions, provide
suggesions and discuss with other users.

## Contributing

After having cloned this repository:

1. make sure [hatch] is installed globally, e.g. `pipx install hatch`,
2. make sure [pre-commit] is installed globally, e.g. with `pipx install pre-commit`,

and then you are already set up to start hacking. Use `hatch run test` to run the unit tests or `hatch run vcr-only`
to run the offline unit tests using [VCR.py]. Regenerate the cassettes with `hatch run vcr-rewrite`.
Check out the environment setup of hatch in [pyproject.toml](pyproject.toml) for many more commands.

If you are using [VS Code], it's quite convenient to create a file  `.vscode/.env` with

```ini
NOTION_TOKEN=TOKEN_TO_YOUR_TEST_NOTION_ACCOUNT
ULTIMATE_NOTION_CONFIG=/path/to/repo/.ultimate-notion/config.toml
```

Check out this [page about contributing] for more details.

## License & Credits

Ultimate Notion is distributed under the terms of the [MIT license](LICENSE.txt).
To start this project off a lot of inspiration and code was taken from [hatch] and [notional].
Ultimate Notion highly depends on [notion-sdk-py].

[Notion]: https://www.notion.so/
[hatch]: https://hatch.pypa.io/
[pre-commit]: https://pre-commit.com/
[notional]: https://github.com/jheddings/notional/
[notion-sdk-py]: https://github.com/ramnes/notion-sdk-py/
[Material for MkDocs]: https://github.com/squidfunk/mkdocs-material
[GitHub Pages]: https://docs.github.com/en/pages
[Ultimate Notion documentation]: https://ultimate-notion.com/
[creating a Notion integration]: https://ultimate-notion.com/latest/usage/getting_started/
[page about contributing]: https://ultimate-notion.com/latest/contributing/
[VS Code]: https://code.visualstudio.com/
[PyPI]: https://pypi.org/
[VCR.py]: https://vcrpy.readthedocs.io/
[Discussion]: https://github.com/ultimate-notion/ultimate-notion/discussions

[Tests-image]: https://github.com/ultimate-notion/ultimate-notion/actions/workflows/run-tests.yml/badge.svg
[Tests-link]: https://github.com/ultimate-notion/ultimate-notion/actions/workflows/run-tests.yml
[Coverage-image]: https://img.shields.io/coveralls/github/ultimate-notion/ultimate-notion/master.svg?logo=coveralls&label=Coverage
[Coverage-link]: https://coveralls.io/r/ultimate-notion/ultimate-notion
[Publish-image]: https://github.com/ultimate-notion/ultimate-notion/actions/workflows/publish-pkg.yml/badge.svg
[Publish-link]: https://github.com/ultimate-notion/ultimate-notion/actions/workflows/publish-pkg.yml
[Docs-image]: https://github.com/ultimate-notion/ultimate-notion/actions/workflows/build-dev-docs.yml/badge.svg
[Docs-link]: https://github.com/ultimate-notion/ultimate-notion/actions/workflows/build-dev-docs.yml
[PyPI_ver-image]: https://img.shields.io/pypi/v/ultimate-notion.svg?logo=pypi&label=PyPI&logoColor=gold
[PyPI_ver-link]: https://pypi.org/project/ultimate-notion/
[PyPI_down-image]: https://img.shields.io/pypi/dm/ultimate-notion.svg?color=blue&label=Downloads&logo=pypi&logoColor=gold
[PyPI_down-link]: https://pypistats.org/packages/ultimate-notion
[PyPI_py-image]: https://img.shields.io/pypi/pyversions/ultimate-notion.svg?logo=python&label=Python&logoColor=gold
[PyPI_py-link]: https://pypi.org/project/ultimate-notion/
[hatch-image]: https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg
[hatch-link]: https://github.com/pypa/hatch
[ruff-image]: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
[ruff-link]: https://github.com/charliermarsh/ruff
[mypy-image]: https://img.shields.io/badge/Types-mypy-blue.svg
[mypy-link]: https://mypy-lang.org/
[MIT-image]: https://img.shields.io/badge/License-MIT-9400d3.svg
[MIT-link]: LICENSE.txt
[sponsor-image]: https://img.shields.io/static/v1?label=Sponsor&message=%E2%9D%A4&logo=GitHub&color=ff69b4
[sponsor-link]: https://github.com/sponsors/FlorianWilhelm
[mkdocs-image]: https://img.shields.io/static/v1?label=‎&message=mkdocs&logo=Material+for+MkDocs&color=526CFE&logoColor=white
[mkdocs-link]: https://ultimate-notion.com/
[precommit-image]: https://img.shields.io/static/v1?label=‎&message=pre-commit&logo=pre-commit&color=76877c
[precommit-link]: https://pre-commit.com/
[pytest-image]: https://img.shields.io/static/v1?label=‎&message=Pytest&logo=Pytest&color=0A9EDC&logoColor=white
[pytest-link]:  https://docs.pytest.org/
