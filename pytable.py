# -*- coding: utf-8 -*-
"""
tables - simple tables using named tuples, with a bit of SQL thrown in

A table is a list of dicts with the same keys.
"""

from collections import defaultdict
import csv

# if you want to read xl files, you need this:
try:
    import openpyxl
except ImportError:
    openpyxl = None


class Table:
    def __init__(self, columns):
        """create a table object with defined columns

        Parameters:
            columns: a string or list of strings giving the column names
                if a string, column names are separated by spaces and/or commas.

        Returns:
            a Table object. This is a lightweight pandas-alike data structure
            containing two properties:
                - columns: a list of column names
                - rows: a list of row dicts. The dict keys are the same
                    as the columns.

            For example, if a table object has columns ['a', 'b'], then it
            might have rows [{'a':1,'b':2}, {'a':3,'b':4}, ...]

            The table has some SQL like operations (select, where, insert)
            and some more pythonic operations (indexing, sorting).
        """
        if isinstance(columns, str):
            # the columns must be parsed
            columns = columns.replace(",", " ").split()
        self.columns = columns
        # the table is empty
        self.rows = []

    def index(self, colname):
        """creates an index of the rows based on row[colname]

        Parameters:
            colname: the name of the column to create the index on.
                This implementation requires that the values in colname
                are unique.

        Returns:
            the table

        Note: might remove this if no use can be found for it.
        """
        self._index = {}
        for row in self.rows:
            self._index[row[colname]] = row
        return self

    def _addrow(self, data):
        """add a row to the table. called by insert

        Parameters:
            data: the row to add. data can be a tuple or list or dict
               or object.

               1 If data is a tuple or list, it is zipped with the table columns to
                 form a dict.
               2 If data is a dict, values corresponding to table columns
                 are extracted. Other dict keys are ignored
               3 If data is an object, attributes corresponding to table columns
                 are extracted. Other attributes are ignored

            In case 1, there must be the right number of values to zip.
            In cases 2 and 3, if the dict or object does not have a key
            corresponding to the table columns, it is replaced by None

        Returns:
            self
        """
        if type(data) is dict:
            # get all the values of keys in self.columns
            data = [data.get(k, None) for k in self.columns]
        elif type(data) not in [list, tuple]:
            # get all the values of attributes in self.columns
            data = [getattr(data, k, None) for k in self.columns]
        else:
            # just check lengths
            if len(data) != len(self.columns):
                raise ValueError("Wrong number of data values")
        # append a row dict
        self.rows.append(dict(zip(self.columns, data)))
        return self

    def add_rows(self, *datalist):
        """add rows to the table from an iterable datalist.
        Each element of the iterable must be a list, tuple, dict or object.

        Parameters:
            datalist: an iterable of lists, dicts or objects. See _addrow
                for how these are treated.

        Returns:
            the table with the extra rows.
        """
        for d in datalist:
            # insert one at a time
            self._addrow(d)
        return self

    def rename_column(self, oldname, newname):
        """renames a column

        Parameters:
            oldname: the current name of the column
            newname: the new name of the column

        Returns:
            the table with the column renamed.
        """
        # change the columns
        self.columns[self.columns.index(oldname)] = newname
        # change each of the row dicts by renaming them in the right
        # sequence.
        for i, v in enumerate(self.rows):
            self.rows[i] = dict(zip(self.columns, v.values()))
        return self

    def remove_column(self, colname):
        """removes a column

        Parameters:
            colname: the name of the column to remove

        Returns:
            the table
        """
        # remove from the column list
        self.columns = [c for c in self.columns if c != colname]
        # remove from each of the row dicts
        for row in self.rows:
            del row[colname]
        return self

    def set_column(self, colname, colvalue=None):
        """sets the value of a column to the table

        Parameters:
            colname: the name of the column to set. If it
                doesn't exist, it is created
            colvalue: the value to fill the column with, either
                a scalar value or a list of values of the same length
                as the rows of the table

        Returns:
            the table with the column changed or added
        """
        if colname not in self.columns:
            self.columns.append(colname)
        if type(colvalue) in [list, tuple]:
            # check length
            if len(colvalue) != len(self.rows):
                raise ValueError("Wrong number of values ")
            # add or replace the value in each row dict
            for i, row in enumerate(self.rows):
                row[colname] = colvalue[i]
        else:
            # there is a single value,
            # add or replace the value in each row dict
            for row in self.rows:
                row[colname] = colvalue
        return self

    def __setitem__(self, key, value):
        """sets a column to a value, where value is either a scalar or a list"""
        return self.set_column(key, value)

    def __getitem__(self, key):
        """returns a list of the values in the column"""
        result = []
        for row in self.rows:
            result.append(row[key])
        return result

    def calculate_column(self, colname, f):
        """calculates a column based on a function

        Parameters:
            colname: the name of the column to calculate. If it doesn't
                exist, it is added.
            f: a function which takes a row dict and returns a scalar

        Returns:
            the table with the column added or changed.
        """
        if colname not in self.columns:
            self.columns.append(colname)
        for row in self.rows:
            row[colname] = f(row)
        return self

    def map_column(self, colname, f):
        """applies a function to a column

        Parameters:
            colname: the name of the existing column to calculate.
            f: a function which takes a scalar and returns a scalar

        Returns:
            the table with the column changed, r[colname] = f(r[colname])
            for each row object r

        Use this instead of calc if your calculations are restricted to
        a single column. Useful for type conversions.
        """
        if colname not in self.columns:
            raise ValueError(f"{colname} is not a column in the table")
        for r in self.rows:
            r[colname] = f(r[colname])
        return self

    def sort(self, colname, reverse=False, keyconvert=None):
        """sort the table in place.

        Parameters:
            colname: the column name to sort on
            reverse: True if you want a descending sort
            keyconvert: a callable to convert the sort column values to
                some type while sorting e.g. lower case, int, etc.
                Default is to do nothing.

        Returns:
            the sorted table.
        """
        if keyconvert is None:
            self.rows.sort(key=lambda r: r[colname], reverse=reverse)
        else:
            self.rows.sort(
                key=lambda r: keyconvert(r[colname]), reverse=reverse
            )

    def filter_rows(self, pred):
        """filter rows by a predicate

        Parameters:
            pred: a predicate function which takes a row dict

        Returns:
            A table containing only those rows for which pred is true.
            The row dicts of the filtered table are the same as
            the row dicts of the original table. This lets you work
            on subsets of the original table.

            To make an independent copy, do select('*') on the result.
        """
        ft = Table(self.columns)
        ft.rows = [*filter(pred, self.rows)]
        return ft

    def select_columns(self, columns):
        """select a subset of columns

        Parameters:
            columns: the columns to select. If '*', all columns are
               selected and a copy of the table is made. If a string, the
               column names are separated by commas or spaces. Otherwise,
               it should be a list or tuple of strings.

        Returns:
            a new table containing only those columns in the parameter,
            in the order given.
        """
        if columns == "*":
            # we select all columns
            columns = self.columns
        elif isinstance(columns, str):
            # parse the columns that we select
            columns = columns.replace(",", " ").split()
        # create the select table
        st = Table([*columns])
        # addrows to the table
        for r in self.rows:
            # the list here is the row values in order
            # of the given columns
            st.insert([r.get(k) for k in columns])
        return st

    def __iter__(self):
        yield from self.rows

    def __len__(self):
        return len(self.rows)

    def join(self, right, on, mode="inner"):
        """join to another table

        Parameters:
            right: the right hand table in the join (the left hand table is self)
            on: the columns to match on. If this is a string,
                we match on self[on]==right[on]. If it's a tuple
                we match on self[on[0]]==right[on[1]]
            mode: 'inner'. 'outer', 'left', and 'right'.

        Returns:
            the joined table. The columns of the table are
            [self[on], ... other columns from self, ...other columns from right]
            The rows are ordered as follows:
                first, all rows in self & right that match.
                then, if mode is 'left' or 'outer', the unmatched rows from self
                then, if mode is 'right' or 'outer', the unmatched rows from right
            In unmatched rows, missing values are set to None.
        """
        if type(on) is str:
            # the on column is the same in both tables
            on = (on, on)
        # lid and rid are the left, right ids from on
        lid, rid = on

        # lookup will lookup rows of the right hand table based on the id. Multiple
        # rows may have the same id
        lookup = defaultdict(list)
        # create the lookup which holds rows of right hand table keyed by on[1]
        for r in right.rows:
            lookup[r[rid]].append(r)

        # dummyL & dummyR are rows from left (self) and right
        # tables used when there is no id match
        dummyL = dict(zip(self.columns, [None] * len(self.columns)))
        dummyR = dict(zip(right.columns, [None] * len(right.columns)))

        # joinrow computes the joined row from the self and right hand table rows
        joinrow = lambda a, b: [
            a[lid] if a[lid] is not None else b[rid],  # the id value
            *[
                a[k] for k in self.columns if k != lid
            ],  # the remaining values in self
            *[
                b[k] for k in right.columns if k != rid
            ],  # the remaining values in right hand table
        ]
        # use joinrow to select the column names
        allcolumns = joinrow(
            dict(zip(self.columns, self.columns)),
            dict(zip(right.columns, right.columns)),
        )

        # and create the joined table
        joined = Table(allcolumns)

        # left_unmatched holds rows in the self table that don't
        # match right hand table
        left_unmatched = []
        # right_matched holds ids from the right hand table that match self
        right_matched = []

        # join the rows
        for row in self.rows:
            leftid = row[lid]
            if leftid in lookup:
                # left & right rows match so we join them
                for rightrow in lookup[leftid]:
                    # create a joined row for each row in right hand table having the id
                    joined.add_rows(joinrow(row, rightrow))
                # and note that the id matches
                if mode in ["right", "outer"]:
                    right_matched.append(leftid)
            elif mode in ["left", "outer"]:
                # we didn't get a match, and with this mode we
                # need to remember that the self row didn't match
                left_unmatched.append(row)
        # left and outer modes now must have the unmatched rows from the
        # left (self) table
        if mode in ["left", "outer"]:
            for row in left_unmatched:
                joined.insert(joinrow(row, dummyR))
        # right and outher modes must now have the rows in the right hand table
        # that didn't match
        if mode in ["right", "outer"]:
            for id, rows in lookup.items():
                if id not in right_matched:
                    for row in rows:
                        joined.add_rows(joinrow(dummyL, row))
        return joined


