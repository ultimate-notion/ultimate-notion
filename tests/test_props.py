from hypothesis import given, strategies as st
import pytest

from ultimate_notion.props import Number


@given(st.floats(allow_nan=False, allow_infinity=False), st.floats(allow_nan=False, allow_infinity=False))
def test_number_add(a, b):
    num1 = Number(a)
    num2 = Number(b)
    result = num1 + num2
    assert result.value == pytest.approx(a + b)

    result = num1 + b
    assert result.value == pytest.approx(a + b)

    num1 += num2
    assert num1.value == pytest.approx(a + b)

    num2 += a
    assert num2.value == pytest.approx(a + b)


@given(st.floats(allow_nan=False, allow_infinity=False), st.floats(allow_nan=False, allow_infinity=False))
def test_number_sub(a, b):
    num1 = Number(a)
    num2 = Number(b)
    result = num1 - num2
    assert result.value == pytest.approx(a - b)

    result = num1 - b
    assert result.value == pytest.approx(a - b)

    num1 -= num2
    assert num1.value == pytest.approx(a - b)

    num2 -= a
    assert num2.value == pytest.approx(b - a)


@given(st.floats(allow_nan=False, allow_infinity=False), st.floats(min_value=0.001, max_value=10000.0))
def test_number_truediv(a, b):
    num1 = Number(a)
    num2 = Number(b)
    result = num1 / num2
    assert result.value == pytest.approx(a / b)

    result = num1 / b
    assert result.value == pytest.approx(a / b)

    num1 /= num2
    assert num1.value == pytest.approx(a / b)

    num1 = Number(a)
    num1 /= b
    assert num1.value == pytest.approx(a / b)


@given(st.floats(allow_nan=False, allow_infinity=False), st.floats(min_value=0.001, max_value=10000.0))
def test_number_floordiv(a, b):
    num1 = Number(a)
    num2 = Number(b)
    result = num1 // num2
    assert result.value == pytest.approx(a // b)

    result = num1 // b
    assert result.value == pytest.approx(a // b)

    num1 //= num2
    assert num1.value == pytest.approx(a // b)

    num1 = Number(a)
    num1 //= b
    assert num1.value == pytest.approx(a // b)


@given(st.integers() | st.floats(allow_nan=False, allow_infinity=False))
def test_number_float(a):
    num = Number(a)
    assert float(num) == float(a)
    assert isinstance(float(num), float)


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_number_int(a):
    num = Number(a)
    assert int(num) == int(a)


@given(st.floats() | st.integers(), st.floats() | st.integers())
def test_number_cmp(a, b):
    num1 = Number(a)
    num2 = Number(b)

    if a < b:
        assert num1 < num2
        assert num1 < b
    if a <= b:
        assert num1 <= num2
        assert num1 <= b
    if a == b:
        assert num1 == num2
        assert num1 == b
    if a > b:
        assert num1 > num2
        assert num1 > b
    if a >= b:
        assert num1 >= num2
        assert num1 >= b
