from __future__ import annotations

import numpy as np
import pytest
from numpy.testing import assert_array_equal

from ultimate_notion import utils


def test_find_indices():
    elems = np.array([7, 2, 4])
    total_set = np.array([1, 2, 7, 3, 6, 4])
    idx = utils.find_indices(elems, total_set)
    assert_array_equal(idx, np.array([2, 1, 5]))

    elems = np.array(['Col7', 'Col2', 'Col4'])
    total_set = np.array(['Col1', 'Col2', 'Col7', 'Col3', 'Col6', 'Col4'])
    idx = utils.find_indices(elems, total_set)
    assert_array_equal(idx, np.array([2, 1, 5]))


def test_slist():
    lst = utils.SList(range(3))
    assert isinstance(lst, list)
    with pytest.raises(ValueError):
        lst.item()
    lst = utils.SList([42])
    item = lst.item()
    assert item == 42


def test_deepcopy_with_sharing():
    class Class:
        def __init__(self):
            self.shared = {'a': 1}
            self.copied = {'a': 2}

    obj = Class()
    copy = utils.deepcopy_with_sharing(obj, shared_attributes=['shared'])
    assert obj.copied is not copy.copied
    assert obj.shared is copy.shared


def test_find_index():
    test_set = [2, 4, 72, 23]
    assert utils.find_index(4, test_set) == 1
    assert utils.find_index(23, test_set) == 3
    assert utils.find_index(42, test_set) is None


def test_rank():
    assert_array_equal(utils.rank(np.array([1, 3, 2, 4])), np.array([0, 2, 1, 3]))
    assert_array_equal(utils.rank(np.array([1, 3, 2, 2])), np.array([0, 2, 1, 1]))
    assert_array_equal(utils.rank(np.array([3, 1, 2, 2])), np.array([2, 0, 1, 1]))
    assert_array_equal(utils.rank(np.array([3, 1, 1, 2])), np.array([2, 0, 0, 1]))
    assert_array_equal(utils.rank(np.array([7, 7, 11, 9])), np.array([0, 0, 2, 1]))


def test_is_stable_version():
    assert utils.is_stable_version('1.2.3') is True
    assert utils.is_stable_version('1.2.3a') is False
    assert utils.is_stable_version('1.2.3b') is False
    assert utils.is_stable_version('1.2.3rc') is False
    assert utils.is_stable_version('1.2.3.dev') is False
    assert utils.is_stable_version('1.2.3.post') is False
    assert utils.is_stable_version('1.2.3.post1') is False
    assert utils.is_stable_version('1.2.3.post0') is False
    assert utils.is_stable_version('1.2.3.post1.dev') is False
