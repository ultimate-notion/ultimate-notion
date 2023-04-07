<div align="center">

<img src="https://raw.githubusercontent.com/ultimate-notion/ultimate-notion/master/docs/assets/images/logo_with_text.svg" alt="Ultimate-Notion logo" width="500" role="img">
</div>
<br/>

Ultimate Notion is the ultimate Python library for [Notion]! It allows you to access and modify your Notion databases and
pages in the most convenient and pythonic way.

|         |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
|---------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| CI/CD   | [![Tests](https://github.com/ultimate-notion/ultimate-notion/actions/workflows/run-tests.yml/badge.svg)](https://github.com/ultimate-notion/ultimate-notion/actions/workflows/run-tests.yml) [![Coverage](https://img.shields.io/coveralls/github/ultimate-notion/ultimate-notion/master.svg?logo=coveralls&label=Coverage)](https://coveralls.io/r/ultimate-notion/ultimate-notion) [![Publish Package](https://github.com/ultimate-notion/ultimate-notion/actions/workflows/publish-pkg.yml/badge.svg)](https://github.com/ultimate-notion/ultimate-notion/actions/workflows/publish-pkg.yml) [![Build Docs](https://github.com/ultimate-notion/ultimate-notion/actions/workflows/build-dev-docs.yml/badge.svg)](https://github.com/ultimate-notion/ultimate-notion/actions/workflows/build-dev-docs.yml)                                                                                                        |
| Package | [![PyPI - Version](https://img.shields.io/pypi/v/ultimate-notion.svg?logo=pypi&label=PyPI&logoColor=gold)](https://pypi.org/project/ultimate-notion/) [![PyPI - Downloads](https://img.shields.io/pypi/dm/ultimate-notion.svg?color=blue&label=Downloads&logo=pypi&logoColor=gold)](https://pepy.tech/project/ultimate-notion) [![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ultimate-notion.svg?logo=python&label=Python&logoColor=gold)](https://pypi.org/project/ultimate-notion/)                                                                                                                                                                                                                                                                                                                                                                                                           |
| Details | [![Project generated with PyScaffold](https://img.shields.io/badge/-PyScaffold-005CA0?logo=pyscaffold)](https://pyscaffold.org/) [![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch) [![linting - Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v0.json)](https://github.com/charliermarsh/ruff) [![code style - black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![types - Mypy](https://img.shields.io/badge/types-Mypy-blue.svg)](https://github.com/ambv/black) [![License - MIT](https://img.shields.io/badge/license-MIT-9400d3.svg)](https://spdx.org/licenses/) [![GitHub Sponsors](https://img.shields.io/static/v1?label=Sponsor&message=%E2%9D%A4&logo=GitHub&color=ff69b4)](https://github.com/sponsors/FlorianWilhelm) |



**This is a pre-alpha version! Don't use it!**

## Features

- in development

## Development

After having cloned this repository:

1. install [hatch] globally, e.g. `pipx install hatch`,
2. create the default environment with `hatch env create`,
3. activate the default environment with `hatch shell`,
4. \[only once\] run `pre-commit install` to install [pre-commit],

and then you are already set up to start hacking. Use `hatch run test:cov` or `hatch run test:no-cov` to run
the unitest with or without coverage reports, respectively.

## Documentation

The [documentation](https://ultimate-notion.com/) is made with [Material for MkDocs](https://github.com/squidfunk/mkdocs-material) and is hosted by [GitHub Pages](https://docs.github.com/en/pages).

## License

Ultimate-Notion is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Credits

To start this project off a lot of inspiration and code was taken from [hatch] and [notional]. Ultimate Notion makes
heavy use of [notional] and is a more user-friendly layer on top of it, just the same way that [notional] is a layer
on top of the excellent [notion-sdk-py].

## ToDos:

* Implement the capability to get the url from any reference
* Implement the creation and filling of a database to make writing unit tests easier
* Implement setting attributes

[Notion]: https://www.notion.so/
[hatch]: https://hatch.pypa.io/
[pre-commit]: https://pre-commit.com/
[notional]: https://github.com/jheddings/notional/
[notion-sdk-py]: https://github.com/ramnes/notion-sdk-py/
