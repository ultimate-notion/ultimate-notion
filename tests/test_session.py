"""Unit tests for the Notion Session"""
import pytest


@pytest.mark.webtest
def test_raise_for_status(notion):
    notion.raise_for_status()
