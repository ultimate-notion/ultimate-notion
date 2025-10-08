# Data models & schemas

We'll create two simple databases with a relation quite similar to those described
in the [Notion docs]. We'll have a database for customers and one for items,
which customers can purchase.

Let's first initialize a Notion session:

```python
import ultimate_notion as uno

notion = uno.Session.get_or_create()
```

## Declarative way of defining a schema

We start by defining the schema for our items in a truly Pythonic way.
The schema should have three properties: the title property `Name` for the name of an item (e.g., "Jeans"),
a size property `Size`, and of course a `Price` property in US Dollars. The size of a piece of
clothing can be chosen from the options `S`, `M`, and `L`. We can directly translate this schema into
Python code:

```python
class Size(uno.OptionNS):
    """Namespace for the select options of our various sizes"""
    S = uno.Option(name='S', color=uno.Color.GREEN)
    M = uno.Option(name='M', color=uno.Color.YELLOW)
    L = uno.Option(name='L', color=uno.Color.RED)


class Item(uno.Schema, db_title='Item DB'):
    """Database of all the items we sell"""
    name = uno.PropType.Title('Name')
    size = uno.PropType.Select('Size', options=Size)
    price = uno.PropType.Number('Price', format=uno.NumberFormat.DOLLAR)
```

The `db_title` parameter in the schema definition is optional but highly recommended. When provided,
it sets the default title for the database when calling `create_db()` without an explicit `title`
argument. Also it allows you to relate your schema to an existing database.

Alternatively, you can specify a `db_id` parameter to bind the schema to an existing database:

```python
class Item(uno.Schema, db_id='550e8400-e29b-41d4-a716-446655440000'):
    """Database of all the items we sell"""
    name = uno.PropType.Title('Name')
    size = uno.PropType.Select('Size', options=Size)
    price = uno.PropType.Number('Price', format=uno.NumberFormat.DOLLAR)
```

When `db_id` is provided, you can easily bind the schema to the existing database using `bind_db()`
without having to manually search for it.If neither `db_id` nor `db_title` is provided, you'll need
to pass a database object explicitly to `bind_db()` or provide a title when creating the database.

Since a database needs to be a block within a page, we assume there is a page called
`Tests` that is connected with this integration. We retrieve the object of
this page and create the database with the page as parent:

```python
root_page = notion.search_page('Tests', exact=True).item()
item_db = notion.create_db(parent=root_page, schema=Item)
```

Now we create a database for our customers and define a one-way [Relation] to the items:

```python
class Customer(uno.Schema, db_title='Customer DB'):
    """Database of all our beloved customers"""
    name = uno.PropType.Title('Name')
    purchases = uno.PropType.Relation('Items Purchased', schema=Item)

customer_db = notion.create_db(parent=root_page, schema=Customer)
```

!!! warning
    To create a database that has a relation to another database, the target
    database must already exist. Thus, the order of creating databases from schemas
    is important.

All available database property types are provided by [PropType], which is a namespace
for the various property types defined in [schema]. Property types with the class
variable `allowed_at_creation` set to `False` are currently not supported by the Notion API
when creating a new database.

## Programmatic way of defining a schema

Besides the recommended *declarative* approach to define a schema, you can also choose a
more classical *programmatic* approach. The main difference is that we first create
a database with a default schema and then start adding new properties (i.e., columns) to it.

```python
employee_db = notion.create_db(parent=root_page)
employee_db.title = 'Employee DB'
employee_db.description = 'Database holding all our employees'

employee_db.schema['Salary'] = uno.PropType.Number()
employee_db.schema.hiring_date = uno.PropType.Date('Hiring Date')

options = [uno.Option(name='Junior', color=uno.Color.GREEN),
           uno.Option(name='Advanced', color=uno.Color.YELLOW),
           uno.Option(name='Senior', color=uno.Color.RED)]

employee_db.schema['Level'] = uno.PropType.Select(options=options)
```

As shown above, there are two ways to add new properties:

1. Dictionary item assignment of a [PropType] to the schema
2. Property assignment of a [PropType] to the schema

In the first case, a corresponding property `salary` of the schema will be created automatically.

This also allows us to perform schema evolution by changing and updating columns:

```python
employee_db.schema['Salary'] = uno.PropType.Formula(
    formula='50000 + dateBetween(prop("Hiring Date"), now(), "years")*1000'
)
employee_db.schema['Level'].options = [
    *options,
    uno.Option(name='Partner', color=uno.Color.PINK)
]
employee_db.schema.hiring_date = uno.PropType.Text()
employee_db.schema.hiring_date.name = 'Hiring Date as String'
employee_db.schema['Hiring Date as String'].name = 'Hiring Date'
employee_db.schema.hiring_date.attr_name = 'hiring_date_as_str'
assert employee_db.schema.hiring_date_as_str == uno.PropType.Text()
```

