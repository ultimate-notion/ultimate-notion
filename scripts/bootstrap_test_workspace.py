"""Create the API-creatable objects used by the live test suite.

The script is idempotent: objects that already exist are left unchanged.
Set NOTION_TOKEN and share the root page with the integration before running it.
"""

import argparse
import base64
import io
import os
import time
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

import typer
from notion_client import Client
from notion_client.errors import HTTPResponseError

import ultimate_notion as uno
from ultimate_notion.errors import SchemaError
from ultimate_notion.rich_text import math as rt_math
from ultimate_notion.rich_text import mention as rt_mention
from ultimate_notion.rich_text import text as rt_text

DEFAULT_ROOT_TITLE = 'Tests'
MAX_REQUEST_ATTEMPTS = 5

# A minimal valid 1x1 JPEG. The `test_page_to_markdown` fixture renders its second image as
# `![1004-300x300.jpg](https://...)`, where the alt text is the *uploaded* file name and the URL is a
# Notion-hosted (`prod-files-secure`) link -- an external URL cannot reproduce it. So we upload a file
# named `1004-300x300.jpg`; the pixels are irrelevant, only the name and that it is Notion-hosted matter.
TINY_JPEG = base64.b64decode(
    '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB'
    'AQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB'
    'AQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACv/EABQQAQAA'
    'AAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMR'
    'AD8AvwA//9k='
)

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


class TaskPriority(uno.OptionNS):
    high = uno.Option('✹ High', color=uno.Color.RED)
    medium = uno.Option('✷ Medium', color=uno.Color.YELLOW)
    low = uno.Option('✶ Low', color=uno.Color.GRAY)


class TaskStatusTodo(uno.OptionNS):
    backlog = uno.Option('Backlog', color=uno.Color.GRAY)
    blocked = uno.Option('Blocked', color=uno.Color.RED)


class TaskStatusInProgress(uno.OptionNS):
    in_progress = uno.Option('In Progress', color=uno.Color.BLUE)


class TaskStatusComplete(uno.OptionNS):
    done = uno.Option('Done', color=uno.Color.GREEN)


