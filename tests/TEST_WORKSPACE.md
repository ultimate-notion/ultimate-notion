# Building the manual test objects

Most of the objects the live tests expect can be created with the Notion API and
are produced by the workspace bootstrap script. **Three of them cannot be created
through the API at all** and must be built by hand in the Notion UI, because they use
features Notion does not expose in its public API:

| Object | Why it must be built by hand |
| --- | --- |
| `All Properties DB` | Contains **AI Autofill** properties and a **Button** property, neither of which the API can create. |
| `Wiki DB` | Is an ordinary page that has been **turned into a wiki**; the API cannot perform that conversion. |
| `Custom Emoji Page` | Its icon is a **custom (uploaded) emoji**; the API can reference custom emoji but cannot upload them. |

Create all three **inside the root page** you shared with your integration (see the
"Set up a Notion test workspace" section in `CONTRIBUTING.md`). Titles must match
exactly, because the fixtures look them up by name.

A fourth object, `Formula DB`, is created by the bootstrap script but needs a manual
follow-up: Notion cannot filter on formula columns created through the API, so its
formula columns must be (re)created in the Notion UI. See [§4](#4-formula-db) below.

---

## 1. `All Properties DB`

A (full-page) database titled exactly `All Properties DB`. Add one property of every
type. Names, types and configuration must match the table below (extracted from the
recorded cassette `tests/cassettes/fixtures/mod_all_props_db.yaml`).

| Property name | Type | Configuration |
| --- | --- | --- |
| `Title` | Title | N/A |
| `Text` | Text | N/A |
| `Number` | Number | Format: **Dollar** |
| `Select` | Select | Options: `Option1` (Default), `Option2` (Red) |
| `Multi-Select` | Multi-select | Options: `MultiOption1` (Purple), `MultiOption2` (Yellow) |
| `Status` | Status | Options: `Not started` (Default), `In progress` (Blue), `Done` (Green) |
| `Date` | Date | N/A |
| `People` | Person | N/A |
| `Files` | Files & media | N/A |
| `Checkbox` | Checkbox | N/A |
| `URL` | URL | N/A |
| `Email` | Email | N/A |
| `Phone number` | Phone | N/A |
| `Formula` | Formula | Expression: `prop("Number") * 2` |
| `Relation` | Relation | Related to **this same `All Properties DB`**; enable **"Show on both pages"** (two-way). Name the synced property `Relation two-way`. |
| `Relation two-way` | Relation | Created automatically as the synced side of `Relation` above. |
| `Rollup` | Rollup | Relation: `Relation`, Property: `Title`, Calculate: **Count all**. |
| `Created time` | Created time | N/A |
| `Created by` | Created by | N/A |
| `Last edited time` | Last edited time | N/A |
| `Last edited by` | Last edited by | N/A |
| `ID` | ID (unique ID) | N/A |
| `Place` | Place | Newer Notion property; add it from the property-type menu. |
| `Button` | Button | **API cannot create.** Add any action (e.g. nothing/no-op is fine). |
| `AI summary` | AI Autofill (Text output) | **API cannot create.** |
| `AI key info` | AI Autofill (Text output) | **API cannot create.** |
| `AI custom` | AI Autofill (Text output) | **API cannot create.** |

Notes:
- **Names are matched exactly (and are case-sensitive).** Notion gives new properties
  default names that differ from the table. For example, the title is `Name`, and you get
  `Multi-select`, `Person`, `Files & media`, `Phone`, and a relation auto-named
  `Related to All Properties DB`. Rename each to match the table exactly.
- **AI Autofill properties:** add via **+ → AI Autofill → + New AI Autofill** and choose
  **`Text`** as the output type, then name the property (`AI summary` / `AI key info` /
  `AI custom`). The AI prompt itself is irrelevant; the tests only care that the
  property exists and is exposed as text. Requires AI to be enabled for your workspace.

## 2. `Wiki DB`

A wiki can only be created from a **page**, not a database. A database's **•••** menu
has no "Turn into wiki", and the `Verification` property the tests require is added
only by the wiki conversion. So:

1. Create a normal **page** titled exactly `Wiki DB` under the root page.
2. In the left sidebar, hover that page → **•••** → **Turn into wiki**. This converts it
   to a wiki and automatically adds the **`Owner`** (Person) and **`Verification`**
   properties to its database. (If you don't see "Turn into wiki", the page may need to
   be a top-level/teamspace page. Create it there and connect your integration to it.)
3. Open the wiki's database and adjust its properties so it has exactly these five:

   | Property name | Type | Source |
   | --- | --- | --- |
   | `Page` | Title | rename the title property to `Page` |
   | `Owner` | Person | added by the wiki conversion |
   | `Verification` | Verification | added by the wiki conversion |
   | `Tags` | Multi-select: `Onboarding` (Blue), `Design` (Green) | add manually |
   | `Last edited time` | Last edited time | add manually |

## 3. `Custom Emoji Page`

1. **Upload the custom emoji.** Go to **Settings → Emoji** (workspace emoji) and
   upload an image named exactly **`ultimate-notion`** so it is usable as
   `:ultimate-notion:`. (Any image works; the project logo at
   `docs/assets/images/favicon.png` is a natural choice.)
2. **Create the page** titled exactly `Custom Emoji Page` under the root page.
3. **Set the page icon** to the `ultimate-notion` custom emoji (page icon → Custom
   tab → pick `ultimate-notion`).
4. **Add the content** so the page renders to exactly this markdown:

   ```markdown
   This page has a custom emoji :ultimate-notion: compared to 🚀.
   💡 Callout block without an emoji
   ```

   Concretely:
   - A **paragraph**: `This page has a custom emoji ` then the inline custom emoji
     `:ultimate-notion:` (type `:ultimate-notion:` and pick it) then ` compared to `
     then the standard rocket emoji `🚀` then `.`
   - A **callout block** with the text `Callout block without an emoji` and its
     **default 💡 icon** (do not change the callout icon).

## 4. `Formula DB`

The bootstrap script creates `Formula DB`, its `Name` / `Tags` / `Date Source` columns,
the four formula columns and two seed rows. But **Notion rejects query filters on any
formula property created through the public API**, returning
`400 "Unable to filter based on a formula of unknown type"` — reproduced across every
API version (`2022-06-28` … `2026-03-11`) and both the `databases` and `data_sources`
query endpoints, even for a constant formula. An API-created formula carries no
filterable result type in its schema (see issue #297). So `test_query_formula` cannot
record until the formula columns are recreated in the UI:

1. Open `Formula DB` and delete the four formula columns (`String`, `Number`,
   `Checkbox`, `Date`).
2. Re-add them in the UI with the same names, types and expressions:

   | Property name | Type | Expression |
   | --- | --- | --- |
   | `String` | Formula | `format(prop("Name"))` |
   | `Number` | Formula | `prop("Tags").length()` |
   | `Checkbox` | Formula | `prop("Tags").includes("Done")` |
   | `Date` | Formula | `prop("Date Source")` |

The bootstrap script verifies this automatically: after seeding it runs a formula filter
and prints either `Formula DB: formula filters OK` or `Formula DB: manual setup
required …`. A green line confirms the manual step worked.

---

## After building the three objects

These three are only the objects the API **cannot** create. A full live run / cassette
re-record also needs the remaining named objects (`Contacts DB`, `Task DB`, `Formula DB`,
the `Getting Started` / markdown / embed / comment pages, etc.) to exist under the same
root page. Create any missing API-creatable objects with:

```console
NOTION_TOKEN=ntn_... UNO_TEST_ROOT_PAGE='My Test Root' hatch run bootstrap-test-workspace
```

The script is idempotent and leaves existing objects unchanged. It also builds the
intricately-styled rich text on the `Markdown Text Test` page that
`tests/test_markdown.py::test_rich_text_md` expects (nested bold/italic/strikethrough/
underline, inline code and equations, a person and a self page-mention, mid-word links).
This rich text *is* reproducible through the API, so it is no longer a manual step. A few
content-sensitive tests still require manual workspace content the API cannot create —
notably the `Comments` page's **inline discussions** (the API cannot start an inline
discussion) and the `Formula DB` formula columns (§4).

After creating objects, the script runs an **audit**: it lists every page and database
the integration can see, reports any **missing** expected object, and lists **stray**
objects that are not part of the expected set (`EXPECTED_PAGE_TITLES` /
`EXPECTED_DATABASE_TITLES` in `scripts/bootstrap_test_workspace.py`, kept in sync with
the title constants in `tests/conftest.py`). Stray records — trashed, orphaned or
limited-access leftovers, including property-less objects — are what silently break
`search_page()`/`search_db()` (issue #273), so a clean audit means a search returns a
known, stable result set. The audit is **report-only** by default; pass `--prune` to
move accessible stray pages to trash:

```console
NOTION_TOKEN=ntn_... hatch run bootstrap-test-workspace --prune
```

Once every named object exists under your shared root page, re-record with
`hatch run vcr-rewrite`.

## Replay-only cassettes (not re-recorded)

A few cassettes are **hand-crafted** to a fixed shape that a live workspace cannot
reproduce, so they must survive a re-record untouched. These tests carry the
`@pytest.mark.replay_only` marker, and `pytest_collection_modifyitems` skips them whenever
`--record-mode=rewrite` is in effect — so `hatch run vcr-rewrite` leaves their committed
cassettes in place. They still run (and must pass) under `hatch run vcr-only`.

| Test | Why it is replay-only |
| --- | --- |
| `test_session.py::test_search_page_with_property_less_results` | The cassette mixes regular pages with stripped-down, property-less `search` records to a fixed result set (4 pages, 2 property-less) for issue #273; a live workspace has many more pages. See issue #374. |

If you craft another replay-only cassette, add `@pytest.mark.replay_only` to its test and a
row here so the next re-record preserves it.