def readcsv(path):
    """read a csv file consisting of a header row and
    one or more data rows.

    Parameters:
        path: the path to the file

    Returns:
        a table object
    """
    with open(path, "r", newline="") as f:
        reader = csv.reader(f)
        t = Table(next(reader))
        for row in reader:
            t.insert(row)
    return t


def writecsv(path, table):
    """write a table to a csv file.

    Parameters:
        path: the path to the file
        table: a table object
    """
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=table.columns)
        writer.writeheader()
        for row in table.rows:
            writer.writerow(row)


def readxl(path, sheet=0):
    """read a page of an Excel spreadsheet consisting of a header row and
    one or more data rows.

    Parameters:
        path: the path to the spreadsheet
        sheet: the sheet number (defaults to 0, the first one)

    Returns:
        a table object
    """
    wb = openpyxl.load_workbook(path)
    sheet = wb.worksheets[sheet]
    fields = None
    rows = []
    for row in sheet.iter_rows(min_row=None, values_only=True):
        if fields is None:
            fields = [*map(lambda s: s.strip(), row)]
        else:
            rows.append(dict(zip(fields, row)))
    t = Table(fields)
    t.rows = rows
    return t


if __name__ == "__main__":
    t = Table("id b c")
    t.add_rows([1, 5, 6], [2, 2, 3], [3, 4, 8])

    t2 = Table("id2, x, y")
    t2.add_rows(
        [1, 50, 60], [2, 20, 30], [2, 21, 31], [33, 40, 80], [33, 41, 81]
    )

    j = t.join(t2, on=("id", "id2"), mode="right")
