# Data models & schemas

We gonna create two simple databases with a relation quite similar as described
in the [Notion docs]. We gonna have a database for customers and one for items,
which customers can purchase.

Let's first initialize a Notion session with

```python
import ultimate_notion as uno

notion = uno.Session.get_or_create()
```

## Declarative schemas & relations

We start by defining the schema for our items in a really pythonic way.
The schema should have three properties, the title property `Name` for the name of an item, e.g. "Jeans",
a size property `Size` and of course a `Price` property numbers in Dollars. The size of of piece of
clothing can be chosen from the options `S`, `M` and `L`. We can directly translate this schema into
Python code:

```python
class Size(uno.OptionNS):
    """Namespace for the select options of our various sizes"""
    S = uno.Option(name='S', color=uno.Color.GREEN)
    M = uno.Option(name='M', color=uno.Color.YELLOW)
    L = uno.Option(name='L', color=uno.Color.RED)


class Item(uno.Schema, db_title='Item DB'):
    """Database of all the items we sell"""
    name = uno.Property('Name', uno.PropType.Title())
    size = uno.Property('Size', uno.PropType.Select(Size))
    price = uno.Property('Price', uno.PropType.Number(uno.NumberFormat.DOLLAR))
```

Since a database needs to be a block wighin a page, we assume there is a page called
`Tests`, which is connected with this integration. We retrieve the object of
this page and create the database with the page as parent page.

```python
root_page = notion.search_page('Tests', exact=True).item()
item_db = notion.create_db(parent=root_page, schema=Item)
```

Now we create a database for our customers and define a one-way [Relation] to the items:

```python
class Customer(uno.Schema, db_title='Customer DB'):
    """Database of all our beloved customers"""
    name = uno.Property('Name', uno.PropType.Title())
    purchases = uno.Property('Items Purchased', uno.PropType.Relation(Item))

customer_db = notion.create_db(parent=root_page, schema=Customer)
```

!!! warning
    To create a database that has a relation to another database requires that the target
    database already exists. Thus the order of creating the databases from the schemas
    is important.

All available types of a database property are provided by [PropType], which is just a namespace
for the various property types defined in [schema]. Property types with the class
variable `allowed_at_creation` set to `False` are currently not supported by the Notion API.
when creating a new database.

## New database entries

Now that we have created those two databases, we can start filling them with a few entries
either using the [create_page] method of the database object:

```python
t_shirt = item_db.create_page(name='T-shirt', size=Size.L, price=17)
khaki_pants = item_db.create_page(name='Khaki pants', size=Size.M, price=25)
tank_top = item_db.create_page(name='Tank top', size=Size.S, price=15)
```

or we can also directly use the [create] method of the schema if the schema is already bound
to a database:

```python
lovelace = Customer.create(name='Ada Lovelace', purchases=[tank_top])
hertzfeld = Customer.create(name='Andy Herzfeld', purchases=[khaki_pants])
engelbart = Customer.create(name='Doug Engelbart', purchases=[khaki_pants, t_shirt])
```

!!! info
    The keyword-arguments are exactly the class variables from the page schemas `Item` and `Customer` above.

This is how our two databases `item_db` and `customer_db` look like in the Notion UI right now:

![Notion item database](../assets/images/notion-item-db.png){: style="width:800px; display:block; margin-left:auto; margin-right:auto;"}

![Notion customer database](../assets/images/notion-customer-db.png){: style="width:800px; display:block; margin-left:auto; margin-right:auto;"}

!!! note
    The description of the databases corresponds to the the docstring of the schema classes `Item` and `Customer`.

## Fast access to page properties

The properties of a page, defined by the properties of the database the page resides in, can be easily accessed with
the `.props` namespace, e.g.:

```python
assert lovelace.props.name == 'Ada Lovelace'
assert engelbart.props.purchases == [khaki_pants, t_shirt]
```

