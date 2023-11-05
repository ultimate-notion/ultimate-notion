from ultimate_notion import Session

TOKEN = 'secret_INSERT_YOUR_TOKEN_HERE'
PAGE_TITLE = 'Getting Started'  # Change this to the title of your page

with Session(auth=TOKEN) as notion:
    page = notion.search_page(PAGE_TITLE).item()
    print(page.show())

# alternatively, without a context manager
notion = Session.get_or_create(auth=TOKEN)
# or if NOTION_AUTH_TOKEN is set in environment, just
# notion = Session.get_or_create()
page = notion.search_page(PAGE_TITLE).item()
print(page.show())
notion.close()
