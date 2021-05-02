"""Functions ported from tidyverse-tibble"""
import itertools
from typing import Any, Callable, Iterable, List, Mapping, Union, Optional

import pandas
from pandas import DataFrame, Series, RangeIndex
from pipda import Context, register_func, register_verb
from pipda.utils import Expression
from pipda.symbolic import DirectRefAttr, DirectRefItem
from varname import argname, varname
from varname.utils import VarnameRetrievingError

from ..core.defaults import DEFAULT_COLUMN_PREFIX
from ..core.utils import copy_attrs, df_assign_item, to_df, logger
from ..core.names import repair_names
from ..core.grouped import DataFrameGroupBy, DataFrameRowwise
from ..core.types import is_scalar
from ..base import setdiff

def tibble(
        *args: Any,
        _name_repair: Union[str, Callable] = 'check_unique',
        _rows: Optional[int] = None,
        **kwargs: Any
) -> DataFrame:
    # pylint: disable=too-many-statements,too-many-branches
    """Constructs a data frame

    Args:
        *args, **kwargs: A set of name-value pairs.
        _name_repair: treatment of problematic column names:
            - "minimal": No name repair or checks, beyond basic existence,
            - "unique": Make sure names are unique and not empty,
            - "check_unique": (default value), no name repair,
                but check they are unique,
            - "universal": Make the names unique and syntactic
            - a function: apply custom name repair
        _rows: Number of rows of a 0-col dataframe when args and kwargs are
            not provided. When args or kwargs are provided, this is ignored.

    Returns:
        A dataframe
    """
    if not args and not kwargs:
        df = DataFrame() if not _rows else DataFrame(index=range(_rows))
        try:
            df.__dfname__ = varname(raise_exc=False)
        except VarnameRetrievingError:
            df.__dfname__ = None # pragma: no cover
        return df

    try:
        argnames = argname(args, vars_only=False, pos_only=True)
        if len(argnames) != len(args):
            raise VarnameRetrievingError
    except VarnameRetrievingError:
        argnames = [f"{DEFAULT_COLUMN_PREFIX}{i}" for i in range(len(args))]

    name_values = zip(argnames, args)
    name_values = itertools.chain(name_values, kwargs.items())
    # cannot do it with Mappings, same keys will be lost
    names = []
    values = []
    for name, value in name_values:
        names.append(name)
        values.append(value)

    names = repair_names(names, repair=_name_repair)
    df = None

    for name, arg in zip(names, values):
        if arg is None:
            continue
        if isinstance(arg, Expression):
            arg = arg(df, Context.EVAL.value)

        if isinstance(arg, dict):
            arg = tibble(**arg)

        elif isinstance(arg, Series) and name in argnames:
            name = arg.name

        if df is None:
            if isinstance(arg, DataFrame):
                # df = arg.copy()
                # DataFrameGroupBy.copy copied into DataFrameGroupBy
                df = DataFrame(arg).copy()
                if name not in argnames:
                    df.columns = [f'{name}${col}' for col in df.columns]

            else:
                df = to_df(arg, name)
        elif isinstance(arg, DataFrame):
            for col in arg.columns:
                df_assign_item(
                    df,
                    f'{name}${col}' if name not in argnames else col,
                    arg[col],
                    allow_dups=True
                )
        else:
            df_assign_item(df, name, arg, allow_dups=True)

    if df is None:
        df = DataFrame()
    try:
        df.__dfname__ = varname(raise_exc=False)
    except VarnameRetrievingError: # still raises in some cases
        df.__dfname__ = None # pragma: no cover

    if not kwargs and len(args) == 1 and isinstance(args[0], DataFrame):
        copy_attrs(df, args[0])
    return df

@register_func(None, context=Context.EVAL)
def fibble(
        *args: Any,
        _name_repair: Union[str, Callable] = 'check_unique',
        _rows: Optional[int] = None,
        **kwargs: Any
) -> DataFrame:
    """A function of tibble that can be used as an argument of verbs"""
    return tibble(*args, **kwargs, _name_repair=_name_repair, _rows=_rows)

