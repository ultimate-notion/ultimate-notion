"""This example demonstrated how to create a ultimate notion session"""

from ultimate_notion import Session

TOKEN = 'secret_YOUR_TOKEN_HERE'
PAGE_TITLE = 'Getting Started'  # Change this to the title of your page

with Session(auth=TOKEN) as notion:
    page = notion.search_page(PAGE_TITLE).item()
    print(page.show())

# alternatively, without a context manager
notion = Session.get_or_create(auth=TOKEN)
# or if `NOTION_TOKEN` is set, just type:
# notion = Session.get_or_create()
# which also works for the context manager
page = notion.search_page(PAGE_TITLE).item()
print(page.show())
notion.close()
