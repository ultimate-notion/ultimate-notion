from ultimate_notion import Session

TOKEN = 'secret_INSERT_YOUR_TOKEN_HERE'
PAGE_TITLE = 'Getting Started'  # Change this to the title of your page

with Session(auth=TOKEN) as notion:
    page = notion.search_page(PAGE_TITLE).item()
    print(page)
