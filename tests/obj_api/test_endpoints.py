from __future__ import annotations

import pytest

import ultimate_notion as uno


@pytest.mark.vcr()
def test_retrieve_property(all_props_db: uno.Database):
    page = all_props_db.get_all_pages().to_pages()[0]
    page_obj = page.obj_ref
    page_props = page.props._obj_prop_vals
    notion = uno.Session.get_or_create()

    for _, prop_val in page_props.items():
        list(notion.api.pages.properties.retrieve(page_obj, prop_val))
