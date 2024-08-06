import os
import string
from importlib.resources import read_text
from types import ModuleType


def get_template(name: str, relative_to: str | ModuleType = __name__) -> string.Template:
    """Retrieve the template by name"""
    if isinstance(relative_to, ModuleType):
        relative_to = relative_to.__name__

    data = read_text(relative_to, name, encoding='utf-8')
    # we assure that line endings are converted to '\n' for all OS
    content = data.replace(os.linesep, '\n')
    return string.Template(content)


def page_html(content: str, *, title: str = '') -> str:
    """Wrap the content of the page as proper HTML for displaying."""
    template = get_template('page.html')
    return template.safe_substitute(content=content, title=title)
