"""This example demonstrates how to create an Ultimate Notion session"""

import ultimate_notion as uno

PAGE_TITLE = 'Getting Started'

with uno.Session() as notion:
    page = notion.search_page(PAGE_TITLE).item()
    print(page.title)

# Alternatively, without a context manager:
notion = uno.Session()
page = notion.search_page(PAGE_TITLE).item()
print(page.title)
notion.close()
