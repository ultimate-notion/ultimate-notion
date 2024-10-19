from __future__ import annotations

import pytest

import ultimate_notion as uno
from ultimate_notion.blocks import TextBlock


@pytest.mark.vcr()
def test_rich_text_md(md_text_page: uno.Page):
    """These markdowns were tested with https://stackedit.io/app#"""
    correct_mds = [
        'here is something **very** *simpel* and <u>underlined</u> as well as `code`',
        '**here is a sentence that was bolded *then* typed.**',
        'here is a test sentence with ~~many **different *styles*.**~~',
        'here is another test with ~~many *different **styles**.*~~',
        'here is one more with a *strange **style*** **combination**',
        'here is one with an inline **~~equa-*tion*~~ *$E=mc^2$ and*** no block equation',
        (
            'and here is one with ~~***person** mention [@Florian Wilhelm]()*~~ and **page mention '
            '↗[Markdown Text Test](https://www.notion.so/0c8ea7f1c7ca4abb8890085c0fac383b)** '
        ),
        'here is one **stretching over *many\n~~many~~*\n~~lines~~**',
        # ToDo: This is not 100% right as line breaks in code blocks are ignored in Markdown.
        # Thus '\n' in the last code block will be ignored and the code will be in one line.
        # To Fix this we would have to break rich_texts into multiple code blocks.
        'This is code, e.g. **`python` code\nnow stretching `over\nmany lines`**',
        'This is a [li**n**k](https://google.de/) and a ~~first~~ an~~d <u>second</u> stroke~~ through<u> word.</u>',
        'Half a [lin](https://google.de/)[k](https://amazon.com/) for two destinations',
        '✨Magic ✨',
    ]
    for idx, block in enumerate(md_text_page.children):
        assert isinstance(block, TextBlock)
        our_md = block.rich_text.to_markdown()
        assert our_md == correct_mds[idx]
