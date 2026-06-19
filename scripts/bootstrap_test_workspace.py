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

DEFAULT_ROOT_TITLE = 'Tests'
MAX_REQUEST_ATTEMPTS = 5

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
    def __init__(self, notion: uno.Session, root_title: str) -> None:
        self.notion = notion
        self.client = notion.client
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
        if not database.is_empty:
            typer.echo('Formula DB already has rows')
            return
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

    def ensure_static_pages(self) -> None:
        self.create_page(
            'Getting Started',
            blocks=[
                uno.Heading1('Getting Started'),
                uno.Paragraph('Welcome to the Ultimate Notion test workspace.'),
            ],
        )
        self.create_page(
            'Markdown Text Test',
            blocks=[uno.Paragraph('Markdown rich-text fixture.')],
        )
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

    def audit_manual_objects(self) -> None:
        for title, kind in (
            ('All Properties DB', 'database'),
            ('Wiki DB', 'database'),
            ('Custom Emoji Page', 'page'),
        ):
            obj = self.find_database(title) if kind == 'database' else self.find_page(title)
            status = 'ready' if obj is not None else 'manual setup required'
            typer.echo(f'{title}: {status}')

    def run(self) -> None:
        self.ensure_wiki_shell()
        self.ensure_contacts_db()
        self.ensure_task_db()
        self.ensure_formula_db()
        self.ensure_static_pages()
        self.audit_manual_objects()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--root-title',
        default=os.environ.get('UNO_TEST_ROOT_PAGE', DEFAULT_ROOT_TITLE),
        help='Title of the root page shared with the integration.',
    )
    args = parser.parse_args()
    token = os.environ.get('NOTION_TOKEN')
    if not token:
        parser.error('NOTION_TOKEN must be set')
    with uno.Session(client=RetryingClient(auth=token)) as notion:
        Bootstrap(notion, args.root_title).run()


if __name__ == '__main__':
    main()
