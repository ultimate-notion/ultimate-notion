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
exactly — the fixtures look them up by name.

---

## 1. `All Properties DB`

A (full-page) database titled exactly `All Properties DB`. Add one property of every
type. Names, types and configuration must match the table below (extracted from the
recorded cassette `tests/cassettes/fixtures/mod_all_props_db.yaml`).

| Property name | Type | Configuration |
| --- | --- | --- |
| `Title` | Title | — |
| `Text` | Text | — |
| `Number` | Number | Format: **Dollar** |
| `Select` | Select | Options: `Option1` (Default), `Option2` (Red) |
| `Multi-Select` | Multi-select | Options: `MultiOption1` (Purple), `MultiOption2` (Yellow) |
| `Status` | Status | Options: `Not started` (Default), `In progress` (Blue), `Done` (Green) |
| `Date` | Date | — |
| `People` | Person | — |
| `Files` | Files & media | — |
| `Checkbox` | Checkbox | — |
| `URL` | URL | — |
| `Email` | Email | — |
| `Phone number` | Phone | — |
| `Formula` | Formula | Expression: `prop("Number") * 2` |
| `Relation` | Relation | Related to **this same `All Properties DB`**; enable **"Show on both pages"** (two-way). Name the synced property `Relation two-way`. |
| `Relation two-way` | Relation | Created automatically as the synced side of `Relation` above. |
| `Rollup` | Rollup | Relation: `Relation`, Property: `Title`, Calculate: **Count all**. |
| `Created time` | Created time | — |
| `Created by` | Created by | — |
| `Last edited time` | Last edited time | — |
| `Last edited by` | Last edited by | — |
| `ID` | ID (unique ID) | — |
| `Place` | Place | Newer Notion property; add it from the property-type menu. |
| `Button` | Button | **API cannot create.** Add any action (e.g. nothing/no-op is fine). |
| `AI summary` | AI Autofill (Text output) | **API cannot create.** |
| `AI key info` | AI Autofill (Text output) | **API cannot create.** |
| `AI custom` | AI Autofill (Text output) | **API cannot create.** |

Notes:
- **Names are matched exactly (and are case-sensitive).** Notion gives new properties
  default names that differ from the table — e.g. the title is `Name`, and you get
  `Multi-select`, `Person`, `Files & media`, `Phone`, and a relation auto-named
  `Related to All Properties DB`. Rename each to match the table exactly.
- **AI Autofill properties:** add via **+ → AI Autofill → + New AI Autofill** and choose
  **`Text`** as the output type, then name the property (`AI summary` / `AI key info` /
  `AI custom`). The AI prompt itself is irrelevant — the tests only care that the
  property exists and is exposed as text. Requires AI to be enabled for your workspace.

## 2. `Wiki DB`

A wiki can only be created from a **page**, not a database — a database's **•••** menu
has no "Turn into wiki" — and the `Verification` property the tests require is added
only by the wiki conversion. So:

1. Create a normal **page** titled exactly `Wiki DB` under the root page.
2. In the left sidebar, hover that page → **•••** → **Turn into wiki**. This converts it
   to a wiki and automatically adds the **`Owner`** (Person) and **`Verification`**
   properties to its database. (If you don't see "Turn into wiki", the page may need to
   be a top-level/teamspace page — create it there and connect your integration to it.)
3. Open the wiki's database and adjust its properties so it has exactly these five:

   | Property name | Type | Source |
   | --- | --- | --- |
   | `Page` | Title | rename the title property to `Page` |
   | `Owner` | Person | added by the wiki conversion |
   | `Verification` | Verification | added by the wiki conversion |
   | `Tags` | Multi-select — `Onboarding` (Blue), `Design` (Green) | add manually |
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

---

## After building the three objects

These three are only the objects the API **cannot** create. A full live run / cassette
re-record also needs the remaining named objects (`Contacts DB`, `Task DB`, `Formula DB`,
the `Getting Started` / markdown / embed / comment pages, etc.) to exist under the same
root page. Create any missing API-creatable objects with:

```console
NOTION_TOKEN=ntn_... UNO_TEST_ROOT_PAGE='My Test Root' hatch run bootstrap-test-workspace
```

The script is idempotent and leaves existing objects unchanged. Some content-sensitive
tests still require the richer recorded fixture content; the bootstrap creates the
minimum useful structure and seed rows needed to inspect and extend a fresh workspace.

Once every named object exists under your shared root page, re-record with
`hatch run vcr-rewrite`.