def tribble(*dummies: Any) -> DataFrame:
    """Create dataframe using an easier to read row-by-row layout

    Args:
        *dummies: Arguments specifying the structure of a dataframe
            Variable names should be specified with `f.name`

    Examples:
        >>> tribble(
        >>>     f.colA, f.colB,
        >>>     "a",    1,
        >>>     "b",    2,
        >>>     "c",    3,
        >>> )

    Returns:
        A dataframe
    """
    columns = []
    data = []
    for dummy in dummies:
        # columns
        if isinstance(dummy, (DirectRefAttr, DirectRefItem)):
            columns.append(dummy.ref)
        elif not columns:
            raise ValueError(
                'Must specify at least one column using the `f.<name>` syntax.'
            )
        else:
            if not data:
                data.append([])
            if len(data[-1]) < len(columns):
                data[-1].append(dummy)
            else:
                data.append([dummy])

    ret = (
        DataFrame(data, columns=columns) if data
        else DataFrame(columns=columns)
    )
    try:
        ret.__dfname__ = varname(raise_exc=False)
    except VarnameRetrievingError:
        ret.__dfname__ = None # pragma: no cover
    return ret

def enframe(
        x: Optional[Union[Iterable, Mapping]],
        name: Optional[str] = "name",
        value: str = "value",
        _base0: bool = False
) -> DataFrame:
    """Converts mappings or lists to one- or two-column data frames."""
    if not value:
        raise ValueError("`value` can't be empty.")

    if x is None:
        x = []
    if is_scalar(x):
        x = [x]

    if len(getattr(x, 'shape', ())) > 1:
        raise ValueError(
            f"`x` must not have more than one dimension, got {len(x.shape)}."
        )

    if not name and isinstance(x, dict):
        x = x.values()

    elif name:
        if not isinstance(x, dict):
            names = (i + int(not _base0) for i in range(len(x)))
            values = x
        else:
            names = x.keys()
            values = x.values()
        x = (list(item) for item in zip(names, values))

    return DataFrame(x, columns=[name, value] if name else [value])

def deframe(x: DataFrame) -> Union[Iterable, Mapping]:
    """Converts two-column data frames to a dictionary, using
    the first column as name and the second column as value.
    If the input has only one column, a list.
    """
    if x.shape[1] == 1:
        return x.iloc[:, 0].values

    if x.shape[1] != 2:
        logger.warning(
            "`x` must be a one- or two-column data frame in `deframe()`."
        )

    return dict(zip(x.iloc[:, 0], x.iloc[:, 1]))

@register_verb(DataFrame, context=Context.EVAL)
def add_row(
        _data: DataFrame,
        *args: Any,
        _before: Optional[int] = None,
        _after: Optional[int] = None,
        _base0: bool = False,
        **kwargs: Any
) -> DataFrame:
    """Add one or more rows of data to an existing data frame."""
    if (
            isinstance(_data. DataFrameGroupBy) and
            not isinstance(_data, DataFrameRowwise)
    ):
        raise ValueError("Can't add rows to grouped data frames.")

    from ..dplyr.group_by import group_by_drop_default
    from ..dplyr.group_data import group_vars

    if not args and not kwargs:
        df = DataFrame(index=[0])
    else:
        df = tibble(*args, **kwargs)

    extra_vars = setdiff(df.columns, _data.columns)
    if extra_vars:
        raise ValueError(f"New rows can't add columns: {extra_vars}")

    pos = pos_from_before_after(_before, _after, _data.shape[0], _base0)
    out = rbind_at(_data, df, pos)

    if isinstance(_data, DataFrameRowwise):
        out = DataFrameRowwise(
            out,
            _group_vars=group_vars(_data),
            _drop=group_by_drop_default(_data)
        )

    copy_attrs(out, _data)
    return out

