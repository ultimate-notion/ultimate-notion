from packaging.version import Version

import ultimate_notion


def test_version():
    assert str(Version(ultimate_notion.__version__))
