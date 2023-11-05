# Features

Some of the feature listed here, loosely correspond to the features of the endpoints defined in the [Notion API].
Please note that a slightly different terminology is used. Since the term *properties* is highly
overloaded, we call the properties of a database *schema* and refer to the individual properties as
*columns*. With *page properties*, we denote only the properties of a page within a database that correspond
to the columns of the schema. In contrast to that, the properties that every page has, e.g. title,
icon, last edited by/time, etc., are called *page attributes*.

## Databases

- [x] retrieve a database by ID
- [x] search for a database by its title
- [x] create a new database with a given schema, i.e. columns and their types
- [x] delete/archive and restore/unarchive a database
- [ ] update a database schema, i.e. adding/removing columns or changing their types
- [ ] change the properties of database columns, e.g. name, formula of formula column, etc.
- [x] read the database attributes like title, icon, etc.
- [ ] change database attributes like title, icon, etc.
- [x] retrieve all containing pages of a database
- [ ] query with filters and sortings to retrieve only specific pages
- [ ] display the content of a database as a table, e.g. in [Jupyter Lab]
- [x] create new pages with properties within the database respecting the schema

## Pages

- [x] retrieve a page by ID
- [x] search for a page by its title
- [x] create a new page
- [x] delete/archive and restore/unarchive a page
- [ ] read page attributes like title, icon, etc.
- [ ] change page attributes like title, icon, etc.
- [ ] read page properties defined by a database schema
- [ ] change page properties
- [ ] navigate  pages using references of parent and children
- [ ] read the blocks within a page
- [ ] add/remove and modify the blocks within a page
- [ ] view the content of a page as [Markdown]

## Blocks

- [ ] retrieve a block by ID
- [ ] navigate blocks using references of parent and children
- [ ] create blocks within a page or another block
- [ ] modify blocks

## Users

- [x] retrieve a user by ID
- [x] retrieve own bot user, i.e. self-identify
- [x] retrieve all users
- [x] read the attributes of a user

## Comments

- [ ] create a comment within a block or page
- [ ] retrieve comments of a block or page
