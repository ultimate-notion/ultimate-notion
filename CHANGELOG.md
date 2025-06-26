# Changelog

## Version 0.9

- New: Allow updating if a database is inline or not
- Chg: `create_db` has a `title` parameter to set a title if no schema is used or needs to be overwritten.

## Version 0.8, 2025-06-23

- New: Added support for creating inline databases by Tzumx
- Chg: Have a proper hierarchy of Ultimate Notion exception classes.
- New: The schema of a database provides a `to_pydantic_model` class for evaluating input.
- New: More schema validations like checking for a title property and distinct property names.
- Fix: Fix error when setting a (multi-)select option with no color specified.
- New: Added a button property value.
- New: Added support for [Polars], i.e. `to_polars` method of database views.
- New: Add support for custom emoji icons
- Chg: Return `None` instead of an empty string `""` when a text property or block is unset.
- New: Setting the width ratios of page columns is supported.
- Fix: Adding a column with `add_column(index)` at a given index is no longer off by 1.
- Add: Updating a database schema, i.e. adding/removing properties or changing their types
- Add: Changing database properties, e.g. name, formula of formula property, options, etc.
- Add: Added the `display_name` field of comments

## Version 0.7.1, 2025-01-05

- Fix: Added missing tomli dependency, issue #62.
- Fix: Support button property of databases to fix error when retrieving a page or database, issue #63.

## Version 0.7, 2024-12-10

- New: Reading and inserting comments is implemented.
- Chg: `SList` is part of the public API now, i.e. is in the `ultimate_notion` namespace.
- Fix: Added missing `link_to_page` subtype `comment_id`.
- Chg: Remove `Text` as direct import, use `text` instead.
- Chg: `.props` namespace of a page now behaves like a mapping, i.e. read-only dictionary.
- Fix: Added missing `.value` function of several `PropertyValue`s.
- Add: Page method `get_property` to allow fetching a single property without reloading the whole page.
- Fix: Resolving page properties correctly if they contain more than 25 references.
- Fix: `PropertiesEndpoint.retrieve` now actually works and either returns a single property item or a list.
- Chg: Renamed `db.fetch_all()` to `db.get_all_pages()`.
- New: Query databases with a PySpark/Polars inspired DSL, e.g. `uno.prop('Name') == 'Linus Torvalds'`, implemented.
- Fix: Database pages created with `db.create_page` are now added to the session cache.
- New: Easily activate a debug mode within the config file.
- Fix: Rollup property defined on a self-referencing relation works now.
- Doc: Added a page about querying a database.
- Chg: Renamed property types `People` to `Person` and `PhoneNumber` to `Phone`.

## Version 0.6, 2024-09-28

- New: Also use the session cache for blocks.
- New: Properties of blocks can be updated.
- Fix: `has_children` doesn't return a wrong value anymore for pages and databases.
- Fix: Several issues with blocks and duplicated but ID-equivalent objects.
- Chg: Simplified dealing with rich texts by introducing `text`, `mention` and `math`.
- Chg: Children of pages are proper pages/databases instead of `ChildPage`/`ChildDatabase`.
- Chg: Renamed `PageSchema` to `Schema`.
- Chg: Accessing the properties of a page directly returns the primitive data types.
- Chg: Completely reworked the functionality of the `Table` block for more consistency and easier usage.

## Version 0.5.1, 2024-08-09

- Fix: Added type `unknown` in user data to generate `UnknownUser`, issue #39.

## Version 0.5, 2024-08-07

- New: Method `page.append` to append content to a page. Creation of blocks is supported!
- New: Documentation on how to create the content of a page.
- New: More robustness with respect to Notion API changes.
- New: High-level method `session.get_block` to retrieve a single block.
- Chg: Internally, `archived` property was renamed to `in_trash`.
- Chg: Renamed `.content` to `.children` of a page for more consitency.
- Chg: Use `Property` again to consistently refer to the columns of a database.
- Chg: Make use of [pendulum](https://pendulum.eustace.io/) to represent `DateRange` values.
- Chg: Renamed `page.database` to `page.parent_db` and `page.in_db` added as methods.
- Chg: Large restructering of the code base.
- Chg: Return `None` for various string attributes/properties if no string is set for consistency.

## Version 0.4, 2024-02-14

- New: Introduced a configuration file under `~/.ultimate-notion/config.toml`.
- New: Added a simple Google Tasks client.
- New: Added a general sychronization task for Notion to other services.
- New: Added a specific Google Tasks synchronization task.
- Fix: A page property can be deleted by setting it to `None`.
- Chg: Reworked the testing setup to use VCR.py more efficiently and be more robust.
- Fix: Tons of fixes within blocks and general page content.
- Chg: `to_markdown()` now uses an internal implementation instead of `notion2md`.

## Version 0.3, 2023-12-26

- Chg: `RichText` is now a subtype of `str` for a more convenient & consistent usage.
- Doc: Added more documentation about using databases.
- Chg: `icon` attribute of database now returns `Emoji` instead of `str`.
- New: Allow setting the `icon` and `cover` attribute of a page.
- New: Allow setting the `title` of a non-database page.
- Fix: `created_by` and `last_edited_by` return proper `User` object.

## Version 0.2, 2023-12-19

- Fix: Notion API's undocumented `description` of `SelectOption` added.
- New: Navigate pages using `parent` and `children`.
- Chg: Rename `parents` to `ancestors`.
- Fix: Wrong return value of PropertyType `Status.value`.
- Chg: Make `show` consistent for Page, View, PageSchema.
- Ref: Refactor `value` in `PropertyValue`.
- Ref: Reduce unnecessary funtionality of `Number`, use `value` instead.

## Version 0.1, 2023-12-16

- First official alpha release.

[Polars]: https://pola.rs/
