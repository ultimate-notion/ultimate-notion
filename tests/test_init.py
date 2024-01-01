from packaging.version import Version

import ultimate_notion


def test_version():
    assert str(Version(ultimate_notion.__version__))


def test_clean_notion_test_are(notion_cleanups):
    """Test to make sure that the notion test area is cleaned after all tests ran"""