class Tasks(uno.Schema, db_title='Task DB'):
    """My personal task list of all the important stuff I have to do"""

    task = uno.PropType.Title('Task')
    status = uno.PropType.Status(
        'Status', to_do=TaskStatusTodo, in_progress=TaskStatusInProgress, complete=TaskStatusComplete
    )
    due_date = uno.PropType.Date('Due Date')
    priority = uno.PropType.Select('Priority', options=TaskPriority)
    urgency = uno.PropType.Formula(
        'Urgency', formula='if(prop("Status") == "Done", "✅", if(empty(prop("Due Date")), "", "🕘"))'
    )


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

    def find_ds(self, title: str) -> uno.DataSource | None:
        return self.one_match(list(self.notion.search_ds(title)), title, 'data source')

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

    def get_or_create_ds(self, title: str, schema: type[uno.Schema]) -> tuple[uno.DataSource, bool]:
        data_source = self.find_ds(title)
        if data_source is not None:
            # Bind the script schema only to seed an empty data source. An existing, hand-maintained one
            # may legitimately diverge -- e.g. Formula DB after its formula columns are recreated in the UI,
            # which Notion then types by result (Text/Number/...) rather than as generic formulas (#297).
            # Forcing the schema would reject that, so we keep whatever is already there.
            if data_source.is_empty:
                try:
                    data_source.schema = schema
                except SchemaError:
                    typer.echo(f'data source exists: {title} (schema differs from the script; keeping its own)')
                    return data_source, False
            typer.echo(f'data source exists: {title}')
            return data_source, False
        data_source = self.notion.create_ds(parent=self.root, schema=schema)
        typer.echo(f'created data source: {title}')
        return data_source, True

    def ensure_wiki_shell(self) -> None:
        if self.find_ds('Wiki DB') is not None:
            typer.echo('wiki exists: Wiki DB')
            return
        self.create_page('Wiki DB')
        typer.echo('manual step: open the Wiki DB page and select ... -> Turn into wiki')

    def ensure_contacts_db(self) -> None:
        database, created = self.get_or_create_ds('Contacts DB', Contacts)
        if created:
            # The icon lives on the container database; data-source icons have no high-level setter.
            self.client.databases.update(database_id=str(database.database_id), icon={'type': 'emoji', 'emoji': '🤝'})
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
        database, _ = self.get_or_create_ds('Task DB', Tasks)
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
        database, _ = self.get_or_create_ds('Formula DB', Formulas)
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
        database = self.find_ds('All Properties DB')
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
    def check_formula_filterable(database: uno.DataSource) -> None:
        """Verify the Formula DB's formula columns are real, computing formulas (`test_query_formula`).

        Notion rejects query filters on formula properties created via the public API ("Unable to filter
        based on a formula of unknown type", #297), so the columns must be recreated in the UI. They must
        be recreated as **Formula** columns, though: recreating them as plain Text/Number/Checkbox/Date
        columns (the formulas' result types) also clears the 400 but leaves them empty. So we check the
        actual computed value -- `String` (= `format(prop("Name"))`) must read `Item 1` for row `Item 1` --
        rather than merely that a filter does not error.
        """
        manual_hint = (
            'Formula DB: manual setup required - recreate String / Number / Checkbox / Date as '
            '**Formula** columns in the UI (not plain Text/Number/Checkbox/Date), with expressions '
            'String=format(prop("Name")), Number=prop("Tags").length(), '
            'Checkbox=prop("Tags").includes("Done"), Date=prop("Date Source"). See issue #297 / §4.'
        )
        try:
            rows = {page.props.name: page for page in database.get_all_pages()}
            item_1 = rows.get('Item 1')
            computed = None if item_1 is None else item_1.props.string
        except (HTTPResponseError, AttributeError) as exc:
            typer.echo(f'{manual_hint} ({exc})')
            return
        if computed == 'Item 1':
            typer.echo('Formula DB: formula columns OK')
        else:
            typer.echo(f'{manual_hint} (String for row "Item 1" reads {computed!r}, expected "Item 1")')

    def ensure_static_pages(self) -> None:
        self.create_page(
            'Getting Started',
            blocks=[
                uno.Heading1('Getting Started'),
                uno.Paragraph('Welcome to the Ultimate Notion test workspace.'),
            ],
        )
        self.ensure_markdown_text_page()
        self.ensure_markdown_test_page()
        self.create_page(
            'Embed/Inline/Linked & Unfurl',
            blocks=[
                uno.Embed('https://ultimate-notion.com/'),
                uno.Bookmark('https://ultimate-notion.com/'),
                uno.Paragraph('Inline link: https://ultimate-notion.com/'),
            ],
        )
        # `test_embed_blocks` requires the last block to be a real linked-database view, which the API
        # cannot create. (A placeholder paragraph would only render the wrong markdown, so we omit it.)
        typer.echo('manual step: add a linked-database view to the Embed page (see tests/TEST_WORKSPACE.md §6)')

        self.ensure_comments_page()

    def ensure_comments_page(self) -> None:
        """Create the `Comments` page and seed its 5 page-level comments (`test_list_comments`).

        Page comments are API-creatable and cannot be deleted via the API, so we only add them when the
        page has none, appending in order with the 5th reading `Another comment` (what the test checks).
        The heading's *inline* discussions (`test_append_block_comments`) cannot be started through the
        API and remain a manual step.
        """
        page = self.create_page('Comments', blocks=[uno.Heading1('Comments')])
        wanted = ['Comment 1', 'Comment 2', 'Comment 3', 'Comment 4', 'Another comment']
        existing = len(page.comments)
        if existing == 0:
            for text in wanted:
                page.comments.append(text)
            typer.echo(f'seeded Comments: {len(wanted)} page comments')
        elif existing == len(wanted):
            typer.echo('Comments: page comments already present')
        else:
            typer.echo(
                f'Comments: has {existing} page comment(s); test_list_comments expects {len(wanted)} '
                "with the 5th reading 'Another comment' -- comments cannot be deleted via the API, "
                'so adjust by hand if needed'
            )
        # Inline discussions on the heading cannot be created via the API.
        typer.echo('manual step: add 2 inline discussions to the Comments heading (see TEST_WORKSPACE.md §7)')

    def ensure_markdown_test_page(self) -> None:
        """Build the `Markdown Test` content fixture for `test_page_to_markdown`.

        Every block except the final two -- a Button and an AI block, which the Notion API cannot
        create -- is built here to match the test's `exp_output` line for line. Idempotent: a page that
        already contains the body (detected by a `Divider`) is left untouched; an empty or stub page is
        (re)built from scratch. The two unsupported blocks must still be added by hand
        (see tests/TEST_WORKSPACE.md §5).
        """
        page = self.find_page('Markdown Test')
        # Use a late, distinctive block as the "fully built" marker: a `Breadcrumb` appears near the end of
        # the body and is unlikely in a partial hand-build, so a stub or half-finished page is rebuilt while
        # a complete one (plus the hand-added unsupported blocks) is left intact on re-runs.
        if page is not None and any(isinstance(block, uno.Breadcrumb) for block in page.children):
            typer.echo('Markdown Test: body already built')
        else:
            if page is not None:
                page.delete()  # trash the stub/partial page and rebuild fresh (it is looked up by title)
            page = self.notion.create_page(parent=self.root, title='Markdown Test')
            self.build_markdown_test_body(page)
            typer.echo('built Markdown Test body')
        typer.echo('manual step: add a Button and an AI block at the end of Markdown Test (see TEST_WORKSPACE.md §5)')

    def build_markdown_test_body(self, page: uno.Page) -> None:
        """Append every API-creatable block of the Markdown Test fixture, in order."""
        add = page.append
        add([uno.Heading1('Headline 1'), uno.Heading2('Headline 2'), uno.Heading3('Headline 3'), uno.Divider()])
        # Toggle headings are siblings (not nested): nesting hides the inner headings from the rendered
        # markdown, which the test expects to see flattened.
        add(
            [
                uno.Heading1('Toggle Headline 1', toggleable=True),
                uno.Heading2('Toggle Headline 2', toggleable=True),
                uno.Heading3('Toggle Headline 3', toggleable=True),
            ]
        )
        add([uno.BulletedItem('Item 1'), uno.BulletedItem('Item 2\nwith a new line'), uno.BulletedItem('Item 3')])
        add(
            [uno.ToDoItem('ToDo1'), uno.ToDoItem('ToDo2\nwith a new line'), uno.ToDoItem('Checked ToDo3', checked=True)]
        )
        add(
            [
                uno.NumberedItem('First item'),
                uno.NumberedItem('Second item\nwith a new line'),
                uno.NumberedItem('Third item'),
            ]
        )
        add(uno.Quote('This is a quote\nwith a new line'))
        add(uno.Callout('Callout!'))
        table = uno.Table(3, 2)
        add(table)
        for row in range(3):
            table[row] = (f'Cell {row + 1}, 1', f'Cell {row + 1}, 2')
        add(uno.Paragraph('This is an emoji! \U0001f600\U0001f600'))
        add(uno.Equation(r'|x|=\begin{cases}x, &\quad x \geq 0\\-x, &\quad x < 0\end{cases}'))
        add(uno.Code('# Python Code\nimport ultimate_notion', language=uno.CodeLang.PYTHON))
        add(uno.Embed('https://picsum.photos/300/300', caption='Caption'))
        # The second image must be Notion-hosted (see TINY_JPEG), so upload it rather than link externally.
        uploaded = self.notion.upload(io.BytesIO(TINY_JPEG), file_name='1004-300x300.jpg', mime_type='image/jpeg')
        add(uno.Image(uploaded))
        add(
            uno.File(
                uno.ExternalFile(url='https://ultimate-notion.com/latest/assets/images/logo_with_text.svg'),
                name='logo_with_text.svg',
            )
        )
        add(uno.Audio(uno.ExternalFile(url='https://samplelib.com/lib/preview/mp3/sample-3s.mp3')))
        add(uno.Heading2('Unsupported Stuff in Markdown'))
        columns = uno.Columns(2)
        add(columns)
        columns[0].append(uno.Paragraph('Column 1'))
        columns[1].append(uno.Paragraph('Column'))
        add(uno.TableOfContents())
        add(uno.Breadcrumb())
        # The subpage is created here so its child-page block lands right after the breadcrumb.
        subpage = self.notion.create_page(parent=page, title='Markdown SubPage Test')
        subpage_synced = uno.SyncedBlock(uno.Paragraph('This is the original Paragraph on SubPage'))
        subpage.append(subpage_synced)
        add(uno.SyncedBlock(uno.Paragraph('This is the original Paragraph on Page')))
        add(subpage_synced.create_synced())  # a synced copy on this page of the block that lives on the subpage
        add(uno.LinkToPage(subpage))

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
            ('All Properties DB', 'data source'),
            ('Wiki DB', 'data source'),
            ('Custom Emoji Page', 'page'),
        ):
            obj = self.find_ds(title) if kind == 'data source' else self.find_page(title)
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
        """Return every object of `object_type` ('page'/'data_source') the integration can see."""
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
        if obj.get('object') in {'database', 'data_source'}:
            parts = obj.get('title') or []
        else:
            parts = []
            for prop in (obj.get('properties') or {}).values():
                if isinstance(prop, dict) and prop.get('type') == 'title':
                    parts = prop.get('title') or []
                    break
        text = ''.join(part.get('plain_text', '') for part in parts if isinstance(part, dict))
        return text or None

    @staticmethod
    def is_row(obj: dict[str, Any]) -> bool:
        """True if `obj` is a page that belongs to a data source (i.e. a database row).

        Rows are managed content of their data source, not free-standing pages, so they must
        not be reported (or pruned) as stray just because their title is not an expected one.
        """
        parent = obj.get('parent')
        parent_type = parent.get('type') if isinstance(parent, dict) else None
        return parent_type in {'data_source_id', 'database_id'}

    def audit_workspace_objects(self) -> None:
        """Report everything the integration can see and flag drift from the expected set.

        A perpetually-red weekly live job is invisible, and stray records (trashed,
        orphaned or limited-access leftovers) silently break searches (issue #273). This
        reports stray and missing objects so a fresh or polluted workspace is obvious, and
        optionally prunes accessible stray pages when run with `--prune`.
        """
        expected_titles = EXPECTED_PAGE_TITLES | EXPECTED_DATABASE_TITLES
        pages = self.iter_visible('page')
        databases = self.iter_visible('data_source')

        visible_titles: set[str] = set()
        property_less = 0
        stray: list[dict[str, Any]] = []
        for obj in (*pages, *databases):
            title = self.raw_title(obj)
            if title is None:
                property_less += 1
            else:
                visible_titles.add(title)
            if self.is_row(obj):  # rows of a data source are managed content, never stray
                continue
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
