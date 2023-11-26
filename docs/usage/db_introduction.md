# Introduction to databases

Databases are one of the most versatile and powerful features of Notion.
Working programmatically with your databases extends Notion's functionality to infinity
as you can use Python for all kinds of transformations, use external data services and what not.
Ultimate Notion unleashes the full power of Python for use with Notion's databases.
So let's see what we can do.

## Reading a database

Assume we have a database called "Contacts DB".

```python
from ultimate_notion import Session

notion = Session.get_or_create()  # if NOTION_TOKEN is set in environment

contacts_dbs = notion.search_db("Contacts DB")

assert [db.title for db in contacts_dbs] == ["Contacts DB"]
```

The method `search_db` will always return a list as Notion gives no guarantees that the
title of a database is unique. Practically though, most users will give databases unique
names and to accommodate for this, the returned list provides a method `.item()`, which
will return the item of a single-item list or raise an error otherwise. Another possibility
would be to retrieve the database by its unqiue id.

```python
contacts_db = notion.search_db("Contacts DB").item()
# or in case the unique ID of the database is known
contacts_db = notion.get_db(contacts_db.id)
```

The [Database object] provides access to many attributes like [title], [icon], [description], etc.

```python
assert contacts_db.description == "Database of all my contacts!"
```

### Accessing the content of a database

Describe a simple Tasklist here!

[Database object]: ../../reference/ultimate_notion/database/#ultimate_notion.database.Database
[title]: ../../reference/ultimate_notion/database/#ultimate_notion.database.Database.title
[icon]: ../../reference/ultimate_notion/database/#ultimate_notion.database.Database.icon
[description]: ../../reference/ultimate_notion/database/#ultimate_notion.database.Database.description
