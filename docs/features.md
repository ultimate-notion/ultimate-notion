# Features

Some of the features listed here loosely correspond to the features of the endpoints defined in the [Notion API].
Please note that slightly different terminology is used. Since the term *properties* is highly
overloaded, we call the properties of a database as a whole *schema* and refer to the individual
properties as *database properties* or sometimes *columns* in the context of a table or view.
With *page properties*, we denote only the properties of a page within a database that correspond
to the properties of the database schema. In contrast to that, the properties that every page has, e.g., title,
icon, last edited by/time, etc., are called *page attributes*.

## General

- [x] high-level and Pythonic interface for the Notion API
- [x] caching to avoid unnecessary calls to the Notion API
- [ ] 100% feature parity with the [official Notion API]

## Databases

- [x] retrieve a database by its ID
- [x] search for a database by its title
- [x] create a new database with a given schema, i.e., properties and their types
- [x] delete and restore a database
- [x] update a database schema, i.e., adding/removing properties or changing their types
- [x] change database properties, e.g., name, formula of formula property, options, etc.
- [x] read the database attributes like title, description, cover, icon, etc.
- [x] change database attributes like title, description, etc.
- [x] retrieve all pages of a database
- [x] query with filters and sorting to retrieve only specific pages
- [x] display the content of a database as a table, e.g., in [JupyterLab]
- [x] export to [Polars], [Pandas], [Markdown], HTML, etc.
- [x] create new pages with properties within the database respecting the schema

## Pages

- [x] retrieve a page by its ID
- [x] search for a page by its title
- [x] create a new page
- [x] delete and restore a page
- [x] read page attributes like title, cover, icon, etc.
- [x] change page attributes like title, cover, icon, etc.
- [x] read page properties defined by a database schema
- [x] change page properties
- [x] navigate pages using parent and children links
- [x] retrieve the blocks within a page
- [x] add or remove blocks within a page
- [x] view the content of a page as [Markdown]

## Blocks

- [x] create a new block and append it to a page or a parent block
- [x] delete a block
- [x] change the content of a block
- [x] navigate blocks using references of parent and children

## Files

- [ ] upload files to Notion

## Users

- [x] retrieve all users
- [x] retrieve a user by their ID
- [x] retrieve own bot user, i.e., self-identify

## Comments

- [x] create a comment in a page or existing discussion thread
- [x] retrieve unresolved comments from a page or block

## Adapters

- [x] general synchronization capabilities with external services
- [x] client for [Google Tasks API] and synchronization adapter to sync Google Tasks with a Notion database
- [ ] synchronization adapter for [Google Sheets API] to sync Google Sheets with a Notion database

## Notion API Limitations

Some features that the Notion UI provides are impossible to implement due to limitations of the Notion API itself.
These limitations include:

- creating a [Status] property or updating the options as well as option groups. Sending a Status property within a
  create database call is currently accepted but just ignored, i.e., a database without the property will show up.
- creating a [Unique ID] property or updating its properties like the prefix. This property type is not even mentioned
  as one of the [database properties].
- creating a [Wiki database], which has a special [Verification] property.
- [updating the database schema] with respect to the options of a select/multi-select property, the formula of a
  formula property, and synced content.
- referencing in a formula expression another formula property, e.g., `prop("other formula")`. Use a substitution instead.
- creating a two-way relation with the same source and target database, i.e., self-referencing. The update database call
  is currently accepted but only a one-way relation is created, which seems to be a bug within the Notion API itself.
- setting the icon and cover of a database.
- moving pages since a [page’s parent cannot be changed].
- setting a [reminder] based on date and/or time.
- modifying the URL of file-like blocks, e.g., `File`, `Image`, etc.
- creating inline comments to start a new discussion thread.
- resolving comments or listing unresolved comments.
- locking or unlocking a page or database.
- working with database button properties.
- retrieving a list of all custom emojis defined in the workspace.
- changing the description of a database property.

If you think those limitations should be fixed, [let the developers of Notion know](mailto:developers@makenotion.com) 😆

[Status]: https://developers.notion.com/reference/property-object#status
[Unique ID]: https://developers.notion.com/reference/page-property-values#unique-id
[database properties]: https://developers.notion.com/reference/property-object
[Verification]: https://developers.notion.com/reference/page-property-values#verification
[Wiki database]: https://developers.notion.com/docs/working-with-databases#wiki-databases
[updating the database schema]: https://developers.notion.com/reference/update-a-database#errors
[Google Tasks API]: https://developers.google.com/tasks/overview
[Google Sheets API]: https://developers.google.com/sheets
[page’s parent cannot be changed]: https://developers.notion.com/reference/patch-page
[reminder]: https://www.notion.com/help/reminders
[official Notion API]: https://developers.notion.com/reference/