This changes the salary property to a formula type, adds a partner level to the level property,
changes the hiring date to a text type, and modifies its name. This is then followed by setting
the name back using property access. It also shows how `attr_name` can be used to set the actual
attribute name of the schema object to `hiring_date_as_str`.

Of course, we can also delete properties:

```python
del employee_db.schema['Salary']
employee_db.schema.hiring_date_as_str.delete()
```

Again using both the dictionary and the property approach.

## New database entries

Now that we have created those two databases, we can start filling them with entries
either using the [create_page] method of the database object:

```python
t_shirt = item_db.create_page(name='T-shirt', size=Size.L, price=17)
khaki_pants = item_db.create_page(name='Khaki pants', size=Size.M, price=25)
tank_top = item_db.create_page(name='Tank top', size=Size.S, price=15)
```

or we can also directly use the [create] method of the schema if the schema is already bound
(e.g., by using [bind_db]) to a database:

```python
lovelace = Customer.create(name='Ada Lovelace', purchases=[tank_top])
hertzfeld = Customer.create(name='Andy Herzfeld', purchases=[khaki_pants])
engelbart = Customer.create(name='Doug Engelbart', purchases=[khaki_pants, t_shirt])
```

!!! info
    The keyword arguments are exactly the class variables from the page schemas `Item` and `Customer` above.

This is how our two databases `item_db` and `customer_db` look in the Notion UI right now:

![Notion item database](../assets/images/notion-item-db.png){:style="width:800px; display:block; margin-left:auto; margin-right:auto;"}

![Notion customer database](../assets/images/notion-customer-db.png){:style="width:800px; display:block; margin-left:auto; margin-right:auto;"}

!!! note
    The description of the databases corresponds to the docstring of the schema classes `Item` and `Customer`.

## Fast access to page properties

The properties of a page, defined by the properties of the database the page resides in, can be easily accessed using
the `.props` namespace:

```python
assert lovelace.props.name == 'Ada Lovelace'
assert engelbart.props.purchases == [khaki_pants, t_shirt]
```

This is especially useful when using a REPL with autocompletion like [JupyterLab] or [IPython].
As an alternative, bracket notation can also be used. This allows us to use the actual property names
from the schema definition:

```python
assert lovelace.props['Name'] == 'Ada Lovelace'
assert engelbart.props['Items Purchased'] == [khaki_pants, t_shirt]
```

These access methods may also be used to update properties. The following two statements:

```python
khaki_pants.props.size = Size.S
khaki_pants.props['Price'] = 20
```

have the same effects as:

```python
khaki_pants.update_props(size=Size.S, price=20)
```

## Two-way & self relations

Notion also supports two-way relations and so does Ultimate Notion. Taking the same example as before, imagine
that we also wanted to see directly which customers bought a specific item. In this case, the one-way relation `Items Purchased`
from `Customer` needs to become a two-way relation. We can achieve this with a simple modification to both schemas:

```python
class Item(uno.Schema, db_title='Item DB'):
    """Database of all the items we sell"""
    name = uno.PropType.Title('Name')
    size = uno.PropType.Select('Size', options=Size)
    price = uno.PropType.Number('Price', format=uno.NumberFormat.DOLLAR)
    bought_by = uno.PropType.Relation('Bought by')

class Customer(uno.Schema, db_title='Customer DB'):
    """Database of all our beloved customers"""
    name = uno.PropType.Title('Name')
    purchases = uno.PropType.Relation('Items Purchased', schema=Item, two_way_prop=Item.bought_by)
```

What happens here is that we first create a *target* relation property `bought_by` in `Item` by not
specifying any other schema. Then in `Customer`, we define a two-way property by specifying not only
the schema `Item` but also the property we want to synchronize with using the `two_way_prop` keyword.

Let's delete the old databases and recreate them with our updated schemas and a few items:

```python
item_db.delete(), customer_db.delete()

item_db = notion.create_db(parent=root_page, schema=Item)
customer_db = notion.create_db(parent=root_page, schema=Customer)

t_shirt = item_db.create_page(name='T-shirt', size=Size.L, price=17)
lovelace = Customer.create(name='Ada Lovelace', purchases=[t_shirt])
hertzfeld = Customer.create(name='Andy Herzfeld', purchases=[t_shirt])
```

and take a look at the two-way relation within `item_db`:

![Notion customer database with two-way relation](../assets/images/notion-item-db-two-way.png){:style="width:800px; display:block; margin-left:auto; margin-right:auto;"}

Assume now that we want to have a schema that references itself, for instance a simple task list
where certain tasks can be subtasks of others:

```python
class Task(uno.Schema, db_title='Task List'):
    """A really simple task list with subtasks"""
    task = uno.PropType.Title('Task')
    due_by = uno.PropType.Date('Due by')
    parent = uno.PropType.Relation('Parent Task', schema=uno.SelfRef)

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
[bind_db]: ../../reference/ultimate_notion/#ultimate_notion.Schema.bind_db
