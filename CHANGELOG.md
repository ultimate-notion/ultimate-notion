# Changelog

## Version 0.3

- Chg: `RichText` is now a subtype of `str` for more convenient & consistent usage.
- Docs: Added more documentation about using databases.
- Chg: `icon` attribute of database now returns `Emoji` instead of `str`.
- New: Allow setting the `icon` and `cover` attribute of a page.
- New: Allow setting the `title` of a non-database page.

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
