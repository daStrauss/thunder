from numpy import random, sum, real, argsort, mean, transpose, dot, inner, outer, zeros, shape, sqrt
from scipy.linalg import eig, inv, orth
from pyspark.accumulators import AccumulatorParam


def svd(data, k, meansubtract=1, method="direct", maxiter=20, tol=0.00001):
    """Large-scale singular value decomposition for dense matrices

    Direct method uses an accumulator to distribute and sum outer products
    only efficient when n >> m (tall and skinny)
    requires that n ** 2 fits in memory

    EM method uses an iterative algorithm based on expectation maximization

    TODO: select method automatically based on data dimensions
    TODO: return fractional variance explained by k eigenvectors

    :param data: RDD of data points as key value pairs
    :param k: number of components to recover
    :param method: choice of algorithm, "direct", "em" (default = "direct")
    :param meansubtract: whether or not to subtract the mean

    :return comps: the left k eigenvectors (as array)
    :return latent: the singular values
    :return scores: the right k eigenvectors (as RDD)
    """
    if method == "direct":

        # set up a matrix accumulator
        class MatrixAccumulatorParam(AccumulatorParam):
            def zero(self, value):
                return zeros(shape(value))

            def addInPlace(self, val1, val2):
                val1 += val2
                return val1

        n = data.count()
        m = len(data.first()[1])
        if meansubtract == 1:
            data = data.mapValues(lambda x: x - mean(x))

        # create a variable and method to compute sums of outer products
        global cov
        cov = data.context.accumulator(zeros((m, m)), MatrixAccumulatorParam())

        def outersum(x):
            global cov
            cov += outer(x, x)

        # compute the covariance matrix
        data.map(lambda (_, v): v).foreach(outersum)

        # do local eigendecomposition
        w, v = eig(cov.value / n)
        w = real(w)
        v = real(v)
        inds = argsort(w)[::-1]
        latent = sqrt(w[inds[0:k]]) * sqrt(n)
        comps = transpose(v[:, inds[0:k]])

        # project back into data, normalize by singular values
        scores = data.mapValues(lambda x: inner(x, comps) / latent)

        return scores, latent, comps

    if method == "em":

        n = data.count()
        m = len(data.first()[1])
        if meansubtract == 1:
            data = data.mapValues(lambda x: x - mean(x))

        def outerprod(x):
            return outer(x, x)

        c = random.rand(k, m)
        iter = 0
        error = 100

        # iterative update subspace using expectation maximization
        # e-step: x = (c'c)^-1 c' y
        # m-step: c = y x' (xx')^-1
        while (iter < maxiter) & (error > tol):
            c_old = c
            # pre compute (c'c)^-1 c'
            c_inv = dot(transpose(c), inv(dot(c, transpose(c))))
            premult1 = data.context.broadcast(c_inv)
            # compute (xx')^-1 through a map reduce
            xx = data.map(lambda (_, v): v).map(lambda x: outerprod(dot(x, premult1.value))).sum()
            xx_inv = inv(xx)
            # pre compute (c'c)^-1 c' (xx')^-1
            premult2 = data.context.broadcast(dot(c_inv, xx_inv))
            # compute the new c through a map reduce
            c = data.map(lambda (_, v): v).map(lambda x: outer(x, dot(x, premult2.value))).sum()
            c = transpose(c)

            error = sum(sum((c - c_old) ** 2))
            iter += 1

        # project data into subspace spanned by columns of c
        # use standard eigendecomposition to recover an orthonormal basis
        c = transpose(orth(transpose(c)))
        premult3 = data.context.broadcast(c)
        cov = data.map(lambda (_, v): v).map(lambda x: dot(x, transpose(premult3.value))).map(lambda x: outerprod(x)).mean()
        w, v = eig(cov)
        w = real(w)
        v = real(v)
        inds = argsort(w)[::-1]
        latent = sqrt(w[inds[0:k]]) * sqrt(n)
        comps = dot(transpose(v[:, inds[0:k]]), c)
        scores = data.mapValues(lambda x: inner(x, comps) / latent)

        return scores, latent, comps
