"""
Utilities for loading and preprocessing data
"""

import pyspark

from numpy import array, mean, cumprod, append, mod, ceil, size, polyfit, polyval, arange, percentile, inf, subtract
from scipy.signal import butter, lfilter


class Dimensions(object):

    def __init__(self, values=[], n=3):
        self.min = tuple(map(lambda i: inf, range(0, n)))
        self.max = tuple(map(lambda i: -inf, range(0, n)))

        for v in values:
            self.merge(v)

    def merge(self, value):
        self.min = tuple(map(min, self.min, value))
        self.max = tuple(map(max, self.max, value))
        return self

    def count(self):
        return tuple(map(lambda x: x + 1, map(subtract, self.max, self.min)))

    def mergedims(self, other):
        self.min = tuple(map(min, self.min, other.min))
        self.max = tuple(map(max, self.max, other.max))
        return self


class DataLoader(object):
    """Class for loading lines of a data file"""

    def __init__(self, nkeys):
        def func(line):
            vec = [float(x) for x in line.split(' ')]
            ts = array(vec[nkeys:])
            keys = tuple(int(x) for x in vec[:nkeys])
            return keys, ts

        self.func = func

    def get(self, y):
        return self.func(y)


class DataPreProcessor(object):
    """Class for preprocessing data"""

    def __init__(self, preprocessmethod):
        if preprocessmethod == "sub":
            func = lambda y: y - mean(y)

        if preprocessmethod == "dff":
            def func(y):
                mnval = mean(y)
                return (y - mnval) / (mnval + 0.1)

        if preprocessmethod == "raw":
            func = lambda x: x

        if preprocessmethod == "dff-percentile":

            def func(y):
                mnval = percentile(y, 20)
                y = (y - mnval) / (mnval + 0.1)   
                return y

        if preprocessmethod == "dff-detrend":

            def func(y):
                mnval = mean(y)
                y = (y - mnval) / (mnval + 0.1)   
                x = arange(1, len(y)+1) 
                p = polyfit(x, y, 1)
                yy = polyval(p, x)
                return y - yy

        if preprocessmethod == "dff-detrendnonlin":

            def func(y):
                mnval = mean(y)
                y = (y - mnval) / (mnval + 0.1)   
                x = arange(1, len(y)+1) 
                p = polyfit(x, y, 5)
                yy = polyval(p, x)
                return y - yy

        if preprocessmethod == "dff-highpass":
            fs = 1
            nyq = 0.5 * fs
            cutoff = (1.0/360) / nyq
            b, a = butter(6, cutoff, "highpass")

            def func(y):
                mnval = mean(y)
                y = (y - mnval) / (mnval + 0.1)
                return lfilter(b, a, y)

        self.func = func

    def get(self, y):
        return self.func(y)


def isrdd(data):
    """ Check whether data is an RDD or not
    :param data: data object (potentially an RDD)
    :return: true (is rdd) or false (is not rdd)
    """
    dtype = type(data)
    if (dtype == pyspark.rdd.RDD) | (dtype == pyspark.rdd.PipelinedRDD):
        return True
    else:
        return False


def getdims(data):
    """Get dimensions of keys; ranges can have arbtirary minima
    and maximum, but they must be contiguous (e.g. the indices of a dense matrix).

    :param data: RDD of data points as key value pairs, or numpy list of key-value tuples
    :return dims: Instantiation of Dimensions class containing the dimensions of the data
    """

    def redfunc(left, right):
        return left.mergedims(right)

    if isrdd(data):
        entry = data.first()[0]
        n = size(entry)
        d = data.map(lambda (k, _): k).mapPartitions(lambda i: [Dimensions(i, n)]).reduce(redfunc)
    else:
        entry = data[0][0]
        rng = range(0, size(entry))
        d = Dimensions()
        if size(entry) == 1:
            distinctvals = list(set(map(lambda x: x[0][0], data)))
        else:
            distinctvals = map(lambda i: list(set(map(lambda x: x[0][i], data))), rng)
        d.max = tuple(map(max, distinctvals))
        d.min = tuple(map(min, distinctvals))

    return d


def subtoind(data, dims):
    """Convert subscript indexing to linear indexing

    :param data: RDD with subscript indices as keys
    :param dims: Array with maximum along each dimension
    :return RDD with linear indices as keys
    """
    def subtoind_inline(k, dimprod):
        return sum(map(lambda (x, y): (x - 1) * y, zip(k[1:], dimprod))) + k[0]
    if size(dims) > 1:
        dimprod = cumprod(dims)[0:-1]
        if isrdd(data):
            return data.map(lambda (k, v): (subtoind_inline(k, dimprod), v))
        else:
            return map(lambda (k, v): (subtoind_inline(k, dimprod), v), data)
    else:
        return data


def indtosub(data, dims):
    """Convert linear indexing to subscript indexing

    :param data: RDD with linear indices as keys
    :param dims: Array with maximum along each dimension
    :return RDD with sub indices as keys
    """
    def indtosub_inline(k, dimprod):
        return tuple(map(lambda (x, y): int(mod(ceil(float(k)/y) - 1, x) + 1), dimprod))

    if size(dims) > 1:
        dimprod = zip(dims, append(1, cumprod(dims)[0:-1]))
        if isrdd(data):
            return data.map(lambda (k, v): (indtosub_inline(k, dimprod), v))
        else:
            return map(lambda (k, v): (indtosub_inline(k, dimprod), v), data)

    else:
        return data


def load(sc, datafile, preprocessmethod="raw", nkeys=3):
    """Load data from a text file with format
    <k1> <k2> ... <t1> <t2> ...
    where <k1> <k2> ... are keys (Int) and <t1> <t2> ... are the data values (Double)
    If multiple keys are provided (e.g. x, y, z), they are converted to linear indexing

    :param sc: SparkContext
    :param datafile: Location of raw data
    :param preprocessmethod: Type of preprocessing to perform ("raw", "dff", "sub")
    :param nkeys: Number of keys per data point
    :return data: RDD of data points as key value pairs
    """

    lines = sc.textFile(datafile)
    loader = DataLoader(nkeys)

    data = lines.map(loader.get)

    if preprocessmethod != "raw":
        preprocessor = DataPreProcessor(preprocessmethod)
        data = data.mapValues(preprocessor.get)

    return data


