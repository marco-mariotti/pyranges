"""Data structure for genomic intervals and their annotation."""

import pandas as pd
import numpy as np

from natsort import natsorted

import pyranges as pr

from pyranges.tostring2 import tostring

from pyranges.methods.intersection import _intersection, _overlap
from pyranges.multithreaded import pyrange_apply, pyrange_apply_single, pyrange_apply_chunks, _slack, _tes, _tss

__all__ = ["PyRanges"]

def fill_kwargs(kwargs):
    """Give the kwargs dict default options."""

    defaults = {
        "strandedness": None,
        "overlap": True,
        "how": None,
        "invert": None,
        "new_pos": None,
        "suffixes": ["_a", "_b"],
        "suffix": "_b",
        "sparse": {
            "self": False,
            "other": False
        }
    }

    defaults.update(kwargs)

    return defaults


class PyRanges():

    """Two-dimensional representation of genomic intervals and their annotations.

    A PyRanges object must have the columns Chromosome, Start and End. These
    describe the genomic position and function as implicit row labels. A Strand
    column is optional and adds strand information to the intervals. Any other
    columns are allowed and are considered metadata.

    Operations between PyRanges align intervals based on their position.

    If a PyRanges is built using the arguments chromosomes, starts, ends and
    optionally strands, all non-scalars must be of the same length.

    Parameters
    ----------
    df : pandas.DataFrame or dict of pandas.DataFrame, default None
        The data to be stored in the PyRanges.

    chromosomes : array-like or scalar value, default None
        The chromosome(s) in the PyRanges.

    starts : array-like, default None
        The start postions in the PyRanges.

    ends : array-like, default None
        The end postions in the PyRanges.

    strands : array-like or scalar value, default None
        The strands in the PyRanges.

    int64 : bool, default False
        Use np.int64 to represent starts and ends

    copy_df : bool, default True
        Copy input pandas.DataFrame

    See Also
    --------

    pyranges.read_bed: read bed-file into PyRanges
    pyranges.read_bam: read bam-file into PyRanges
    pyranges.read_gff: read gff-file into PyRanges
    pyranges.read_gtf: read gtf-file into PyRanges
    pyranges.from_dict: create PyRanges from dict of columns

    Notes
    -----

    A PyRanges object is represented internally as a dictionary efficiency. The keys are
    chromosomes or chromosome/strand tuples and the values are pandas DataFrames.

    Examples
    --------

    >>> pr.PyRanges()
    Empty PyRanges

    >>> pr.PyRanges(chromosomes="chr1", starts=(1, 5), ends=[3, 149],
    ...             strands=("+", "-"), int64=True)
    +--------------+-----------+-----------+--------------+
    | Chromosome   |     Start |       End | Strand       |
    | (category)   |   (int64) |   (int64) | (category)   |
    |--------------+-----------+-----------+--------------|
    | chr1         |         1 |         3 | +            |
    | chr1         |         5 |       149 | -            |
    +--------------+-----------+-----------+--------------+
    Stranded PyRanges object has 2 rows and 4 columns from 1 chromosomes.
    For printing, the PyRanges was sorted on Chromosome and Strand.

    >>> df = pd.DataFrame({"Chromosome": ["chr1", "chr2"], "Start": [100, 200],
    ...                    "End": [150, 201]})
    >>> df
      Chromosome  Start  End
    0       chr1    100  150
    1       chr2    200  201
    >>> pr.PyRanges(df)
    +--------------+-----------+-----------+
    | Chromosome   |     Start |       End |
    | (category)   |   (int32) |   (int32) |
    |--------------+-----------+-----------|
    | chr1         |       100 |       150 |
    | chr2         |       200 |       201 |
    +--------------+-----------+-----------+
    Unstranded PyRanges object has 2 rows and 3 columns from 2 chromosomes.
    For printing, the PyRanges was sorted on Chromosome.


    >>> gr = pr.from_dict({"Chromosome": [1, 1], "Strand": ["+", "-"], "Start": [1, 4], "End": [2, 27],
    ...                    "TP": [0, 1], "FP": [12, 11], "TN": [10, 9], "FN": [2, 3]})
    >>> gr
    +--------------+--------------+-----------+-----------+-----------+-----------+-----------+-----------+
    |   Chromosome | Strand       |     Start |       End |        TP |        FP |        TN |        FN |
    |   (category) | (category)   |   (int32) |   (int32) |   (int64) |   (int64) |   (int64) |   (int64) |
    |--------------+--------------+-----------+-----------+-----------+-----------+-----------+-----------|
    |            1 | +            |         1 |         2 |         0 |        12 |        10 |         2 |
    |            1 | -            |         4 |        27 |         1 |        11 |         9 |         3 |
    +--------------+--------------+-----------+-----------+-----------+-----------+-----------+-----------+
    Stranded PyRanges object has 2 rows and 8 columns from 1 chromosomes.
    For printing, the PyRanges was sorted on Chromosome and Strand.
    """

    dfs = None
    gf = None

    def __init__(self,
                 df=None,
                 chromosomes=None,
                 starts=None,
                 ends=None,
                 strands=None,
                 int64=False,
                 copy_df=True):

        from pyranges.methods.init import _init

        if df is None and chromosomes is None:
            df = pd.DataFrame(columns="Chromosome Start End".split())

        _init(self, df, chromosomes, starts, ends, strands, int64, copy_df)



    def __len__(self):
        """Return the number of intervals in the PyRanges."""
        return sum([len(d) for d in self.values()])

    # def __call__(self, f, strand=None, as_pyranges=True, nb_cpu=1, **kwargs):

    def __getattr__(self, name):

        from pyranges.methods.attr import _getattr

        return _getattr(self, name)

    def __setattr__(self, column_name, column):

        from pyranges.methods.attr import _setattr

        _setattr(self, column_name, column)

    def __getitem__(self, val):

        from pyranges.methods.getitem import _getitem

        return _getitem(self, val)

    def __str__(self):

        return tostring(self)

    def __repr__(self):

        return str(self)

    def __iter__(self):

        return iter(self.items())


    def apply(self, f, strand=None, as_pyranges=True, **kwargs):

        """Apply a function to the PyRanges.

        Parameters
        ----------
        f : function
            Function to apply on each DataFrame in a PyRanges

        strand : bool, default None, i.e. auto

            Whether to do operations on chromosome/strand pairs or chromosomes. If None, will use
            chromosome/strand pairs if the PyRanges is stranded.

        as_pyranges : bool, default True

            Whether to return as a PyRanges or dict. If `f` does not return a DataFrame valid for
            PyRanges, `as_pyranges` must be False.

        nb_cpu: int, default 1

            How many cpus to use. Can at most use 1 per chromosome or chromosome/strand tuple.
            Will only lead to speedups on large datasets.

        Returns
        -------
        PyRanges or dict
            Result of applying f to each DataFrame in the PyRanges

        See also
        --------

        pyranges.PyRanges.apply_pair: apply a function to a pair of PyRanges
        pyranges.PyRanges.apply_chunks: apply a row-based function to a PyRanges in parallel

        Note
        ----

        This is the function used internally to carry out almost all unary PyRanges methods.

        Examples
        --------

        >>> gr = pr.from_dict({"Chromosome": [1, 1, 2, 2], "Strand": ["+", "+", "-", "+"],
        ...                    "Start": [1, 4, 2, 9], "End": [2, 27, 13, 10]})
        >>> gr
        +--------------+--------------+-----------+-----------+
        |   Chromosome | Strand       |     Start |       End |
        |   (category) | (category)   |   (int32) |   (int32) |
        |--------------+--------------+-----------+-----------|
        |            1 | +            |         1 |         2 |
        |            1 | +            |         4 |        27 |
        |            2 | +            |         9 |        10 |
        |            2 | -            |         2 |        13 |
        +--------------+--------------+-----------+-----------+
        Stranded PyRanges object has 4 rows and 4 columns from 2 chromosomes.
        For printing, the PyRanges was sorted on Chromosome and Strand.

        >>> gr.apply(lambda df: len(df), as_pyranges=False)
        {('1', '+'): 2, ('2', '+'): 1, ('2', '-'): 1}

        >>> gr.apply(lambda df: len(df), as_pyranges=False, strand=False)
        {'1': 2, '2': 2}

        >>> def add_to_ends(df, **kwargs):
        ...     df.loc[:, "End"] = kwargs["slack"] + df.End
        ...     return df
        >>> gr.apply(add_to_ends, slack=500)
        +--------------+--------------+-----------+-----------+
        |   Chromosome | Strand       |     Start |       End |
        |   (category) | (category)   |   (int32) |   (int32) |
        |--------------+--------------+-----------+-----------|
        |            1 | +            |         1 |       502 |
        |            1 | +            |         4 |       527 |
        |            2 | +            |         9 |       510 |
        |            2 | -            |         2 |       513 |
        +--------------+--------------+-----------+-----------+
        Stranded PyRanges object has 4 rows and 4 columns from 2 chromosomes.
        For printing, the PyRanges was sorted on Chromosome and Strand.
        """

        if strand is None:
            strand = self.stranded

        kwargs.update({"strand": strand})
        kwargs.update(kwargs.get("kwargs", {}))
        kwargs = fill_kwargs(kwargs)

        result = pyrange_apply_single(f, self, strand, kwargs)

        if not as_pyranges:
            return result
        else:
            return PyRanges(result)


    def apply_chunks(self, f, as_pyranges=False, nb_cpu=1, **kwargs):

        """Apply a row-based function to arbitrary partitions of the PyRanges.

        apply_chunks speeds up the application of functions where the result is not affected by
        applying the function to ordered, non-overlapping splits of the data.

        Parameters
        ----------
        f : function
            Row-based or associative function to apply on the partitions.

        as_pyranges : bool, default False

            Whether to return as a PyRanges or dict. 

        nb_cpu: int, default 1

            How many cpus to use. The data is split into nb_cpu partitions.

        **kwargs
            Additional keyword arguments to pass as keyword arguments to `f`

        Returns
        -------
        dict of lists
            Result of applying f to each partition of the DataFrames in the PyRanges.

        See also
        --------

        pyranges.PyRanges.apply_pair: apply a function to a pair of PyRanges
        pyranges.PyRanges.apply_chunks: apply a row-based function to a PyRanges in parallel

        Note
        ----

        apply_chunks will only lead to speedups on large datasets or slow-running functions. Using
        it with nb_cpu=1 is pointless; use apply instead.

        Examples
        --------

        >>> gr = pr.from_dict({"Chromosome": [1, 1, 1], "Start": [2, 3, 5], "End": [9, 4, 6]})
        >>> gr
        +--------------+-----------+-----------+
        |   Chromosome |     Start |       End |
        |   (category) |   (int32) |   (int32) |
        |--------------+-----------+-----------|
        |            1 |         2 |         9 |
        |            1 |         3 |         4 |
        |            1 |         5 |         6 |
        +--------------+-----------+-----------+
        Unstranded PyRanges object has 3 rows and 3 columns from 1 chromosomes.
        For printing, the PyRanges was sorted on Chromosome.

        >>> gr.apply_chunks(
        ... lambda df, **kwargs: list(df.End + kwargs["add"]), nb_cpu=1, add=1000)
        {'1': [[1009, 1004, 1006]]}
        """

        kwargs.update(kwargs.get("kwargs", {}))
        kwargs = fill_kwargs(kwargs)

        result = pyrange_apply_chunks(f, self, as_pyranges, kwargs)

        return result


    def apply_pair(self,
                   other,
                   f,
                   strandedness=None,
                   as_pyranges=True,
                   **kwargs):

        """Apply a function to a pair of PyRanges.

        The function is applied to each chromosome or chromosome/strand pair found in at least one
        of the PyRanges.

        Parameters
        ----------
        f : function
            Row-based or associative function to apply on the DataFrames.

        as_pyranges : bool, default False

            Whether to return as a PyRanges or dict. If `f` does not return a DataFrame valid for
            PyRanges, `as_pyranges` must be False.

        nb_cpu: int, default 1

            How many cpus to use. Can at most use 1 per chromosome or chromosome/strand tuple.
            Will only lead to speedups on large datasets.

        **kwargs
            Additional keyword arguments to pass as keyword arguments to `f`

        Returns
        -------
        dict of lists
            Result of applying f to each partition of the DataFrames in the PyRanges.

        See also
        --------

        pyranges.PyRanges.apply_pair: apply a function to a pair of PyRanges
        pyranges.PyRanges.apply_chunks: apply a row-based function to a PyRanges in parallel
        pyranges.iter: iterate over two or more PyRanges

        Note
        ----

        This is the function used internally to carry out almost all comparison functions in
        PyRanges.

        Examples
        --------

        >>> gr = pr.data.chipseq()
        >>> gr2 = pr.data.chipseq_background()

        >>> gr.apply_pair(gr2, pr.methods.intersection._intersection) # same as gr.intersect(gr2)
        +--------------+-----------+-----------+------------+-----------+--------------+
        | Chromosome   |     Start |       End | Name       |     Score | Strand       |
        | (category)   |   (int32) |   (int32) | (object)   |   (int64) | (category)   |
        |--------------+-----------+-----------+------------+-----------+--------------|
        | chr1         | 226987603 | 226987617 | U0         |         0 | +            |
        | chr8         |  38747236 |  38747251 | U0         |         0 | -            |
        | chr15        |  26105515 |  26105518 | U0         |         0 | +            |
        +--------------+-----------+-----------+------------+-----------+--------------+
        Stranded PyRanges object has 3 rows and 6 columns from 3 chromosomes.
        For printing, the PyRanges was sorted on Chromosome and Strand.

        >>> f1 = pr.data.f1()
        >>> f1
        +--------------+-----------+-----------+------------+-----------+--------------+
        | Chromosome   |     Start |       End | Name       |     Score | Strand       |
        | (category)   |   (int32) |   (int32) | (object)   |   (int64) | (category)   |
        |--------------+-----------+-----------+------------+-----------+--------------|
        | chr1         |         3 |         6 | interval1  |         0 | +            |
        | chr1         |         8 |         9 | interval3  |         0 | +            |
        | chr1         |         5 |         7 | interval2  |         0 | -            |
        +--------------+-----------+-----------+------------+-----------+--------------+
        Stranded PyRanges object has 3 rows and 6 columns from 1 chromosomes.
        For printing, the PyRanges was sorted on Chromosome and Strand.

        >>> f2 = pr.data.f2()
        >>> f2
        +--------------+-----------+-----------+------------+-----------+--------------+
        | Chromosome   |     Start |       End | Name       |     Score | Strand       |
        | (category)   |   (int32) |   (int32) | (object)   |   (int64) | (category)   |
        |--------------+-----------+-----------+------------+-----------+--------------|
        | chr1         |         1 |         2 | a          |         0 | +            |
        | chr1         |         6 |         7 | b          |         0 | -            |
        +--------------+-----------+-----------+------------+-----------+--------------+
        Stranded PyRanges object has 2 rows and 6 columns from 1 chromosomes.
        For printing, the PyRanges was sorted on Chromosome and Strand.

        >>> f1.apply_pair(f2, lambda df, df2: (len(df), len(df2)), as_pyranges=False)
        {('chr1', '+'): (2, 2), ('chr1', '-'): (1, 2)}

        """

        kwargs.update({"strandedness": strandedness})
        kwargs.update(kwargs.get("kwargs", {}))
        kwargs = fill_kwargs(kwargs)

        result = pyrange_apply(f, self, other, **kwargs)

        if not as_pyranges:
            return result
        else:
            return PyRanges(result)

    def copy(self):

        return self.apply(lambda df: df.copy(deep=True))

    # def eval(self, eval_cmd, strand=True, as_pyranges=True, **kwargs):

    #     f = lambda df: eval(eval_cmd)

    #     kwargs = fill_kwargs(kwargs)

    #     result = pyrange_apply_single(f, self, strand, kwargs)

    #     if not as_pyranges:
    #         return result
    #     else:
    #         return PyRanges(result)

    def overlap(self, other, **kwargs):

        # print("how:", kwargs["how"])
        kwargs["sparse"] = {"self": False, "other": True}
        kwargs["how"] = kwargs.get("how", "first")
        kwargs = fill_kwargs(kwargs)
        # print("how:", kwargs["how"])

        dfs = pyrange_apply(_overlap, self, other, **kwargs)

        # if kwargs.get("return_indexes"):
        #     return dfs
        # else:
        return pr.PyRanges(dfs)

    # # TODO: use subtract code here instead, easier
    # def no_overlap(self, other, **kwargs):

    #     kwargs = fill_kwargs(kwargs)
    #     kwargs["invert"] = True
    #     kwargs["sparse"] = {"self": False, "other": True}

    #     # if kwargs["strandedness"] in ["same", "opposite"]:
    #     #     kwargs["strandedness"] = {
    #     #         "same": "opposite",
    #     #         "opposite": "same"
    #     #     }[kwargs["strandedness"]]
    #     dfs = pyrange_apply(_overlap, self, other, **kwargs)

    #     return PyRanges(dfs)

    def nearest(self, other, **kwargs):

        from pyranges.methods.nearest import _nearest

        kwargs = fill_kwargs(kwargs)
        if kwargs.get("how") in "upstream downstream".split():
            assert other.stranded, "If doing upstream or downstream nearest, other pyranges must be stranded"

        dfs = pyrange_apply(_nearest, self, other, **kwargs)

        return PyRanges(dfs)


    # @profile
    def k_nearest(self, other, k=1, **kwargs):

        from pyranges.methods.k_nearest import _nearest
        from sorted_nearest import get_all_ties, get_different_ties

        kwargs = fill_kwargs(kwargs)
        kwargs["stranded"] = self.stranded and other.stranded

        overlap = kwargs.get("overlap", True)
        ties = kwargs.get("ties", False)

        self = pr.PyRanges({k: v.copy() for k, v in self.dfs.items()})

        try: # if k is an array
            k = k.values
        except:
            pass

        self.__k__ = k
        self.__IX__ = np.arange(len(self))


        # from time import time
        # start = time()
        dfs = pyrange_apply(_nearest, self, other, **kwargs)
        # end = time()
        # print("nearest", end - start)

        nearest = PyRanges(dfs)
        # nearest.msp()
        # raise
        # print("nearest len", len(nearest))

        if not overlap:
            # self = self.drop(like="__k__|__IX__")
            result = nearest#.drop(like="__k__|__IX__")
        else:
            from collections import defaultdict
            overlap_kwargs = {k: v for k, v in kwargs.items()}
            # print("kwargs ties:", kwargs.get("ties"))
            overlap_kwargs["how"] = defaultdict(lambda: None, {"first": "first", "last": "last"})[kwargs.get("ties")]
            # start = time()
            overlaps = self.join(other, **overlap_kwargs)
            # end = time()
            # print("overlaps", end - start)
            overlaps.Distance = 0
            # print("overlaps len", len(overlaps))

            result = pr.concat([overlaps, nearest])

        if not len(result):
            return pr.PyRanges()
        # print(result)
        # print(overlaps.drop(like="__").df)
        # raise

        # start = time()
        new_result = {}
        if ties in ["first", "last"]:
            # method = "tail" if ties == "last" else "head"
            # keep = "last" if ties == "last" else "first"

            for c, df in result:
                # start = time()
                # print(c)
                # print(df)

                df = df.sort_values(["__IX__", "Distance"])
                grpby = df.groupby("__k__", sort=False)
                dfs = []
                for k, kdf in grpby:
                    # print("k", k)
                    # print(kdf)
                    # dist_bool = ~kdf.Distance.duplicated(keep=keep)
                    # print(dist_bool)
                    # kdf = kdf[dist_bool]
                    grpby2 = kdf.groupby("__IX__", sort=False)
                    # f = getattr(grpby2, method)
                    _df = grpby2.head(k)
                    # print(_df)
                    dfs.append(_df)
                # raise

                if dfs:
                    new_result[c] = pd.concat(dfs)
                # print(new_result[c])
        elif ties == "different" or not ties:
            for c, df in result:

                # print(df)

                if df.empty:
                    continue
                dfs = []

                df = df.sort_values(["__IX__", "Distance"])
                grpby = df.groupby("__k__", sort=False)

                # for each index
                # want to keep until we have k
                # then keep all with same distance
                for k, kdf in grpby:
                    # print("kdf " * 10)
                    # print("k " * 5, k)
                    # print(kdf["__IX__ Distance".split()])
                    # print(kdf.dtypes)
                    # print(kdf.index.dtypes)
                    # if ties:
                    if ties:
                        lx = get_different_ties(kdf.index.values, kdf.__IX__.values, kdf.Distance.astype(np.int64).values, k)
                    else:
                        lx = get_all_ties(kdf.index.values, kdf.__IX__.values, kdf.Distance.astype(np.int64).values, k)
                    # print(lx)


                    # else:
                    #     lx = get_all_ties(kdf.index.values, kdf.__IX__.values, kdf.Distance.astype(np.int64).values, k)
                    _df = kdf.reindex(lx)
                    # print("_df", _df)
                    dfs.append(_df)

                if dfs:
                    new_result[c] = pd.concat(dfs)

        result = pr.PyRanges(new_result)

        if not result.__IX__.is_monotonic:
            result = result.sort("__IX__")

        result = result.drop(like="__IX__|__k__")

        self = self.drop(like="__k__|__IX__")

        def prev_to_neg(df, kwargs):

            strand = df.Strand.iloc[0] if "Strand" in df else "+"

            suffix = kwargs["suffix"]

            bools = df["End" + suffix] < df.Start
            if not strand == "+":
                bools = ~bools

            df.loc[bools, "Distance"] = -df.loc[bools, "Distance"]
            return df

        # print(result)
        result = result.apply(prev_to_neg, suffix=kwargs["suffix"])
        # print(result)

        # end = time()
        # print("final stuff", end - start)

        return result


    def intersect(self, other, **kwargs):

        kwargs = fill_kwargs(kwargs)
        kwargs["sparse"] = {"self": False, "other": True}

        dfs = pyrange_apply(_intersection, self, other, **kwargs)

        return PyRanges(dfs)

    def set_intersect(self, other, **kwargs):

        kwargs = fill_kwargs(kwargs)
        strandedness = kwargs["strandedness"]
        strand = True if strandedness else False
        self_clusters = self.merge(strand=strand, **kwargs)
        other_clusters = other.merge(strand=strand, **kwargs)
        dfs = pyrange_apply(_intersection, self_clusters, other_clusters,
                            **kwargs)

        return PyRanges(dfs)

    def set_union(self, other, **kwargs):

        kwargs = fill_kwargs(kwargs)
        strandedness = kwargs["strandedness"]
        strand = True if strandedness else False

        if not strand:
            self = self.unstrand()
            other = other.unstrand()

        gr = pr.concat([self, other], strand)

        gr = gr.merge(strand=strand, **kwargs)

        return gr

    def subtract(self, other, **kwargs):

        from pyranges.methods.subtraction import _subtraction

        kwargs["sparse"] = {"self": False, "other": True}
        kwargs = fill_kwargs(kwargs)
        strandedness = kwargs["strandedness"]

        strand = True if strandedness else False
        other_clusters = other.merge(strand=strand, **kwargs)

        result = pyrange_apply(_subtraction, self, other_clusters, **kwargs)

        return PyRanges(result)

    def join(self, other, **kwargs):

        from pyranges.methods.join import _write_both

        slack = kwargs.get("slack")
        if slack:
            self.Start__slack = self.Start
            self.End__slack = self.End

            self = self.slack(slack)

        if "suffix" in kwargs:
            suffixes = "", kwargs["suffix"]
            kwargs["suffixes"] = suffixes

        kwargs = fill_kwargs(kwargs)

        if "new_pos" in kwargs:
            if kwargs["new_pos"] in "intersection union".split():
                suffixes = kwargs.get("suffixes")
                assert suffixes is not None, "Must give two non-empty suffixes when using new_pos with intersection or union."
                assert suffixes[0], "Must have nonempty first suffix when using new_pos with intersection or union."
                assert suffixes[1], "Must have nonempty second suffix when using new_pos with intersection or union."

        # def get_items_dtypes(s):

        #     columns = s.columns
        #     dtypes = (s.dfs.values())
        how = kwargs.get("how")

        if how in ["left", "outer"]:
            kwargs["example_header_other"] = other.head(1).df
        if how in ["right", "outer"]:
            kwargs["example_header_self"] = self.head(1).df


        dfs = pyrange_apply(_write_both, self, other, **kwargs)

        gr = PyRanges(dfs)

        if slack:
            gr.Start = gr.Start__slack
            gr.End = gr.End__slack
            gr = gr.drop(like="(Start|End).*__slack")

        new_position = kwargs.get("new_pos")
        if new_position:
            gr = gr.new_position(new_pos=new_position, suffixes=kwargs["suffixes"])

        return gr

    def count_overlaps(self, other, **kwargs):

        kwargs = fill_kwargs(kwargs)

        from pyranges.methods.coverage import _number_overlapping
        counts = pyrange_apply(_number_overlapping, self, other, **kwargs)

        return pr.PyRanges(counts)

    def coverage(self, other, **kwargs):

        kwargs = fill_kwargs(kwargs)

        counts = self.count_overlaps(other, keep_nonoverlapping=True, **kwargs)

        strand = True if kwargs["strandedness"] else False
        other = other.merge(count=True, strand=strand)

        from pyranges.methods.coverage import _coverage

        # print(counts)
        counts = pr.PyRanges(pyrange_apply(_coverage, counts, other, **kwargs))
        # print("counts" * 100)
        # print(counts)

        return counts


    def insert(self, other, loc=None):

        """Add one or more columns to the PyRanges.

        Parameters
        ----------
        other : array, matrix, Series or DataFrame
            Data to insert into the PyRanges. `other` must have the same length as the PyRanges.

        loc : int, default None, i.e. after last column of PyRanges.
            Insertion index.

        Returns
        -------
        PyRanges
            A copy of the PyRanges with the column(s) inserted starting at `loc`.

        Note
        ----

        Column(s) from arrays and matrixes are labeled with a numerical ID.

        Examples
        --------

        >>> gr = pr.random(4)
        >>> gr
        +--------------+-----------+-----------+--------------+
        | Chromosome   |     Start |       End | Strand       |
        | (category)   |   (int32) |   (int32) | (category)   |
        |--------------+-----------+-----------+--------------|
        | chr10        |  89739541 |  89739641 | +            |
        | chr10        |  40294130 |  40294230 | +            |
        | chr11        |  72039494 |  72039594 | +            |
        | chr14        |    374564 |    374664 | +            |
        +--------------+-----------+-----------+--------------+
        Stranded PyRanges object has 4 rows and 4 columns from 3 chromosomes.
        For printing, the PyRanges was sorted on Chromosome and Strand.

        >>> s = pd.Series(data = [1, 3, 3, 7], name="Column")
        >>> gr.insert(s)
        +--------------+-----------+-----------+--------------+-----------+
        | Chromosome   |     Start |       End | Strand       |    Column |
        | (category)   |   (int32) |   (int32) | (category)   |   (int64) |
        |--------------+-----------+-----------+--------------+-----------|
        | chr10        |  89739541 |  89739641 | +            |         1 |
        | chr10        |  40294130 |  40294230 | +            |         3 |
        | chr11        |  72039494 |  72039594 | +            |         3 |
        | chr14        |    374564 |    374664 | +            |         7 |
        +--------------+-----------+-----------+--------------+-----------+
        Stranded PyRanges object has 4 rows and 5 columns from 3 chromosomes.
        For printing, the PyRanges was sorted on Chromosome and Strand.

        """

        # TODO: need to split dataframes/series/arrays/matrixes and put in dicts
        #       see attr.py for splitting code

        self = self.copy()

        if isinstance(other, (pd.Series, pd.DataFrame)):
            assert len(other) == len(self), "Pandas Series or DataFrame must be same length as PyRanges!"

            if isinstance(other, pd.Series):
                if not other.name:
                    i = 0
                    while str(i) in self:
                        i += 1
                    other.name = str(i)
                
                setattr(self, other.name, other)
                

            if isinstance(other, pd.DataFrame):
                for c in other:
                    setattr(self, c, other[c])

        elif isinstance(other, dict) and other:

            columns = next(iter(other.values())).columns

            ds = []
            for c in columns:
                ds.append({k: v[c] for k, v in other.items()})

            for c, d in zip(columns, ds):
                setattr(self, str(c), d)

        return self



    # def insert(self, other, col, **kwargs):

    #     from pyranges.methods.insert import _insert

    #     kwargs["columns"] = col
    #     kwargs = fill_kwargs(kwargs)
    #     dfs = pyrange_apply(_insert, self, other, **kwargs)

    #     return PyRanges(dfs)

    def split(self, strand=None, **kwargs):

        if strand is None:
            strand = self.stranded

        kwargs = fill_kwargs(kwargs)

        from pyranges.methods.split import _split
        df = pyrange_apply_single(_split, self, strand, kwargs)

        return pr.PyRanges(df)


    def cluster(self, strand=None, by=None, **kwargs):

        if strand is None:
            strand = self.stranded

        kwargs = fill_kwargs(kwargs)

        kwargs["sparse"] = {"self": False}

        _stranded = self.stranded
        if not strand and _stranded:
            # print(" WOOO " * 100)
            self.Strand2 = self.Strand
            self = self.unstrand()

        if not by:
            from pyranges.methods.cluster import _cluster
            df = pyrange_apply_single(_cluster, self, strand, kwargs)
        else:
            from pyranges.methods.cluster import _cluster_by
            kwargs["by"] = by
            df = pyrange_apply_single(_cluster_by, self, strand, kwargs)

        gr = PyRanges(df)

        # each cluster got same ids (0 to len). Need to make unique!
        new_dfs = {}
        first = True
        max_id = 0
        for k, v in gr.items():
            if first:
                max_id = v.Cluster.max()
                new_dfs[k] = v
                first = False
                continue

            v.loc[:, "Cluster"] += max_id
            max_id = v.Cluster.max()
            new_dfs[k] = v

        if not strand and _stranded:
            # print(" wooo " * 100)
            # print(new_dfs)
            new_dfs = {
                k: d.rename(columns={"Strand2": "Strand"})
                for k, d in new_dfs.items()
            }
            # print(new_dfs)

        self = PyRanges(new_dfs)

        return self

    def new_position(self, new_pos, strand=None, **kwargs):

        from pyranges.methods.new_position import _new_position

        kwargs["sparse"] = {"self": False}
        kwargs["new_pos"] = new_pos
        kwargs = fill_kwargs(kwargs)

        if strand is None:
            strand = self.stranded

        dfs = pyrange_apply_single(_new_position, self, strand, kwargs)

        return pr.PyRanges(dfs)

    def merge(self, strand=None, count=False, **kwargs):

        if strand is None:
            strand = self.stranded

        if not ("by" in kwargs):
            kwargs["sparse"] = {"self": True}
            from pyranges.methods.merge import _merge
            df = pyrange_apply_single(_merge, self, strand, kwargs)
        else:
            kwargs["sparse"] = {"self": False}
            from pyranges.methods.merge import _merge_by
            df = pyrange_apply_single(_merge_by, self, strand, kwargs)

        if not count:
            df = {k: v.drop("Count", axis=1) for k, v in df.items()}

        return PyRanges(df)

    def window(self, window_size, strand=None, **kwargs):

        from pyranges.methods.windows import _windows

        if strand is None:
            strand = self.stranded

        kwargs["sparse"] = {"self": False}
        kwargs["window_size"] = window_size

        df = pyrange_apply_single(_windows, self, strand, kwargs)

        return PyRanges(df)

    def tile(self, tile_size, strand=None, **kwargs):

        from pyranges.methods.windows import _tiles

        if strand is None:
            strand = self.stranded

        kwargs["sparse"] = {"self": False}
        kwargs["tile_size"] = tile_size

        df = pyrange_apply_single(_tiles, self, strand, kwargs)

        return PyRanges(df)

    def subset(self, function, strand=None, **kwargs):

        kwargs = fill_kwargs(kwargs)

        if strand is None:
            strand = self.stranded

        if self.stranded and not strand:
            self = self.unstrand()

        result = pyrange_apply_single(function, self, strand, kwargs)

        if not result:
            return pr.PyRanges()

        first_result = next(iter(result.values()))

        assert first_result.dtype == bool, "result of subset function must be bool, but is {}".format(
            first_result.dtype)

        return self[result]

    def assign(self, col, function, strand=None, **kwargs):

        if strand is None:
            strand = self.stranded

        kwargs = fill_kwargs(kwargs)

        result = pyrange_apply_single(function, self, strand, kwargs)

        first_result = next(iter(result.values()))

        assert isinstance(
            first_result, pd.Series
        ), "result of assign function must be Series, but is {}".format(
            type(first_result))

        # do a deepcopy of object
        new_self = pr.PyRanges({k: v.copy() for k, v in self.items()})
        new_self.__setattr__(col, result)

        return new_self

    def to_example(self, nrows=10):

        nrows_half = int(min(nrows, len(self))/2)

        if nrows < len(self):
            first = self.head(nrows_half)
            last = self.tail(nrows_half)
            example = pr.concat([first, last])
        else:
            example = self

        d = {c: list(getattr(example, c)) for c in example.columns}

        return d

    def to_rle(self, value_col=None, strand=None, rpm=False, nb_cpu=1):

        if strand is None:
            strand = self.stranded

        from pyranges.methods.to_rle import _to_rle

        return _to_rle(self, value_col, strand=strand, rpm=rpm, nb_cpu=nb_cpu)



    def slack(self, slack):

        if isinstance(slack, dict):
            assert self.stranded, "PyRanges must be stranded to add 5/3-end specific slack."

        kwargs = fill_kwargs({"slack": slack})

        prg = PyRanges(
            pyrange_apply_single(_slack, self, self.stranded, kwargs))

        return prg


    def five_end(self, slack=0):

        assert self.stranded, "Need stranded pyrange to find 5'."
        kwargs = fill_kwargs({"slack": slack})
        return PyRanges(
            pyrange_apply_single(_tss, self, self.stranded, kwargs))

    def three_end(self, slack=0):

        assert self.stranded, "Need stranded pyrange to find 3'."
        kwargs = fill_kwargs({"slack": slack})
        return PyRanges(
            pyrange_apply_single(_tes, self, self.stranded, kwargs))

    def sort(self, by=None, **kwargs):

        from pyranges.methods.sort import _sort
        kwargs["sparse"] = {"self": False}
        if by:
            kwargs["by"] = by
        kwargs = fill_kwargs(kwargs)
        return PyRanges(
            pyrange_apply_single(_sort, self, self.stranded, kwargs))

    def drop_duplicate_positions(self, strand=None, **kwargs):

        from pyranges.methods.drop_duplicates import _drop_duplicate_positions
        if strand is None:
            strand = self.stranded

        kwargs["sparse"] = {"self": False}
        kwargs = fill_kwargs(kwargs)
        kwargs["strand"] = strand and self.stranded
        return PyRanges(
            pyrange_apply_single(_drop_duplicate_positions, self, strand,
                                 kwargs))

    def keys(self):
        return natsorted(self.dfs.keys())

    @property
    def columns(self):
        """Return the list of column names in the dataframes."""

        columns = [list(df.columns) for df in self.values()]
        if not all([c == columns[0] for c in columns[1:]]):
            print("Columns differ between dataframes:")
            for k, df in self:
                print(k, df.columns)

            raise Exception()

        if columns:
            return columns[0]
        else:
            return []

    @property
    def dtypes(self):
        """Return the dtypes."""

        df = next(iter(self.dfs.values()))

        return df.dtypes


    def set_columns(self, value):
        assert len(value) == len(
            self.columns), "New and old columns must be same length"

        def _columns(df):
            df.columns = value
            return df

        return pr.PyRanges(
            pyrange_apply_single(
                _columns,
                self,
                strand=None,
                kwargs={"sparse": {
                    "self": False
                }}))

    def drop(self, drop=None, like=None):
        """Drop column(s) from the PyRanges object.

        If no arguments are given, all the columns except Chromosome, Start, End and Strand are
        dropped. To drop Strand, the drop_strand argument needs to be given.
        """

        from pyranges.methods.drop import _drop
        return _drop(self, drop, like)

    @property
    def stranded(self):
        keys = self.keys()
        # print(keys)
        # print(not(len(keys)))
        if not len(keys):
            # so that stranded ops work with empty dataframes
            return True

        key = keys[0]
        # print("isinstance " * 10, isinstance(key, tuple))

        return isinstance(key, tuple)

    @property
    def strands(self):

        if not self.stranded:
            raise Exception("PyRanges not stranded!")

        return natsorted(set([k[1] for k in self.keys()]))

    @property
    def chromosomes(self):

        if self.stranded:
            return natsorted(set([k[0] for k in self.keys()]))
        else:
            return natsorted(set([k for k in self.keys()]))

    def items(self):

        return natsorted([(k, df) for (k, df) in self.dfs.items()])

    def values(self):

        return [df for k, df in self.items() if not df.empty]

    def unstrand(self):

        if not self.stranded:
            return self

        gr = pr.concat([self["+"], self["-"]])

        gr = gr.apply(lambda df: df.drop("Strand", axis=1).reset_index(drop=
                                                                       True))

        return pr.PyRanges(gr.dfs)

    @property
    def df(self):

        return self.as_df()

    @property
    def empty(self):
        return len(self) == 0

    def as_df(self):

        if len(self) == 0:
            return pd.DataFrame()
        elif len(self) == 1:
            return self.values()[0]
        else:
            return pd.concat(self.values()).reset_index(drop=True)

    def lengths(self, as_dict=False):


        if as_dict:
            if not len(self):
                return {}
            lengths = {}
            for k, df in self.items():
                lengths[k] = df.End - df.Start

            return lengths
        else:
            _lengths = []
            if not len(self):
                return np.array(_lengths, dtype=int)
            for _, df in self:
                lengths = df.End - df.Start
                _lengths.append(lengths)

            return pd.concat(_lengths).reset_index(drop=True)

    def summary(self):

        from pyranges.methods.summary import _summary

        return _summary(self)

    def to_csv(self, path=None, sep=",", header=True, compression="infer", chain=False):
        from pyranges.out import _to_csv
        result = _to_csv(
            self, path, sep=sep, header=header, compression=compression)
        if path and chain:
            return self
        else:
            return result

    def to_bed(self, path=None, keep=True, compression="infer", chain=False):
        from pyranges.out import _to_bed

        result = _to_bed(self, path, keep=keep, compression=compression)

        if path and chain:
            return self
        else:
            return result

    def to_gtf(self, path=None, compression="infer", chain=False):
        from pyranges.out import _to_gtf

        result = _to_gtf(self, path, compression=compression)

        if path and chain:
            return self
        else:
            return result

    def to_gff3(self, path=None, compression="infer", chain=False):
        from pyranges.out import _to_gff3

        result = _to_gff3(self, path, compression=compression)

        if path and chain:
            return self
        else:
            return result


    def to_bigwig(self, path, chromosome_sizes, rpm=True, divide_by=None, value_col=None):
        from pyranges.out import _to_bigwig

        _to_bigwig(self, path, chromosome_sizes, rpm, divide_by, value_col)

        return self

    @property
    def length(self):

        return int(self.lengths(as_dict=False).sum())


    def head(self, n=8):
        subsetter = np.zeros(len(self), dtype=np.bool)
        subsetter[:n] = True
        return self[subsetter]

    def tail(self, n=8):
        subsetter = np.zeros(len(self), dtype=np.bool)
        subsetter[(len(self) - n):] = True
        return self[subsetter]

    def sample(self, n=8):
        sample = np.random.choice(len(self), size=n, replace=False)
        subsetter = np.zeros(len(self), dtype=np.bool)
        subsetter[sample] = True
        return self[subsetter]

    def print(self, n=8, merge_position=False, sort=False, formatting=None, chain=False):

        s = tostring(
            self,
            n=n,
            merge_position=merge_position,
            sort=sort,
            formatting=formatting)

        print(s)

        if chain:
            return self


    def mp(self, n=8, formatting=None):

        print(tostring(self, n=n, merge_position=True, formatting=formatting))

    def sp(self, n=30, formatting=None):

        print(tostring(self, n=n, sort=True, formatting=formatting))

    def msp(self, n=30, formatting=None):

        print(
            tostring(
                self,
                n=n,
                merge_position=True,
                sort=True,
                formatting=formatting))

    def rp(self):

        print(self.dfs)

    def pc(self, n=8, formatting=None):

        print(tostring(self, n=n, formatting=formatting))

        return self

    def mpc(self, n=8, formatting=None):

        print(tostring(self, n=n, merge_position=True, formatting=formatting))

        return self

    def spc(self, n=30, formatting=None):

        print(tostring(self, n=n, sort=True, formatting=formatting))

        return self

    def mspc(self, n=30, formatting=None):

        print(
            tostring(
                self,
                n=n,
                merge_position=True,
                sort=True,
                formatting=formatting))

        return self

    def rpc(self):

        print(self.dfs)

        return self

    def __getstate__(self):
        return self.dfs

    def __setstate__(self, d):
        self.__dict__["dfs"] = d
