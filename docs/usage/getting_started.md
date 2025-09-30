# Getting started

## Installation

To install Ultimate Notion, simply run:

```console
pip install ultimate-notion
```

or to install all additional dependencies, use:

```console
pip install 'ultimate-notion[all]'
```

Ultimate Notion requires Python 3.10 or higher. Depending on your system, you might need to use [pyenv], [conda], etc. to install a more recent version.

## Creating an integration

1. Open [Notion] and select a workspace
2. Click **⚙ Settings** in the left sidebar
3. In the settings window, click **Connections** (in the *Workspace* section at the bottom)
4. Click **↗ Develop or manage integrations** at the bottom

This takes you to the [My integrations] page. Now:

1. Click **+ New integration**
2. Provide a name and select your workspace
3. Optionally add a [logo]
4. Select **Internal** as the integration type
5. Click **Save**

![Notion integration](../assets/images/notion-integration-create.png){:style="height:600px; display:block; margin-left:auto; margin-right:auto;"}

After creation, you'll see a success popup. Click **Configure integration settings** to access your integration's preferences.

### Configuring your integration

In the *Configuration* tab:

1. Click **Show** next to *Internal Integration Secret*
2. Copy and save the authentication token (starts with `ntn_`)
3. Under *Capabilities*, grant all capabilities for maximum flexibility
4. Click **Save**

![Notion integration](../assets/images/notion-integration-capabilities.png){:style="height:600px; display:block; margin-left:auto; margin-right:auto;"}

This token will be used by Ultimate Notion for authentication and must be provided in the [configuration](configuration.md).

## Granting page access

Your integration needs explicit access to pages. To grant access:

1. Open any page in Notion
2. Click the **⋯** menu in the upper right corner
3. Select **Connections**
4. Search for and select your integration
5. Confirm access

![Notion integration](../assets/images/notion-integration-add.png){:style="width:600px; display:block; margin-left:auto; margin-right:auto;"}

Your integration now has access to this page and all its child pages.

Alternatively, you can manage page access from **⚙ Settings** » **Connections** in your workspace.

## Loading a Notion page

Test your integration with this code. Replace `PAGE_TITLE` with the title of a page you've granted access to:

``` py
--8<-- "examples/getting_started.py"
```

Run the code to see the rendered output. In JupyterLab, you'll see formatted Markdown; in a terminal, you'll see plain text.

![Getting started page](../assets/images/notion-getting-started-page.png){style="width:600px; display:block; margin-left:auto; margin-right:auto;"}

## Understanding Notion concepts

### Pages and blocks

In Notion, everything is either a **page** or a **block**. A page contains blocks like headings, text, lists, tables, and quotes.

### Databases

A **database** is a special block type that can exist:

- Within a page (inline database)
- At the same level as pages (full-page database)

Each database has a **schema** with **properties** (columns) of specific types (text, number, URL, etc.).
Pages within a database inherit these properties as structured data.

**Note**: Linked databases (marked with ↗) aren't accessible via the API—always work with the source database.

### Page hierarchy and permissions

Pages can contain other pages, creating a hierarchy:

- **Parent page**: Contains other pages
- **Child pages**: Contained within another page
- **Root pages**: Directly in the workspace

Integration permissions inherit from parent pages, so granting access to a parent automatically includes all children.

### Identifiers

Notion assigns a **UUID** (32-character identifier) to every page, block, user, and property. These UUIDs remain
constant even when titles change.

You can find page/database UUIDs by:

1. Using **Copy link** from the **···** menu
2. Extracting from the URL: `https://www.notion.so/{TITLE}-{UUID}`

### Text handling

Notion treats empty strings and unset values equivalently. Ultimate Notion returns `None` for empty strings to
maintain consistency, but displays them as `""` when converting objects to strings.

[Notion]: https://www.notion.so
[My integrations]: https://www.notion.so/my-integrations
[logo]: ../assets/images/logo_integration.png
[pyenv]: https://github.com/pyenv/pyenv
[conda]: https://docs.conda.io/
