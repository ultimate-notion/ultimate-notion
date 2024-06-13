# Changelog

## Version 0.5

- New: More robust with respect to Notion API changes.
- Chg: Internally, `archived` property was renamed to `in_trash`.
- Chg: Renamed `.content` to `.children` of a page for more consitency.
- Chg: Use Property again to consistently refer to the columns of a database.
- Chg: Make use of [pendulum](https://pendulum.eustace.io/) to represent `DateRange` values.

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

- Chg: `RichText` is now a subtype of `str` for more convenient & consistent usage.
- Docs: Added more documentation about using databases.
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
