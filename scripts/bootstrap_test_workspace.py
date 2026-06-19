"""Create the API-creatable objects used by the live test suite.

The script is idempotent: objects that already exist are left unchanged.
Set NOTION_TOKEN and share the root page with the integration before running it.
"""

import argparse
import inspect
import os
import time
from typing import Any

from notion_client import Client

DEFAULT_ROOT_TITLE = 'Tests'


def sync_object(response: Any) -> dict[str, Any]:
    """Validate a JSON object returned by the synchronous Notion client."""
    if inspect.isawaitable(response):
        msg = 'The workspace bootstrap requires the synchronous Notion client.'
        raise TypeError(msg)
    if not isinstance(response, dict):
        msg = f'Expected a JSON object from Notion, got {type(response).__name__}.'
        raise TypeError(msg)
    return response


def object_list(value: Any) -> list[dict[str, Any]]:
    """Validate a list of JSON objects."""
    if not isinstance(value, list):
        msg = f'Expected a JSON array from Notion, got {type(value).__name__}.'
        raise TypeError(msg)

    result = []
    for item in value:
        if not isinstance(item, dict):
            msg = f'Expected a JSON object in the Notion response, got {type(item).__name__}.'
            raise TypeError(msg)
        result.append(item)
    return result


def rich_text(text: str) -> list[dict[str, Any]]:
    return [{'type': 'text', 'text': {'content': text}}]


def title_of(obj: dict[str, Any]) -> str:
    if obj['object'] == 'database':
        return ''.join(item.get('plain_text', '') for item in obj.get('title', []))
    for prop in obj.get('properties', {}).values():
        if prop.get('type') == 'title':
            return ''.join(item.get('plain_text', '') for item in prop.get('title', []))
    return ''