This is especially neat when using a REPL with autocompletion like [JupyterLab] or [IPython].
As an alternative, also the bracket-notation can be used. This allows us to use the actual property names
fro the schema definition, e.g.:

```python
assert lovelace.props['Name'] == 'Ada Lovelace'
assert engelbart.props['Items Purchased'] == [khaki_pants, t_shirt]
```

## Two-way & self relations

Notion also supports two-way relations and so does Ultimate Notion. Taking the same example as before, imagine
that we also wanted to see direclty which customers bought a specific item. In this case the one-way relation `Items Purchased`
from `Customer` needs to become a two-way relation. We can achieve this, with a simple modification in both schemas:

```python
class Item(uno.Schema, db_title='Item DB'):
    """Database of all the items we sell"""
    name = uno.Property('Name', uno.PropType.Title())
    size = uno.Property('Size', uno.PropType.Select(Size))
    price = uno.Property('Price', uno.PropType.Number(uno.NumberFormat.DOLLAR))
    bought_by = uno.Property('Bought by', uno.PropType.Relation())

class Customer(uno.Schema, db_title='Customer DB'):
    """Database of all our beloved customers"""
    name = uno.Property('Name', uno.PropType.Title())
    purchases = uno.Property(
        'Items Purchased',
        uno.PropType.Relation(Item, two_way_prop=Item.bought_by)
    )
```

So what happens here is that we first create a *target* relation property `bought_by` in `Item` by not
specifying any other schema. Then in `Customer`, we define now a two-way property but specifying not only
the schema `Item` bouth also the property we want to synchronize with using the `two_way_prop` keyword.

Let's delete the old databases and recreate them with our updates schemas and a few items

```python
item_db.delete(), customer_db.delete()

item_db = notion.create_db(parent=root_page, schema=Item)
customer_db = notion.create_db(parent=root_page, schema=Customer)

t_shirt = item_db.create_page(name='T-shirt', size=Size.L, price=17)
lovelace = Customer.create(name='Ada Lovelace', purchases=[t_shirt])
hertzfeld = Customer.create(name='Andy Herzfeld', purchases=[t_shirt])
```

and take a look at the two-way relation within `item_db`:

![Notion customer database wiht two-way relation](../assets/images/notion-item-db-two-way.png){: style="width:800px; display:block; margin-left:auto; margin-right:auto;"}

Assume now that we want to have a schema that references itself, for instance a simple task list like where
certain tasks can be subtasks of others:

```python
class Task(uno.Schema, db_title='Task List'):
    """A really simple task lists with subtasks"""
    task = uno.Property('Task', uno.PropType.Title())
    due_by = uno.Property('Due by', uno.PropType.Date())
    parent = uno.Property('Parent Task', uno.PropType.Relation(uno.SelfRef))

task_db = notion.create_db(parent=root_page, schema=Task)

from datetime import datetime, timedelta

today = datetime.now()

clean_house = Task.create(
    task='Clean the house',
    due_by=today + timedelta(weeks=4)
)
vacuum_room = Task.create(
    task='Vacuum living room',
    due_by=today + timedelta(weeks=1),
    parent=clean_house
)
tidyup_kitchen = Task.create(
    task='Tidy up kitchen',
    due_by=today + timedelta(days=3),
    parent=clean_house
)
```

!!! Warning
    Due to a bug in the Notion API, it's not possible to have a two-way self-referencing relation right now.
    Creating a two-way relation leads to the creation of a one-way relation. We check for that and fail.

[Notion docs]: https://www.notion.so/help/relations-and-rollups#create-a-relation
[create_page]: ../../reference/ultimate_notion/database/#ultimate_notion.database.Database.create_page
[create]: ../../reference/ultimate_notion/schema/#ultimate_notion.schema.Schema.create
[Relation]:  ../../reference/ultimate_notion/schema/#ultimate_notion.schema.Relation
[PropType]: ../../reference/ultimate_notion/schema/#ultimate_notion.schema.PropType
[schema]: ../../reference/ultimate_notion/schema/#ultimate_notion.schema