@register_verb(DataFrame, context=Context.EVAL)
def add_column(
        _data: DataFrame,
        *args: Any,
        _before: Optional[Union[str, int]] = None,
        _after: Optional[Union[str, int]] = None,
        _name_repair: Union[str, Callable] = 'check_unique',
        _base0: bool = False,
        **kwargs: Any
) -> DataFrame:
    """Add one or more columns to an existing data frame."""
    from ..dplyr.group_by import group_by_drop_default
    from ..dplyr.group_data import group_vars

    df = tibble(*args, **kwargs, _name_repair=_name_repair)

    if df.shape[1] == 0:
        return _data.copy()

    if df.shape[0] != _data.shape[0]:
        if df.shape[0] != 1:
            raise ValueError(
                f"New columns have {df.shape[0]} rows, "
                f"but `_data` has {_data.shape[0]}."
            )
        df = df.iloc[[0] * _data.shape[0], :].reset_index(drop=True)

    pos = pos_from_before_after_names(
        _before,
        _after,
        _data.columns.tolist(),
        _base0
    )
    out = cbind_at(_data, df, pos)

    if isinstance(_data, DataFrameGroupBy):
        out = _data.__class__(
            out,
            _group_vars=group_vars(_data),
            _drop=group_by_drop_default(_data)
        )

    copy_attrs(out, _data)
    return out

@register_verb(DataFrame)
def has_rownames(_data: DataFrame) -> bool:
    """Detect if a data frame has row names"""
    return not isinstance(_data.index, RangeIndex)

has_index = has_rownames # pylint: disable=invalid-name

@register_verb(DataFrame)
def remove_rownames(_data: DataFrame) -> DataFrame:
    """Remove the index/rownames of a data frame"""
    return _data.reset_index(drop=True)

remove_index = drop_index = remove_rownames # pylint: disable=invalid-name

@register_verb(DataFrame)
def rownames_to_column(_data: DataFrame, var="rowname") -> DataFrame:
    """Add rownames as a column"""
    if var in _data.columns:
        raise ValueError(f"Column name `{var}` must not be duplicated.")

    from ..dplyr.mutate import mutate
    return mutate(_data, **{var: _data.index}, _before=0)

index_to_column = rownames_to_column # pylint: disable=invalid-name

@register_verb(DataFrame)
def rowid_to_column(_data: DataFrame, var="rowname") -> DataFrame:
    """Add rownames as a column"""
    if var in _data.columns:
        raise ValueError(f"Column name `{var}` must not be duplicated.")

    from ..dplyr.mutate import mutate
    return mutate(_data, **{var: range(0, _data.shape[0])}, _before=0)

@register_verb(DataFrame, context=Context.SELECT)
def column_to_rownames(_data: DataFrame, var: str = "rowname") -> DataFrame:
    """Set rownames/index with one column, and remove it"""
    from ..dplyr.mutate import mutate

    rownames = _data[var]
    out = mutate(_data, **{var: None})
    out.index = rownames
    return out

column_to_index = column_to_rownames # pylint: disable=invalid-name

# Helpers ------------------------------------------------------------------

def pos_from_before_after_names(
        before: Optional[Union[str, int]],
        after: Optional[Union[str, int]],
        names: List[str],
        base0: bool
) -> int:
    """Get the position to insert from before and after"""
    before = check_names_before_after(before, names, base0)
    after = check_names_before_after(after, names, base0)
    return pos_from_before_after(before, after, len(names), True)

def check_names_before_after(
        pos: Optional[Union[str, int]],
        names: List[str],
        base0: bool
) -> int:
    """Get position by given index or name"""
    if pos is None:
        return len(names)
    if not isinstance(pos, str):
        return pos - int(not base0)
    return names.index(pos)

def cbind_at(data: DataFrame, df: DataFrame, pos: int) -> DataFrame:
    """Column bind at certain pos, 0-based"""
    part1 = data.iloc[:, :pos]
    part2 = data.iloc[:, pos:]
    return pandas.concat((part1, df, part2), axis=1, ignore_index=True)

def pos_from_before_after(
        before: Optional[int],
        after: Optional[int],
        nrow: int,
        base0: bool
) -> int:
    """Get the position to insert from before and after"""
    if before is not None and after is not None:
        raise ValueError("Can't specify both `_before` and `_after`.")

    if before is None and after is None:
        return nrow

    if after is not None:
        after = after - int(not base0) if after > 0 else nrow + after
        return max(0, min(after + 1, nrow))

    before = before - int(not base0) if before > 0 else nrow + before
    return max(0, min(before - 1, nrow))

def rbind_at(data: DataFrame, df: DataFrame, pos: int) -> DataFrame:
    """Row bind at certain pos, 0-based"""
    part1 = data.iloc[:pos, :]
    part2 = data.iloc[pos:, :]
    return pandas.concat((part1, df, part2)).reset_index(drop=True)
