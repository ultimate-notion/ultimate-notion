"""Create the API-creatable objects used by the live test suite.

The script is idempotent: objects that already exist are left unchanged.
Set NOTION_TOKEN and share the root page with the integration before running it.
"""

import argparse
import os
import time
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

import typer
from notion_client import Client
from notion_client.errors import HTTPResponseError

import ultimate_notion as uno
from ultimate_notion.rich_text import math as rt_math
from ultimate_notion.rich_text import mention as rt_mention
from ultimate_notion.rich_text import text as rt_text

DEFAULT_ROOT_TITLE = 'Tests'
MAX_REQUEST_ATTEMPTS = 5

# The exact set of objects the live test suite expects to find in the workspace.
# Keep these in sync with the title constants in `tests/conftest.py`. The audit step
# uses them to report anything else the integration can see (stray records) and to
# flag any expected object that is missing, so a search returns a known, stable set.
EXPECTED_PAGE_TITLES = frozenset(
    {
        DEFAULT_ROOT_TITLE,  # 'Tests' (or the value of UNO_TEST_ROOT_PAGE)
        'Getting Started',
        'Markdown Text Test',
        'Markdown Test',
        'Markdown SubPage Test',
        'Embed/Inline/Linked & Unfurl',
        'Comments',
        'Custom Emoji Page',
    }
)
EXPECTED_DATABASE_TITLES = frozenset(
    {
        'Contacts DB',
        'Task DB',
        'Formula DB',
        'All Properties DB',
        'Wiki DB',  # an ordinary page until it is manually turned into a wiki
    }
)

P = ParamSpec('P')
T = TypeVar('T')


