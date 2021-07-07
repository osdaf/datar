import pytest
from pandas import DataFrame
from datar.base import *
from datar.tibble import tibble

from .conftest import assert_iterable_equal

def test_rowcolnames():
    df = DataFrame(dict(x=[1,2,3]))
    assert colnames(df) == ['x']
    assert rownames(df) == [0, 1, 2]
    df = DataFrame([1,2,3], index=['a', 'b', 'c'])
    assert colnames(df) == [0]
    assert rownames(df) == ['a', 'b', 'c']

    df = colnames(df, ['y'])
    assert_iterable_equal(df.columns, ['y'])

    df = colnames(df, ['y'], _nested=False)
    assert_iterable_equal(df.columns, ['y'])

    assert_iterable_equal(colnames(df, _nested=False), ['y'])

    df = rownames(df, ['a', 'b', 'c'])
    assert_iterable_equal(df.index, ['a', 'b', 'c'])

    df = tibble(a=tibble(x=1, y=1), b=tibble(u=2, v=3), z=2)
    df = df >> colnames(['c', 'd', 'w'], _nested=True)
    assert_iterable_equal(df.columns, ['c$x', 'c$y', 'd$u', 'd$v', 'w'])


def test_diag():
    out = dim(3 >> diag())
    assert out == (3,3)
    out = dim(10 >> diag(3, 4))
    assert out == (3,4)
    x = c(1j,2j) >> diag()
    assert x.iloc[0,0] == 0+1j
    assert x.iloc[0,1] == 0+0j
    assert x.iloc[1,0] == 0+0j
    assert x.iloc[1,1] == 0+2j
    x = TRUE >> diag(3)
    assert sum(x.values.flatten()) == 3
    x = c(2,1) >> diag(4)
    assert_iterable_equal(x >> diag(), [2,1,2,1])

    with pytest.raises(ValueError):
        x >> diag(3, 3)

    x = 1 >> diag(4)
    assert_iterable_equal(x >> diag(3) >> diag(), [3,3,3,3])

def test_ncol():
    df = tibble(x=tibble(a=1, b=2))
    assert ncol(df) == 1
    assert ncol(df, _nested=False) == 2

def test_t():
    df = tibble(x=1, y=2)
    out = t(df)
    assert out.shape == (2, 1)
    assert_iterable_equal(out.index, ['x', 'y'])

def test_names():
    assert_iterable_equal(names(tibble(x=1)), ['x'])
    assert_iterable_equal(names({'x': 1}), ['x'])
    assert names({'x':1}, ['y']) == {'y': 1}

def test_setdiff():
    assert_iterable_equal(setdiff(1,2), [1])
    assert_iterable_equal(setdiff([1,2], [2]), [1])


def test_intersect():
    assert_iterable_equal(intersect(1,2), [])
    assert_iterable_equal(intersect([1,2], [2]), [2])

def test_union():
    assert_iterable_equal(union(1,2), [1,2])
    assert_iterable_equal(union([1,2], [2]), [1,2])

def test_setequal():
    assert setequal([1,2], [2,1])
    assert setequal(1, 1)

def test_duplicated():
    assert_iterable_equal(
        duplicated([1,1,-1,-1,2,2], incomparables=[-1]),
        [False, True, False, False, False, True]
    )
    assert_iterable_equal(
        duplicated([1,1,2,2], from_last=True),
        [True, False, True, False]
    )
    df = tibble(x=[1,1,2,2])
    assert_iterable_equal(duplicated(df), [False, True, False, True])
