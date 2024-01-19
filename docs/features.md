# Features

Some of the feature listed here, loosely correspond to the features of the endpoints defined in the [Notion API].
Please note that a slightly different terminology is used. Since the term *properties* is highly
overloaded, we call the properties of a database *schema* and refer to the individual properties as
*columns*. With *page properties*, we denote only the properties of a page within a database that correspond
to the columns of the schema. In contrast to that, the properties that every page has, e.g. title,
icon, last edited by/time, etc., are called *page attributes*.

## Databases

- [x] retrieve a database by its ID
- [x] search for a database by its title
- [x] create a new database with a given schema, i.e. columns and their types
- [x] delete/archive and restore/unarchive a database
- [ ] update a database schema, i.e. adding/removing columns or changing their types
- [ ] change the properties of database columns, e.g. name, formula of formula column, options, etc.
- [x] read the database attributes like title, description, cover, icon, etc.
- [x] change database attributes like title, description, etc.
- [x] retrieve all pages of a database
- [ ] query with filters and sortings to retrieve only specific pages
- [x] display the content of a database as a table, e.g. in [Jupyter Lab]
- [x] create new pages with properties within the database respecting the schema

## Pages

- [x] retrieve a page by its ID
- [x] search for a page by its title
- [x] create a new page
- [x] delete/archive and restore/unarchive a page
- [x] read page attributes like title, cover, icon, etc.
- [x] change page attributes like title, cover, icon, etc.
- [x] read page properties defined by a database schema
- [x] change page properties
- [x] navigate pages using parent and children links
- [ ] read the blocks within a page
- [ ] add/remove and modify the blocks within a page
- [x] view the content of a page as [Markdown]

## Blocks

- [ ] navigate blocks using references of parent and children
- [ ] create blocks within a page or another block
- [ ] modify blocks

## Users

- [x] retrieve a user by their ID
- [x] retrieve own bot user, i.e. self-identify
- [x] retrieve all users
- [x] read the attributes of a user

## Comments

- [ ] create a comment within a block or page
- [ ] retrieve comments of a block or page

## Miscellaneous

- [x] general synchronization capabilities with external services
- [x] client for [Google Tasks API] and synchronization adapter

## Notion API Limitations

Some features that the Notion UI provides are not possible to implement due to limitations of the API itself.

- creating a [Status] column or updating the options as well as option groups. Sending an Status column within a create
  database call is currently accepted but just ignored, i.e. a database without the column will show up.
- creating a [Unique ID] column or updating its properties like the prefix. This column type is not even mentioned
  as one of the [database properties].
- creating a [Wiki database] which has a special [Verification] column.
- [updating the database schema] with respect to the options of a select/multi-select column, the formula of a
  formula column, and synced content.
- referencing in a formula expression another formula column, e.g. `prop("other formula")`. Use substitution instead.
- creating a two-way relation with the same source and target database, i.e. self-referencing. The update database call
  is currently accepted but only a one-way relation created, which seems to be a bug.
- uploading files as icons or in general uploading files.
- setting the icon and cover of a database.

If you think those limitations should be fixed, [let the developers of Notion know](mailto:developers@makenotion.com) 😆

[Status]: https://developers.notion.com/reference/property-object#status
[Unique ID]: https://developers.notion.com/reference/page-property-values#unique-id
[database properties]: https://developers.notion.com/reference/property-object
[Verification]: https://developers.notion.com/reference/page-property-values#verification
[Wiki database]: https://developers.notion.com/docs/working-with-databases#wiki-databases
[updating the database schema]: https://developers.notion.com/reference/update-a-database#errors
[Google Tasks API]: https://developers.google.com/tasks/overview
