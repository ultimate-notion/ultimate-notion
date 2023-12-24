"""This example demonstrates how to create an Ultimate Notion session"""

import ultimate_notion as uno

TOKEN = "secret_YOUR_TOKEN_HERE"
# Change PAGE_TITLE to the title of your page
PAGE_TITLE = "Getting Started"

with uno.Session(auth=TOKEN) as notion:
    page = notion.search_page(PAGE_TITLE).item()
    page.show()

# Alternatively, without a context manager:
notion = uno.Session.get_or_create(auth=TOKEN)
# `auth` can be omitted if `NOTION_TOKEN` is set in the environment, e.g.
# notion = Session.get_or_create()
# which also works for the context manager
page = notion.search_page(PAGE_TITLE).item()
page.show()
notion.close()
