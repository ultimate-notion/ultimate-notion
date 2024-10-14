from __future__ import annotations

import pytest

import ultimate_notion as uno


@pytest.mark.vcr()
def test_list_comments(comment_page: uno.Page):
    comments = comment_page.comments
    assert len(comments) == 5
    comment = comments[4]
    assert comment.text == 'Another comment'
    assert comment.user.name == 'Flo-Bot'


@pytest.mark.vcr()
def test_new_page_comment(root_page: uno.Page, notion: uno.Session):
    comment_page = notion.create_page(parent=root_page, title='Page for page comments')
    assert len(comment_page.comments) == 0

    comment_page.comments.append('My first comment')
    assert len(comment_page.comments) == 1

    comment_page.reload()
    assert len(comment_page.comments) == 1

    comment_page.comments.append('Another comment')
    assert len(comment_page.comments) == 2


@pytest.mark.vcr()
def test_append_block_comments(comment_page: uno.Page):
    # Note that this test is quite fragile as we can only add comments to a block that already has comments.
    # Also it's not possible to delete/resolve comments via the API, so we can't clean up after ourselves.
    block = uno.SList(child for child in comment_page.children if isinstance(child, uno.Heading1)).item()
    discussions = block.discussions
    assert len(discussions) == 2

    discussion = discussions[0]
    assert discussion[0].text == 'Infinite discussion!'
    curr_len = len(discussion)

    discussion.append('Another comment')
    assert len(discussion) == curr_len + 1

    comment_page.reload()
    assert len(discussions) == curr_len + 1
