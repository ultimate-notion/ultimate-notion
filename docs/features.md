# Features

Some of the feature listed here, loosely correspond to the features of the endpoints defined in the [Notion API].
Please note that a slightly different terminology is used. Since the term *properties* is highly
overloaded, we call the properties of a database *schema* and refer to the individual properties as
*columns*. With *page properties*, we denote only the properties of a page within a database that correspond
to the columns of the schema. In contrast to that, the properties that every page has, e.g. title,
icon, last edited by/time, etc., are called *page attributes*.

## Databases

- [x] retrieving a database using its ID
- [x] searching for a database using its title
- [x] creating a new database with a given schema, i.e. columns and their types
- [x] deleting/archiving a database
- [ ] updating a database schema, i.e. adding/removing columns or changing their types
- [ ] changing the properties of database columns, e.g. name, formula of formula column, etc.
- [x] reading the database attributes like title, icon, etc.
- [ ] changing database attributes like title, icon, etc.
- [x] retrieving all containing pages of a database
- [ ] querying with filters and sortings to retrieve only specific pages
- [ ] displaying the content of a database as a table, e.g. in [Jupyter Lab]
- [x] creating new pages with properties within the database respecting the schema

## Pages

- [x] retrieving a page using its ID
- [ ] searching for a page using its title
- [ ] creating a new page by specifying its parent
- [x] deleting/archiving a page
- [ ] reading page attributes like title, icon, etc.
- [ ] changing page attributes like title, icon, etc.
- [ ] reading page properties defined by a database schema
- [ ] changing page properties
- [ ] navigating  pages using references of parent and children
- [ ] reading the blocks within a page
- [ ] adding/removing and modifying the blocks within a page
- [ ] viewing the page content as [Markdown]

## Blocks

- [ ] retrieving a block using its ID
- [ ] navigating blocks using references of parent and children
- [ ] creating blocks within a page or another block
- [ ] modifying blocks

## Users

- [x] retrieving a user using its ID
- [x] retrieve own bot user, i.e. self-identify
- [x] retrieving all users
- [x] read the attributes of a user

## Comments

- [ ] creating a comment by specifying its parent page
- [ ] retrieving comments of a block or page