def request_with_retry(call: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """Retry Notion rate-limit and overload responses as instructed by the API."""
    for attempt in range(MAX_REQUEST_ATTEMPTS):
        try:
            return call(*args, **kwargs)
        except HTTPResponseError as error:
            if error.status not in {429, 529} or attempt == MAX_REQUEST_ATTEMPTS - 1:
                raise
            retry_after = error.headers.get('Retry-After')
            delay = int(retry_after) if retry_after is not None else 2**attempt
            typer.echo(f'Notion asked us to retry in {delay}s.', err=True)
            time.sleep(delay)

    msg = 'Notion request retry loop exited unexpectedly.'
    raise RuntimeError(msg)


class RetryingClient(Client):
    """Synchronous Notion client that respects rate-limit retry responses."""

    def request(self, *args: Any, **kwargs: Any) -> Any:
        return request_with_retry(super().request, *args, **kwargs)


def json_object(value: Any) -> dict[str, Any]:
    """Validate a raw JSON object returned by notion-client."""
    if not isinstance(value, dict):
        msg = f'Expected a JSON object from Notion, got {type(value).__name__}.'
        raise TypeError(msg)
    return value


def rich_text(text: str) -> list[dict[str, Any]]:
    return [{'type': 'text', 'text': {'content': text}}]


# The 12 intricately-styled paragraphs that `tests/test_markdown.py::test_rich_text_md`
# expects on the `Markdown Text Test` page. Contrary to earlier belief, this rich text *is*
# reproducible through the API (nested bold/italic/strikethrough/underline, inline code and
# equations, a person and a self page-mention, mid-word links), so the bootstrap builds it
# rather than leaving it as a manual UI step. The target markdown is the `correct_mds` list
# in that test; `markdown_text_paragraphs` reproduces it segment by segment.
_G = 'https://google.de/'
_A = 'https://amazon.com/'

# The first paragraph rendered to markdown -- used to detect an already-built page so the
# bootstrap stays idempotent (a placeholder page renders to plain, unstyled text).
MARKDOWN_TEXT_FIRST_MD = 'here is something **very** *simpel* and <u>underlined</u> as well as `code`'


def markdown_text_paragraphs(notion: uno.Session, page: uno.Page) -> list[uno.Paragraph]:
    """Return the 12 styled paragraphs for the `Markdown Text Test` page.

    `page` is the page itself, needed for the self page-mention in paragraph 7; a workspace
    member is used for that paragraph's person mention (the test neutralises the name).
    """
    t, m = rt_text, rt_math
    users = notion.all_users()
    person = next((u for u in users if getattr(u, 'is_person', False)), users[0])
    parts = [
        t('here is something ')
        + t('very', bold=True)
        + t(' ')
        + t('simpel', italic=True)
        + t(' and ')
        + t('underlined', underline=True)
        + t(' as well as ')
        + t('code', code=True),
        t('here is a sentence that was bolded ', bold=True)
        + t('then', bold=True, italic=True)
        + t(' typed.', bold=True),
        t('here is a test sentence with ')
        + t('many ', strikethrough=True)
        + t('different ', strikethrough=True, bold=True)
        + t('styles', strikethrough=True, bold=True, italic=True)
        + t('.', strikethrough=True, bold=True),
        t('here is another test with ')
        + t('many ', strikethrough=True)
        + t('different ', strikethrough=True, italic=True)
        + t('styles', strikethrough=True, italic=True, bold=True)
        + t('.', strikethrough=True, italic=True),
        t('here is one more with a ')
        + t('strange ', italic=True)
        + t('style', italic=True, bold=True)
        + t(' ')
        + t('combination', bold=True),
        t('here is one with an inline ')
        + t('equa-', bold=True, strikethrough=True)
        + t('tion', bold=True, strikethrough=True, italic=True)
        + t(' ', bold=True)
        + m('E=mc^2', bold=True, italic=True)
        + t(' and', bold=True, italic=True)
        + t(' no block equation'),
        t('and here is one with ')
        + t('person', bold=True, italic=True, strikethrough=True)
        + t(' mention ', italic=True, strikethrough=True)
        + rt_mention(person, italic=True, strikethrough=True)
        + t(' and ')
        + t('page mention ', bold=True)
        + rt_mention(page, bold=True)
        + t(' '),
        t('here is one ')
        + t('stretching over ', bold=True)
        + t('many\n', bold=True, italic=True)
        + t('many', bold=True, italic=True, strikethrough=True)
        + t('\n', bold=True)
        + t('lines', bold=True, strikethrough=True),
        t('This is code, e.g. ')
        + t('python', bold=True, code=True)
        + t(' code\nnow stretching ', bold=True)
        + t('over\nmany lines', bold=True, code=True),
        t('This is a ')
        + t('li', href=_G)
        + t('n', bold=True, href=_G)
        + t('k', href=_G)
        + t(' and a ')
        + t('first', strikethrough=True)
        + t(' an')
        + t('d ', strikethrough=True)
        + t('second', strikethrough=True, underline=True)
        + t(' stroke', strikethrough=True)
        + t(' through')
        + t(' word.', underline=True),
        t('Half a ') + t('lin', href=_G) + t('k', href=_A) + t(' for two destinations'),
        t('✨Magic ✨'),
    ]
    return [uno.Paragraph(part) for part in parts]


class ContactRole(uno.OptionNS):
    project_manager = uno.Option('Project Manager', color=uno.Color.GREEN)
    software_engineer = uno.Option('Software Engineer', color=uno.Color.GRAY)
    ux_designer = uno.Option('UX Designer', color=uno.Color.RED)
    marketing_manager = uno.Option('Marketing Manager', color=uno.Color.ORANGE)
    data_analyst = uno.Option('Data Analyst', color=uno.Color.BLUE)
    qa_engineer = uno.Option('QA Engineer')
    technical_writer = uno.Option('Technical Writer', color=uno.Color.PINK)
    business_analyst = uno.Option('Business Analyst', color=uno.Color.PURPLE)
    it_support_specialist = uno.Option('IT Support Specialist', color=uno.Color.YELLOW)


class Contacts(uno.Schema, db_title='Contacts DB'):
    """Database of all my contacts!"""

    name = uno.PropType.Title('Name')
    title = uno.PropType.Text('Title', description='Title within the company')
    role = uno.PropType.Select('Role', options=ContactRole)
    email = uno.PropType.Email('Email')
    phone = uno.PropType.Phone('Phone')
    url = uno.PropType.URL('URL')
    team_member = uno.PropType.Checkbox('Team Member')
    sync_date = uno.PropType.Date('Sync Date')


class FormulaTag(uno.OptionNS):
    in_progress = uno.Option('In Progress', color=uno.Color.PINK)
    done = uno.Option('Done', color=uno.Color.GRAY)


class Formulas(uno.Schema, db_title='Formula DB'):
    name = uno.PropType.Title('Name')
    tags = uno.PropType.MultiSelect('Tags', options=FormulaTag)
    date_source = uno.PropType.Date('Date Source')
    string = uno.PropType.Formula('String', formula='format(prop("Name"))')
    number = uno.PropType.Formula('Number', formula='prop("Tags").length()')
    checkbox = uno.PropType.Formula('Checkbox', formula='prop("Tags").includes("Done")')
    date = uno.PropType.Formula('Date', formula='prop("Date Source")')


class Bootstrap:
    def __init__(self, notion: uno.Session, root_title: str, *, prune: bool = False) -> None:
        self.notion = notion
        self.client = notion.client
        self.root_title = root_title
        self.prune = prune
        root = self.find_page(root_title)
        if root is None:
            msg = f'Root page {root_title!r} was not found. Share it with the integration first.'
            raise RuntimeError(msg)
        self.root = root

    @staticmethod
    def one_match(matches: list[T], title: str, kind: str) -> T | None:
        if len(matches) > 1:
            msg = f'Found multiple {kind}s titled {title!r}; remove duplicates before bootstrapping.'
            raise RuntimeError(msg)
        return matches[0] if matches else None

    def find_page(self, title: str) -> uno.Page | None:
        return self.one_match(list(self.notion.search_page(title)), title, 'page')

    def find_database(self, title: str) -> uno.Database | None:
        return self.one_match(list(self.notion.search_db(title)), title, 'database')

    def create_page(
        self,
        title: str,
        *,
        parent: uno.Page | None = None,
        blocks: list[uno.Block] | None = None,
    ) -> uno.Page:
        page = self.find_page(title)
        if page is not None:
            typer.echo(f'page exists: {title}')
            return page
        page = self.notion.create_page(parent=self.root if parent is None else parent, title=title, blocks=blocks)
        typer.echo(f'created page: {title}')
        return page

    def get_or_create_database(self, title: str, schema: type[uno.Schema]) -> tuple[uno.Database, bool]:
        database = self.find_database(title)
        if database is not None:
            database.schema = schema
            typer.echo(f'database exists: {title}')
            return database, False
        database = self.notion.create_db(parent=self.root, schema=schema)
        typer.echo(f'created database: {title}')
        return database, True

    def ensure_wiki_shell(self) -> None:
        if self.find_database('Wiki DB') is not None:
            typer.echo('wiki exists: Wiki DB')
            return
        self.create_page('Wiki DB')
        typer.echo('manual step: open the Wiki DB page and select ... -> Turn into wiki')

    def ensure_contacts_db(self) -> None:
        database, created = self.get_or_create_database('Contacts DB', Contacts)
        if created:
            # Database icons currently have no high-level setter.
            self.client.databases.update(database_id=str(database.id), icon={'type': 'emoji', 'emoji': '🤝'})
        if not database.is_empty:
            typer.echo('Contacts DB already has rows')
            return
        roles = [
            ContactRole.project_manager,
            ContactRole.software_engineer,
            ContactRole.ux_designer,
            ContactRole.marketing_manager,
            ContactRole.data_analyst,
            ContactRole.qa_engineer,
            ContactRole.technical_writer,
            ContactRole.business_analyst,
            ContactRole.it_support_specialist,
            ContactRole.software_engineer,
        ]
        for idx, role in enumerate(roles, 1):
            database.create_page(
                name=f'Contact {idx}',
                title=f'Title {idx}',
                role=role,
                email=f'contact{idx}@example.com',
                team_member=idx % 2 == 0,
            )
        typer.echo('seeded Contacts DB: 10 rows')

    def ensure_task_db(self) -> None:
        database = self.find_database('Task DB')
        if database is None:
            # Status properties cannot be created through Ultimate Notion's Schema API.
            response = json_object(
                self.client.databases.create(
                    parent={'page_id': str(self.root.id)},
                    title=rich_text('Task DB'),
                    description=rich_text('My personal task list of all the important stuff I have to do'),
                    properties={
                        'Task': {'title': {}},
                        'Status': {
                            'status': {
                                'options': [
                                    {'name': 'Backlog', 'color': 'gray'},
                                    {'name': 'Blocked', 'color': 'red'},
                                    {'name': 'In Progress', 'color': 'blue'},
                                    {'name': 'Done', 'color': 'green'},
                                ]
                            }
                        },
                        'Due Date': {'date': {}},
                        'Priority': {
                            'select': {
                                'options': [
                                    {'name': '✹ High', 'color': 'red'},
                                    {'name': '✷ Medium', 'color': 'yellow'},
                                    {'name': '✶ Low', 'color': 'gray'},
                                ]
                            }
                        },
                        'Urgency': {
                            'formula': {
                                'expression': (
                                    'if(prop("Status") == "Done", "✅", if(empty(prop("Due Date")), "", "🕘"))'
                                )
                            }
                        },
                    },
                )
            )
            database = self.notion.get_db(response['id'])
            typer.echo('created database: Task DB')
        else:
            typer.echo('database exists: Task DB')
        if not database.is_empty:
            typer.echo('Task DB already has rows')
            return
        rows = [
            ('Run first Marathon', 'In Progress', '✹ High', '2026-07-01T12:00:00.000+00:00'),
            ('Buy milk', 'Backlog', '✶ Low', '2026-07-02T12:00:00.000+00:00'),
            ('Ship release', 'Done', '✷ Medium', '2026-06-18T12:00:00.000+00:00'),
        ]
        for name, status, priority, due_date in rows:
            database.create_page(
                task=name,
                status=status,
                priority=priority,
                due_date=due_date,
            )
        typer.echo('seeded Task DB: 3 rows')

    def ensure_formula_db(self) -> None:
        database, _ = self.get_or_create_database('Formula DB', Formulas)
        if database.is_empty:
            for title, tags in (
                ('Item 1', [FormulaTag.done, FormulaTag.in_progress]),
                ('Item 2', [FormulaTag.in_progress]),
            ):
                database.create_page(
                    name=title,
                    tags=tags,
                    date_source='2024-11-25T14:08:00.000+00:00',
                )
            typer.echo('seeded Formula DB: 2 rows')
        else:
            typer.echo('Formula DB already has rows')
        self.check_formula_filterable(database)

    def ensure_all_props_db_rows(self) -> None:
        """Seed rows into the manually-created `All Properties DB`.

        The database itself cannot be created through the API (it has AI Autofill and
        Button properties, see `tests/TEST_WORKSPACE.md`) so it must be built by hand,
        but its *rows* can be created through the API. `test_retrieve_property` reads the
        first row, so the database must be non-empty for a live re-record (see issue #371).
        Only writable properties are set; read-only ones (formula, rollup, AI, button,
        timestamps, ...) are populated by Notion.
        """
        database = self.find_database('All Properties DB')
        if database is None:
            typer.echo('All Properties DB: not found; build it by hand first (see tests/TEST_WORKSPACE.md)')
            return
        if not database.is_empty:
            typer.echo('All Properties DB already has rows')
            return
        for idx in (1, 2):
            database.create_page(
                title=f'Item {idx}',
                text=f'Text {idx}',
                number=idx,
                checkbox=idx % 2 == 0,
            )
        typer.echo('seeded All Properties DB: 2 rows')

    @staticmethod
    def check_formula_filterable(database: uno.Database) -> None:
        """Report whether the Formula DB's formulas can be filtered on.

        Notion rejects query filters on formula properties created via the public API
        ("Unable to filter based on a formula of unknown type", see issue #297), so the
        formula columns must be (re)created in the Notion UI before `test_query_formula`
        can record. This probe surfaces that as a manual step instead of a cryptic 400
        during cassette recording.
        """
        try:
            database.query.filter(uno.prop('String').is_not_empty()).execute()
        except HTTPResponseError as exc:
            typer.echo(
                f'Formula DB: manual setup required - formula filters fail ({exc}). '
                'Recreate the formula columns in the Notion UI so Notion assigns them a '
                'filterable result type (see issue #297), then re-run.'
            )
        else:
            typer.echo('Formula DB: formula filters OK')

    def ensure_static_pages(self) -> None:
        self.create_page(
            'Getting Started',
            blocks=[
                uno.Heading1('Getting Started'),
                uno.Paragraph('Welcome to the Ultimate Notion test workspace.'),
            ],
        )
        self.ensure_markdown_text_page()
        markdown_page = self.create_page(
            'Markdown Test',
            blocks=[uno.Heading1('Headline 1')],
        )
        self.create_page(
            'Markdown SubPage Test',
            parent=markdown_page,
            blocks=[uno.Paragraph('This is the original Paragraph on SubPage')],
        )
        self.create_page(
            'Embed/Inline/Linked & Unfurl',
            blocks=[
                uno.Embed('https://ultimate-notion.com/'),
                uno.Bookmark('https://ultimate-notion.com/'),
                uno.Paragraph('Inline link: https://ultimate-notion.com/'),
                uno.Paragraph('Linked database placeholder'),
            ],
        )
        self.create_page(
            'Comments',
            blocks=[uno.Heading1('Comments')],
        )

    def ensure_markdown_text_page(self) -> None:
        """Create the `Markdown Text Test` page and build its 12 styled rich-text paragraphs.

        Idempotent: if the page already renders the expected first paragraph it is left
        unchanged; otherwise its body is rebuilt (a freshly-created or placeholder page).
        """
        page = self.create_page('Markdown Text Test')
        children = list(page.children)
        if children and children[0].to_markdown() == MARKDOWN_TEXT_FIRST_MD:
            typer.echo('Markdown Text Test: rich text already built')
            return
        for child in children:
            child.delete()
        page.append(markdown_text_paragraphs(self.notion, page))
        typer.echo('Markdown Text Test: built 12 rich-text paragraphs')

    def audit_manual_objects(self) -> None:
        for title, kind in (
            ('All Properties DB', 'database'),
            ('Wiki DB', 'database'),
            ('Custom Emoji Page', 'page'),
        ):
            obj = self.find_database(title) if kind == 'database' else self.find_page(title)
            status = 'ready' if obj is not None else 'manual setup required'
            typer.echo(f'{title}: {status}')

    @classmethod
    def for_audit(cls, notion: uno.Session, *, prune: bool = False) -> 'Bootstrap':
        """Construct an instance for the read-only audit, skipping the root-page lookup.

        The audit only uses the raw Notion client, so it works even against a released
        package version that still has the issue #273 validation bug, and against a
        workspace whose root page has not been shared yet.
        """
        self = cls.__new__(cls)
        self.notion = notion
        self.client = notion.client
        self.prune = prune
        return self

    def iter_visible(self, object_type: str) -> 'list[dict[str, Any]]':
        """Return every object of `object_type` ('page'/'database') the integration can see."""
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                'filter': {'property': 'object', 'value': object_type},
                'page_size': 100,
            }
            if cursor is not None:
                kwargs['start_cursor'] = cursor
            response = json_object(self.client.search(**kwargs))
            results.extend(json_object(item) for item in response.get('results', []))
            if not response.get('has_more'):
                return results
            cursor = response.get('next_cursor')

    @staticmethod
    def raw_title(obj: dict[str, Any]) -> str | None:
        """Best-effort plain-text title from a raw page/database object, or None if untitled.

        Returns None for the stripped-down, property-less objects Notion returns for
        trashed / limited-access records (see issue #273).
        """
        if obj.get('object') == 'database':
            parts = obj.get('title') or []
        else:
            parts = []
            for prop in (obj.get('properties') or {}).values():
                if isinstance(prop, dict) and prop.get('type') == 'title':
                    parts = prop.get('title') or []
                    break
        text = ''.join(part.get('plain_text', '') for part in parts if isinstance(part, dict))
        return text or None

    def audit_workspace_objects(self) -> None:
        """Report everything the integration can see and flag drift from the expected set.

        A perpetually-red weekly live job is invisible, and stray records (trashed,
        orphaned or limited-access leftovers) silently break searches (issue #273). This
        reports stray and missing objects so a fresh or polluted workspace is obvious, and
        optionally prunes accessible stray pages when run with `--prune`.
        """
        expected_titles = EXPECTED_PAGE_TITLES | EXPECTED_DATABASE_TITLES
        pages = self.iter_visible('page')
        databases = self.iter_visible('database')

        visible_titles: set[str] = set()
        property_less = 0
        stray: list[dict[str, Any]] = []
        for obj in (*pages, *databases):
            title = self.raw_title(obj)
            if title is None:
                property_less += 1
            else:
                visible_titles.add(title)
            if title not in expected_titles:  # None (property-less) is never expected
                stray.append(obj)

        typer.echo('')
        typer.echo(f'audit: {len(pages)} page(s), {len(databases)} database(s) visible to the integration')
        typer.echo(f'audit: {property_less} object(s) with no resolvable title (property-less or untitled)')

        missing = sorted(expected_titles - visible_titles)
        if missing:
            typer.echo(f'audit: MISSING expected object(s): {", ".join(missing)}', err=True)
        else:
            typer.echo('audit: all expected objects are present')

        if not stray:
            typer.echo('audit: no stray objects; the workspace matches the expected set')
            return

        typer.echo(f'audit: {len(stray)} stray object(s) not in the expected set:', err=True)
        for obj in stray:
            title = self.raw_title(obj)
            label = repr(title) if title is not None else '<untitled/property-less>'
            in_trash = obj.get('in_trash', obj.get('archived', False))
            typer.echo(f'  - {obj.get("object")} {obj.get("id")} {label}{" [in trash]" if in_trash else ""}', err=True)

        if self.prune:
            self.prune_stray(stray)
        else:
            typer.echo('audit: re-run with --prune to move accessible stray pages to trash', err=True)

    def prune_stray(self, stray: list[dict[str, Any]]) -> None:
        """Best-effort move stray pages to trash. Skips databases and inaccessible objects."""
        pruned = 0
        for obj in stray:
            if obj.get('object') != 'page' or obj.get('in_trash') or obj.get('archived'):
                continue
            try:
                request_with_retry(self.client.pages.update, page_id=str(obj['id']), in_trash=True)
            except HTTPResponseError as error:
                typer.echo(f'  could not prune {obj.get("id")}: {error}', err=True)
                continue
            pruned += 1
        typer.echo(f'audit: pruned {pruned} stray page(s) to trash')

    def run(self) -> None:
        self.ensure_wiki_shell()
        self.ensure_contacts_db()
        self.ensure_task_db()
        self.ensure_formula_db()
        self.ensure_all_props_db_rows()
        self.ensure_static_pages()
        self.audit_manual_objects()
        self.audit_workspace_objects()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--root-title',
        default=os.environ.get('UNO_TEST_ROOT_PAGE', DEFAULT_ROOT_TITLE),
        help='Title of the root page shared with the integration.',
    )
    parser.add_argument(
        '--prune',
        action='store_true',
        help='Move accessible stray pages (not in the expected set) to trash. Off by default.',
    )
    parser.add_argument(
        '--audit-only',
        action='store_true',
        help='Skip object creation; only audit what the integration can see (read-only by default).',
    )
    args = parser.parse_args()
    token = os.environ.get('NOTION_TOKEN')
    if not token:
        parser.error('NOTION_TOKEN must be set')
    with uno.Session(client=RetryingClient(auth=token)) as notion:
        if args.audit_only:
            Bootstrap.for_audit(notion, prune=args.prune).audit_workspace_objects()
        else:
            Bootstrap(notion, args.root_title, prune=args.prune).run()


if __name__ == '__main__':
    main()
