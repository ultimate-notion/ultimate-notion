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

Finally, three **content pages** are created as shells by the bootstrap script but must
have their content finished by hand, because each needs a block the API cannot create:

| Page | Manual content needed |
| --- | --- |
| `Markdown Test` | Ends with two **unsupported blocks** (a Button and an AI block) the API cannot create. See [§5](#5-markdown-test-page). |
| `Embed/Inline/Linked & Unfurl` | Must end with a real **linked-database view**, which the API cannot create. See [§6](#6-embed-page-linked-database). |
| `Comments` | Needs an **inline comment** on its heading; the API cannot *start* inline discussions. See [§7](#7-comments-page-inline-comment). |

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

## 5. `Markdown Test` page

The bootstrap creates this page with a single `Headline 1` block as a shell. It is a
content fixture for `tests/test_page.py::test_page_to_markdown`, which asserts the page
renders to **exactly** the markdown in that test's `exp_output` (compared line-by-line
with `strict=True`). The expected markdown is the spec — build the page so its blocks
render to it, in order. Most blocks are ordinary (headings, a divider, **toggle**
headings, bulleted / to-do / numbered lists, a quote, a 💡 callout, a 3×2 table, a
paragraph, a block equation, a python code block, an image with a caption, a second
image, a file, an audio embed, a heading, a two-column block, a table of contents, a
breadcrumb, a child subpage `Markdown SubPage Test`, a synced block and a link to the
subpage).

The page **cannot be finished through the API**, because its last two blocks render as
`<kbd>Unsupported block</kbd>`:

1. Add a **Button** block (`/button`) near the end.
2. Add an **AI block** (e.g. `/ai` summary) as the final block.

Both are returned by the API as `Unsupported` blocks but cannot be *created* by it (see
`ultimate_notion.blocks.Unsupported`), so they must be added in the UI. The exact text
of the other blocks is given verbatim by `exp_output`; match it line for line.

## 6. `Embed/Inline/Linked & Unfurl` page

The bootstrap creates this page with an embed, a bookmark and an inline-link paragraph.
`test_embed_blocks` additionally requires the **last** block to be a real **linked
database** view (it asserts the final rendered line is
`<kbd>↗️ Linked database (unsupported)</kbd>`). The API cannot create a linked-database
view, so add one by hand at the end of the page: type `/linked`, choose **Create linked
database**, and point it at any existing database (e.g. `Task DB`).

## 7. `Comments` page inline comment

The bootstrap creates this page with a single `Comments` heading. The doc snippet test
`tests/test_docs_py_snippets.py::test_page_advanced` reads an **inline discussion** on
that heading (`page.children[0].discussions[0]`). The Notion API can append to an
existing discussion and start *page* discussions, but it cannot **start an inline
discussion**, so this must be done in the UI: open the `Comments` page, hover the
`Comments` heading, and add an inline comment (any text).

---

## After building the manual objects

The sections above cover the parts the API **cannot** create: the three fully-manual
objects (§1–§3), the `Formula DB` formula columns (§4) and the manual content on the
`Markdown Test` / embed / `Comments` pages (§5–§7). A full live run / cassette re-record
also needs the remaining API-creatable objects (`Contacts DB`, `Task DB`, `Formula DB`,
the `Getting Started` / markdown / embed / comment page shells, etc.) to exist under the
same root page. Create any missing API-creatable objects with:

```console
NOTION_TOKEN=ntn_... UNO_TEST_ROOT_PAGE='My Test Root' hatch run bootstrap-test-workspace
```

The script is idempotent and leaves existing objects unchanged. Some content-sensitive
tests still require the richer recorded fixture content; the bootstrap creates the
minimum useful structure and seed rows needed to inspect and extend a fresh workspace.

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
