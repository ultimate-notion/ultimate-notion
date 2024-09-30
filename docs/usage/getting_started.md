# Getting started

## Installation

To install Ultimate Notion simple run:

```console
pip install ultimate-notion
```

or to install all additional dependencies, use:

```console
pip install 'ultimate-notion[all]'
```

Ultimate Notion needs at least Pyton 3.10. Depending on your system, you might need to use [pyenv], [conda], etc. to
install a more recent version.

## Creating an integration

Now open the web interface of [Notion], select a workspace, click <kbd>Settings</kbd> to open the account setting
window, click <kbd>Connections</kbd> and choose <kbd>Develop or manage integrations</kbd>. This should take you to
the [My integrations] site. Now select <kbd>+ Create new integration</kbd>, provide a name, a [logo] and select the
Notion workspace the integration should be associated to. After that click the <kbd>Submit</kbd> button.

![Notion integration](../assets/images/notion-integration-create.png){: style="height:600px; display:block; margin-left:auto; margin-right:auto;"}

This brings you to the Secrets-site where you need to copy and save the *Internal Integration Token*, which always starts
with `ntn_` or `secret_` when created before September 25, 2024. This token will be used by Ultimate Notion for authentication.

## Granting access to an integration

Open Notion, i.e. the web interface or your Notion app. Make sure the integration you created shows up under
<kbd>Settings & members</kbd> » <kbd>Connections</kbd>. Now select any page you want to access via Ultimate Notion and
select the <kbd>···</kbd> on the upper right. In the drop-down menu, scroll down, select <kbd>+ Add connections</kbd>,
search and select your created integration. A pop-up that you need to confirm will inform you that your integration
will have access to the selected page as well as all its children.

![Notion integration](../assets/images/notion-integration-add.png){: style="width:600px; display:block; margin-left:auto; margin-right:auto;"}

## Ultimate Notion configuration

Ultimate Notion looks up the environment variable `ULTIMATE_NOTION_CONFIG` for a configuration [TOML]-file.
If this variable is not set, it defaults to `~/.ultimate-notion/config.toml` under MacOS/Linux and
`$HOME/.ultimate-notion/config.toml` under Windows systems. If no configuration file is found, a default one is created
automatically that will set the Notion token to be looked up using the environment variable `NOTION_TOKEN`.
Alternatively, you can set the your token directly in the configuration file.

## Loading a Notion page

To try out if your integration works, just copy&paste the following code into your favorite editor or better [JupyterLab].
Replace the content of `PAGE_TITLE` with the title of the page, you granted access for your integration and make sure your
token is set correctly as environment variable or in your configuration file.

``` py
--8<-- "examples/getting_started.py"
```

Run the code and you should see in JupyterLab following rendered Markdown code or just the plain output if you run the
code in a terminal.

![Getting started page](../assets/images/notion-getting-started-page.png){: style="width:600px; display:block; margin-left:auto; margin-right:auto;"}

## Notion concepts in a nutshell

In Notion everything is either a *page* or a *block*. A page contains a number of blocks, e.g. headings, text,
bulleted list, tables, quotes and so on.

An important and special block is the *database*, which may be within a page, i.e. *inline*, as a block
or at the same hierarchy level as a *page*. Every *database* has a *schema* defined by a set of *properties*,
i.e. columns, with specific types, e.g. number, text, url, etc., that imposes structured *properties*
on every page within that database. Only pages contained in a database have properties.
Notion itself also offers *linked databases* (with ↗ next to the database title) but those are not accessible
via the API, thus you must always work with the source database. A special type of database is a
*wiki database* that comes with a pre-defined schema, i.e., title, last-edited-time, owner, tags, verification.

Besides the properties of pages contained in a database, every page has *attributes* such as a title, cover, icon, or
whether it is archived or not. The *title* attribute of a page is special and will always be included as a property
in the schema if the page is contained in a database. The property name of the title attribute can be customized.
Think of the title property as a human-readable identifier, which does not have to be unique! This concept is important
when *relation* properties are used between different databases as the title property of a linked page will show up in
the relation property of the other database. If a page is deleted using Ultimate Notion, it is not deleted
directly but moved to the trash can, i.e. "🗑️ Trash" in the sidebar, for a period of 30 days before it is deleted.

A page, e.g. with title "child-page", can be contained in another page, e.g. with title "parent-page". This leads to a
hierarchy that is typically used for structuring content. We say that "parent-page" is the *parent* of "child-page" and
"child-page" is one of the *children* of "parent-page". A page at the root of the workspace has the workspace itself as parent.
This concept is important as access permissions for integrations are inherited from parent pages. Permissions can
only be granted to pages, not to complete workspaces encompassing all pages.

To identify a page, block, user, comment or even a property, Notion assigns each of them a universally unique
identifier (UUID), i.e. 32 hexadecimal digits, potentially structured in various fields by a dash, i.e. `-`.
Using for instance, the uuid of a database instead of its title, allows you to reference it in your code even after someone
changed its title. The UUIDs of pages and databases can be retrieved by using the web interface of Notion or using
<kbd>Copy link</kbd> from the <kbd>···</kbd>-menu in the upper right corner. The link will have the schema:

    https://www.notion.so/{TITLE-OF-PAGE}-{UUID}?{PARAMS}

UUIDs of other entities like blocks, properties, users etc. can only be retrieved via the API. Ultimate Notion provides
an `id`-property on most of its objects for that. Notion also provides a shortened URL compared to the one above:

    https://notion.so/{UUID}



[My integrations]: https://www.notion.so/my-integrations
[logo]: ../assets/images/logo_integration.png