class Bootstrap:
    def __init__(self, client: Client, root_title: str) -> None:
        self.client = client
        self.root_title = root_title
        root = self.find_exact(root_title, 'page')
        if root is None:
            msg = f'Root page {root_title!r} was not found. Share it with the integration first.'
            raise RuntimeError(msg)
        self.root = root

    def search_exact(self, title: str, kind: str) -> list[dict[str, Any]]:
        response = sync_object(
            self.client.search(
                query=title,
                filter={'property': 'object', 'value': kind},
                page_size=100,
            ),
        )
        return [obj for obj in response['results'] if title_of(obj) == title]

    def find_exact(self, title: str, kind: str) -> dict[str, Any] | None:
        matches = self.search_exact(title, kind)
        if len(matches) > 1:
            msg = f'Found multiple {kind}s titled {title!r}; remove duplicates before bootstrapping.'
            raise RuntimeError(msg)
        return matches[0] if matches else None

    def create_page(
        self,
        title: str,
        *,
        parent_id: str | None = None,
        children: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if page := self.find_exact(title, 'page'):
            print(f'page exists: {title}')
            return page
        page = sync_object(
            self.client.pages.create(
                parent={'page_id': parent_id or self.root['id']},
                properties={'title': {'title': rich_text(title)}},
                children=children or [],
            ),
        )
        print(f'created page: {title}')
        time.sleep(0.4)
        return page

    def create_database(
        self,
        title: str,
        properties: dict[str, Any],
        *,
        description: str | None = None,
        icon: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if database := self.find_exact(title, 'database'):
            print(f'database exists: {title}')
            return database
        kwargs: dict[str, Any] = {
            'parent': {'page_id': self.root['id']},
            'title': rich_text(title),
            'properties': properties,
        }
        if description is not None:
            kwargs['description'] = rich_text(description)
        if icon is not None:
            kwargs['icon'] = icon
        database = sync_object(self.client.databases.create(**kwargs))
        print(f'created database: {title}')
        time.sleep(0.7)
        return database

    def database_rows(self, database: dict[str, Any]) -> list[dict[str, Any]]:
        response = sync_object(
            self.client.databases.query(database_id=database['id'], page_size=100),
        )
        return object_list(response.get('results'))

    def create_database_page(
        self,
        database: dict[str, Any],
        title_prop: str,
        title: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        values = {title_prop: {'title': rich_text(title)}}
        values.update(properties or {})
        self.client.pages.create(parent={'database_id': database['id']}, properties=values)
        time.sleep(0.25)

    def ensure_wiki_shell(self) -> None:
        if self.find_exact('Wiki DB', 'database'):
            print('wiki exists: Wiki DB')
            return
        self.create_page('Wiki DB')
        print('manual step: open the Wiki DB page and select ... -> Turn into wiki')

    def ensure_contacts_db(self) -> None:
        database = self.create_database(
            'Contacts DB',
            {
                'Name': {'title': {}},
                'Title': {'rich_text': {}, 'description': 'Title within the company'},
                'Role': {
                    'select': {
                        'options': [
                            {'name': 'Project Manager', 'color': 'green'},
                            {'name': 'Software Engineer', 'color': 'gray'},
                            {'name': 'UX Designer', 'color': 'red'},
                            {'name': 'Marketing Manager', 'color': 'orange'},
                            {'name': 'Data Analyst', 'color': 'blue'},
                            {'name': 'QA Engineer', 'color': 'default'},
                            {'name': 'Technical Writer', 'color': 'pink'},
                            {'name': 'Business Analyst', 'color': 'purple'},
                            {'name': 'IT Support Specialist', 'color': 'yellow'},
                        ]
                    }
                },
                'Email': {'email': {}},
                'Phone': {'phone_number': {}},
                'URL': {'url': {}},
                'Team Member': {'checkbox': {}},
                'Sync Date': {'date': {}},
            },
            description='Database of all my contacts!',
            icon={'type': 'emoji', 'emoji': '🤝'},
        )
        if self.database_rows(database):
            print('Contacts DB already has rows')
            return
        roles = [
            'Project Manager',
            'Software Engineer',
            'UX Designer',
            'Marketing Manager',
            'Data Analyst',
            'QA Engineer',
            'Technical Writer',
            'Business Analyst',
            'IT Support Specialist',
            'Software Engineer',
        ]
        for idx, role in enumerate(roles, 1):
            self.create_database_page(
                database,
                'Name',
                f'Contact {idx}',
                {
                    'Title': {'rich_text': rich_text(f'Title {idx}')},
                    'Role': {'select': {'name': role}},
                    'Email': {'email': f'contact{idx}@example.com'},
                    'Team Member': {'checkbox': idx % 2 == 0},
                },
            )
        print('seeded Contacts DB: 10 rows')

    def ensure_task_db(self) -> None:
        database = self.create_database(
            'Task DB',
            {
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
                        'expression': 'if(prop("Status") == "Done", "✅", if(empty(prop("Due Date")), "", "🕘"))'
                    }
                },
            },
            description='My personal task list of all the important stuff I have to do',
        )
        if self.database_rows(database):
            print('Task DB already has rows')
            return
        rows = [
            ('Run first Marathon', 'In Progress', '✹ High', '2026-07-01T12:00:00.000+00:00'),
            ('Buy milk', 'Backlog', '✶ Low', '2026-07-02T12:00:00.000+00:00'),
            ('Ship release', 'Done', '✷ Medium', '2026-06-18T12:00:00.000+00:00'),
        ]
        for name, status, priority, due_date in rows:
            self.create_database_page(
                database,
                'Task',
                name,
                {
                    'Status': {'status': {'name': status}},
                    'Priority': {'select': {'name': priority}},
                    'Due Date': {'date': {'start': due_date}},
                },
            )
        print('seeded Task DB: 3 rows')

    def ensure_formula_db(self) -> None:
        database = self.create_database(
            'Formula DB',
            {
                'Name': {'title': {}},
                'Tags': {
                    'multi_select': {
                        'options': [
                            {'name': 'In Progress', 'color': 'pink'},
                            {'name': 'Done', 'color': 'gray'},
                        ]
                    }
                },
                'Date Source': {'date': {}},
                'String': {'formula': {'expression': 'format(prop("Name"))'}},
                'Number': {'formula': {'expression': 'prop("Tags").length()'}},
                'Checkbox': {'formula': {'expression': 'prop("Tags").includes("Done")'}},
                'Date': {'formula': {'expression': 'prop("Date Source")'}},
            },
        )
        if self.database_rows(database):
            print('Formula DB already has rows')
            return
        for title, tags in (('Item 1', ['Done', 'In Progress']), ('Item 2', ['In Progress'])):
            self.create_database_page(
                database,
                'Name',
                title,
                {
                    'Tags': {'multi_select': [{'name': tag} for tag in tags]},
                    'Date Source': {'date': {'start': '2024-11-25T14:08:00.000+00:00'}},
                },
            )
        print('seeded Formula DB: 2 rows')

    def ensure_static_pages(self) -> None:
        self.create_page(
            'Getting Started',
            children=[
                {
                    'object': 'block',
                    'type': 'heading_1',
                    'heading_1': {'rich_text': rich_text('Getting Started'), 'color': 'default'},
                },
                {
                    'object': 'block',
                    'type': 'paragraph',
                    'paragraph': {
                        'rich_text': rich_text('Welcome to the Ultimate Notion test workspace.'),
                        'color': 'default',
                    },
                },
            ],
        )
        self.create_page(
            'Markdown Text Test',
            children=[
                {
                    'object': 'block',
                    'type': 'paragraph',
                    'paragraph': {
                        'rich_text': rich_text('Markdown rich-text fixture.'),
                        'color': 'default',
                    },
                }
            ],
        )
        markdown_page = self.create_page(
            'Markdown Test',
            children=[
                {
                    'object': 'block',
                    'type': 'heading_1',
                    'heading_1': {'rich_text': rich_text('Headline 1'), 'color': 'default'},
                }
            ],
        )
        self.create_page(
            'Markdown SubPage Test',
            parent_id=markdown_page['id'],
            children=[
                {
                    'object': 'block',
                    'type': 'paragraph',
                    'paragraph': {
                        'rich_text': rich_text('This is the original Paragraph on SubPage'),
                        'color': 'default',
                    },
                }
            ],
        )
        self.create_page(
            'Embed/Inline/Linked & Unfurl',
            children=[
                {'object': 'block', 'type': 'embed', 'embed': {'url': 'https://ultimate-notion.com/'}},
                {'object': 'block', 'type': 'bookmark', 'bookmark': {'url': 'https://ultimate-notion.com/'}},
                {
                    'object': 'block',
                    'type': 'paragraph',
                    'paragraph': {
                        'rich_text': rich_text('Inline link: https://ultimate-notion.com/'),
                        'color': 'default',
                    },
                },
                {
                    'object': 'block',
                    'type': 'paragraph',
                    'paragraph': {'rich_text': rich_text('Linked database placeholder'), 'color': 'default'},
                },
            ],
        )
        self.create_page(
            'Comments',
            children=[
                {
                    'object': 'block',
                    'type': 'heading_1',
                    'heading_1': {'rich_text': rich_text('Comments'), 'color': 'default'},
                }
            ],
        )

    def audit_manual_objects(self) -> None:
        for title, kind in (
            ('All Properties DB', 'database'),
            ('Wiki DB', 'database'),
            ('Custom Emoji Page', 'page'),
        ):
            status = 'ready' if self.find_exact(title, kind) else 'manual setup required'
            print(f'{title}: {status}')

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
    Bootstrap(Client(auth=token), args.root_title).run()


if __name__ == '__main__':
    main()
