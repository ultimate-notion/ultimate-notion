# Data models & schemas

# Todo: Use to run this https://github.com/koaning/mktestdocs

We gonna create two simple databases with a relation quite similar as described
in the [Notion docs]. We gonna have a database for customers and one for items
, which customers can purchase.

Let's first initialize a Notion session:

```python
>>> from ultimate_notion import Session
>>>
>>> notion = Session()

```

We start by defining the schema for our items:

```python
>>> from ultimate_notion import PageSchema, Property, schema
>>>
>>> sizes = [
...     schema.SelectOption(name="S"),
...     schema.SelectOption(name="M", color="red"),
...     schema.SelectOption(name="L", color="yellow"),
... ]
>>>
>>>
>>> class Item(PageSchema):
...     name = Property("Name", schema.Title())
...     size = Property("Size", schema.SingleSelect(sizes))
...     price = Property("price", schema.Number(schema.NumberFormat.DOLLAR))

```

Since a database needs to be a block wighin a page, we assume there is a page called
'Tests', which is connected with this integration script. We retrieve the object of
this page and create the database with the page as parent page.

```python
>>> root_page = notion.search_page('Tests', exact=True).item()
>>> item_db = notion.create_db(parent=root_page, schema=Item, title='Items')

```

Now we create a database for our customers and define a one-way relation to the items:

```python
>>> class Customer(PageSchema):
...     name = Property("Name", schema.Title())
...     purchases = Property("Items Purchased", schema.Relation(item_db))
>>>
>>> customer_db = notion.create_db(parent=root_page, schema=Customer, title='Customers')

```

The databases are created and we can start filling them with a few items.

```python
>>> # some items
>>> t_shirt = item_db.create_page(name="T-shirt", size="M", prize=17)
>>> khaki_pants = item_db.create_page(name="Khaki pants", size="M", prize=25)
>>> tank_top = item_db.create_page(name="Tank top", size="S", prize=15)
>>>
>>> # some customers
>>> lovelace = customer_db.create_page(name="Ada Lovelace")
>>> hertzfeld = customer_db.create_page(name="Andy Herzfeld")
>>> Engelbart = customer_db.create_page(name="Doug Engelbart")

```

Note that that the keyword-arguments are exactly the class variables from the page
schemas `Item` and `Customer` above.

Since all pages are by default live-updated, we can modify the page objects to change
the data in the actual Notion dababases. Let's say Ada Lovelace purchased a tank top
as well as some khaki pants.

```python
>>> lovelace.prop.purchases.extend([tank_top, khaki_pants])
>>> lovelace
Customer("Ada Lovelace")
>>> print(lovelace)
Customer(
    name="Ada Lovelace",
    purchases=[Item("Tank top"), Item("Khaki pants")],
)
```

!!! tip
    Use `ensure_db` and `ensure_page` to get or create a database and to get or
    create a page, respectively. This allows you to avoid extra codepaths in the
    initial phase when setting up a database for instance. Note that the *title*
    property is used as the unique identifier for a database or page.





[Notion docs]: https://www.notion.so/help/relations-and-rollups#create-a-relation
