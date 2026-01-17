<!-- markdownlint-disable MD031 -->
# Contributing

Welcome to the contributor guide of Ultimate Notion.

This document focuses on getting any potential contributor familiarized with
the development processes, but [other kinds of contributions] are also appreciated.

If you are new to using [git] or have never collaborated on a project previously,
please have a look at [contribution-guide.org]. Other resources are also
listed in the excellent [guide created by FreeCodeCamp] [^contrib1].

Please notice that all users and contributors are expected to be **open,
considerate, reasonable, and respectful**. When in doubt,
[Python Software Foundation's Code of Conduct] is a good reference in terms of
behavior guidelines.

## Issue Reports

If you experience bugs or general issues with Ultimate Notion, please have a look
at the [issue tracker].
If you don't see anything useful there, please feel free to file an issue report.

!!! tip
    Please don't forget to include the closed issues in your search.
    Sometimes a solution was already reported, and the problem is considered
    **solved**.

New issue reports should include information about your programming environment
(e.g., operating system, Python version) and steps to reproduce the problem.
Please also try to simplify the reproduction steps to a very minimal example
that still illustrates the problem you are facing. By removing other factors,
you help us to identify the root cause of the issue.

## Documentation improvements

You can help improve the documentation of Ultimate Notion by making them more readable
and coherent, or by adding missing information and correcting mistakes.

This documentation uses [mkdocs] as its main documentation compiler.
This means that the docs are kept in the same repository as the project code, and
that any documentation update is done in the same way as a code contribution.

!!! tip
      Please notice that the [GitHub web interface] provides a quick way for
      proposing changes. While this mechanism can be tricky for normal code contributions,
      it works perfectly fine for contributing to the docs, and can be quite handy.
      If you are interested in trying this method out, please navigate to
      the `docs` folder in the source [repository], find which file you
      would like to propose changes to and click on the little pencil icon at the
      top, to open [GitHub's code editor]. Once you finish editing the file,
      please write a message in the form at the bottom of the page describing
      which changes you have made and what the motivations behind them are and
      submit your proposal.

When working on documentation changes in your local machine, you can
build and serve them using [hatch] with `hatch run docs:build` and
`hatch run docs:serve`, respectively.

## Code Contributions

### Submit an issue

Before you work on any non-trivial code contribution it's best to first create
a report in the [issue tracker] to start a discussion on the subject.
This often provides additional considerations and avoids unnecessary work.

### Clone the repository

1. Create a user account on GitHub if you do not already have one.

2. Fork the project [repository]: click on the *Fork* button near the top of the
   page. This creates a copy of the code under your account on GitHub.

3. Clone this copy to your local disk:
   ```console
   git clone git@github.com:YourLogin/ultimate-notion.git
   cd ultimate-notion
   ```

4. Make sure [hatch] and [pre-commit] are installed using [pipx]:
   ```console
   pipx install hatch
   pipx install pre-commit
   ```

5. Optionally run `hatch config set dirs.env.virtual .direnv` to let
   [VS Code] find your virtual environments. If you are using [VS Code],
   then it's quite convenient to add a file `.vscode/.env` in your checkout with:
   ```ini
   NOTION_TOKEN=TOKEN_TO_YOUR_TEST_NOTION_ACCOUNT
   ULTIMATE_NOTION_CONFIG=/path/to/repo/.ultimate-notion/config.toml
   ```
   These settings will also be respected by [pytest] using [pytest-dotenv].

### Setup the unit tests

Ultimate Notion has two ways to deal with unit tests. Most unit tests are recorded on cassettes
using [VCR.py], which allows to record unit tests that need internet connection and replay them
without the need of being online, also way faster. So to run existing unit tests, you can just
use `hatch run vcr-only` and everything should work. For new unit tests, you need to have
copy the *Ultimate Notion Tests* template into your workspace and set your unit tests up
so that they can access them.

1. Open the [Ultimate Notion Tests] website and click `Duplicate` on the upper left corner.
2. Login to Notion and select to which workspace you want to add the template.
3. In Notion, the `Ultimate Notion Tests` page should show up in your sidebar.
   Hover over it and click the menu <kbd>⋯</kbd>, then select `Copy link` to extract the
   *page id* for the step below.
4. Set up a Notion integration for testing with all permissions as described in the [Getting started] docs.
   Copy the *Internal integration secret* for the step below.
5. Create a file `.vscode/.env` within your cloned repository with the following content:
   ```cfg
   NOTION_TOKEN=YOUR_INTERNAL_INTEGRATION_SECRET
   ULTIMATE_NOTION_CONFIG=/PATH/TO/YOUR/CONFIG/.ultimate-notion/config.toml
   ROOT_PAGE_ID=PAGE_ID_AS_EXTRACTED_ABOVE.
   ```
   where you replace the values accordingly.

This should allow you to record new unit tests with `hatch run test -k NEW_TEST`.

### Implement your changes

1. Create a branch to hold your changes:
   ```console
   git switch -c my-feature
   ```
   and start making changes. Never work on the main branch!

2. Start your work on this branch. Don't forget to add [docstrings] in [Google style]
   to new functions, modules and classes, especially if they are part of public APIs.

3. Check that your changes don't break any unit tests with `hatch run vcr-only` for tests
   that do not generate calls to the Notion API or `hatch run test` for new tests generating API calls.

4. Run `hatch run lint:all` and `hatch run lint:fix` to check the code with [ruff] & [mypy]
   and automatically fix [ruff] issues if possible.

5. Add yourself to the list of contributors in `AUTHORS.md`.

6. When you’re done editing, do:
   ```console
   git add <MODIFIED FILES>
   git commit
   ```
   to record your changes in [git].\
   Please make sure you see the validation messages from [pre-commit] and fix any remaining issues.

!!! info
      Don't forget to add unit tests and documentation in case your
      contribution adds a feature and is not just a bugfix.

      Moreover, writing a [descriptive commit message] is highly recommended.
      In case of doubt, you can check the commit history with:
      ```
      git log --graph --decorate --pretty=oneline --abbrev-commit --all
      ```
      to look for recurring communication patterns.

### Submit your contribution

1. If everything works fine, push your local branch to the remote server with:

      ```console
      git push -u origin my-feature
      ```

2. Go to the GitHub page of your fork and click "Create pull request"
   to send your changes for review.

   Find more detailed information in [creating a PR]. You might also want to open
   the PR as a draft first and mark it as ready for review after the feedbacks
   from the continuous integration (CI) system or any required fixes.

[^contrib1]: Even though, these resources focus on open source projects and
    communities, the general ideas behind collaborating with other developers
    to collectively create software are general and can be applied to all sorts
    of environments, including private companies and proprietary code bases.

[contribution-guide.org]: http://www.contribution-guide.org/
[creating a PR]: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request
[docstrings]: https://peps.python.org/pep-0257/
[ruff]: https://docs.astral.sh/ruff/
[mypy]: https://mypy-lang.org/
[git]: https://git-scm.com
[github web interface]: https://docs.github.com/en/github/managing-files-in-a-repository/managing-files-on-github/editing-files-in-your-repository
[other kinds of contributions]: https://opensource.guide/how-to-contribute
[pre-commit]: https://pre-commit.com/
[pipx]: https://pypa.github.io/pipx/
[pytest]: https://docs.pytest.org/
[pytest-dotenv]: https://github.com/quiqua/pytest-dotenv
[python software foundation's code of conduct]: https://www.python.org/psf/conduct/
[Google style]: https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings
[guide created by FreeCodeCamp]: https://github.com/FreeCodeCamp/how-to-contribute-to-open-source
[VS Code]: https://code.visualstudio.com/
[GitHub's code editor]: https://docs.github.com/en/repositories/working-with-files/managing-files/editing-files
[mkdocs]: https://www.mkdocs.org/
[Ultimate Notion Tests]: https://north-tile-42e.notion.site/Ultimate-Notion-Tests-2d8289fbc2b58168bc9ac92273808b70
[VCR.py]: https://vcrpy.readthedocs.io/
[Getting started]: https://ultimate-notion.com/latest/usage/getting_started/#creating-an-integration
