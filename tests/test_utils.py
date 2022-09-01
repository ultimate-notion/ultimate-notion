import pytest

from ultimate_notion.utils import slist


def test_slist():
    sl = slist([1])
    assert isinstance(sl, list)
    assert sl.item() == 1

    sl = slist([1, 2])
    with pytest.raises(ValueError):
        sl.item()

    sl = slist([])
    with pytest.raises(ValueError):
        sl.item()
