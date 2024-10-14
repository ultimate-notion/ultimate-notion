"""Low-level object-oriented API for Notion.

This subpackage provides an object-oriented API for Notion by wrapping the JSON-structured
requests and responses of [notion-sdk-py] into Python objects using pydantic. Also paginated
result lists by the API are resolved automatically.

The code was taken originally from [Notional] by Jason Heddings and is MIT-licensed.
Due to the Pydantic v2 migration and several other design changes, it was heavily refactored since then.

[Notional]: https://github.com/jheddings/notional
[notion-sdk-py]: https://github.com/ramnes/notion-sdk-py/
"""

from __future__ import annotations

from ultimate_notion.obj_api.endpoints import NotionAPI

__all__ = ['NotionAPI']

# ToDo: add here everything needed also obj_names for concistency. And make sure we only important from here t
# o establish an API.


# ToDo: Recheck every model if `= None` really is needed. Maybe come up with an even smarter way
#       to differentiate between a model for sending and receiving data.
