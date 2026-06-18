# Building the manual test objects

Most of the objects the live tests expect can be created with the Notion API and
will eventually be produced by a bootstrap script. **Three of them cannot be created
through the API at all** and must be built by hand in the Notion UI, because they use
features Notion does not expose in its public API:

| Object | Why it must be built by hand |
| --- | --- |
| `All Properties DB` | Contains **AI Autofill** properties and a **Button** property, neither of which the API can create. |
| `Wiki DB` | Is a database that has been **turned into a wiki**, which adds a `Verification` property; the API cannot create wikis. |
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
| `AI summary` | AI Autofill → **AI summary** | **API cannot create.** Appears as text via the API. |
| `AI key info` | AI Autofill → **Key info** | **API cannot create.** |
| `AI custom` | AI Autofill → **Custom autofill** | **API cannot create.** |

Notes:
- The AI Autofill properties are under **+ → AI Autofill** when adding a property.
  They require AI to be enabled for your workspace.
- If your Notion plan does not offer a given AI option, create the closest available
  AI Autofill property and keep the name (`AI summary` / `AI key info` / `AI custom`);
  the tests treat them as text.

## 2. `Wiki DB`

1. Create a full-page database titled exactly `Wiki DB` with these properties:

   | Property name | Type | Configuration |
   | --- | --- | --- |
   | `Page` | Title | — |
   | `Owner` | Person | — |
   | `Tags` | Multi-select | Options: `Onboarding` (Blue), `Design` (Green) |
   | `Last edited time` | Last edited time | — |

2. Turn it into a wiki: open the database's **•••** menu → **Turn into wiki**.
   This automatically adds the **`Verification`** property the tests expect; you do
   not add it manually.

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

The remaining named objects (`Contacts DB`, `Task DB`, `Formula DB`, the markdown
pages, etc.) can be created with the API. Once the three manual objects above exist
under your shared root page, the suite has everything it needs and the cassettes can
be re-recorded with `hatch run vcr-rewrite`.
