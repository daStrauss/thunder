from numpy import in1d, zeros, array, size, float64
from scipy.io import loadmat
from scipy.stats import ttest_ind
from sklearn.naive_bayes import GaussianNB
from sklearn import cross_validation


class MassUnivariateClassifier(object):
    """Class for loading and classifying with classifiers"""

    def __init__(self, paramfile):
        """Initialize classifier using parameters derived from a Matlab file,
        or a python dictionary. At a minimum, must contain a "labels" field, with the
        label to classify at each time point. Can additionally include fields for
        "features" (which feature was present at each time point)
        and "samples" (which sample was present at each time point)

        :param paramfile: string of filename, or dictionary, containing parameters
        """
        if type(paramfile) is str:
            params = loadmat(paramfile, squeeze_me=True)
        elif type(paramfile) is dict:
            params = paramfile
        else:
            raise TypeError("Parameters for classification must be provided as string with file location, or dictionary")

        self.labels = params['labels']

        if 'features' in params:
            self.features = params['features']
            self.nfeatures = len(list(set(self.features.flatten())))
            self.samples = params['samples']
            self.sampleids = list(set(self.samples.flatten()))
            self.nsamples = len(self.sampleids)
        else:
            self.nfeatures = 1
            self.nsamples = len(self.labels)

    @staticmethod
    def load(paramfile, classifymode, cv=0):
        return CLASSIFIERS[classifymode](paramfile, cv)

    def get(self, x, set=None):
        pass

    def classify(self, data, featureset=None):
        """Do the classification on an RDD using a map

        :param data: RDD of data points as key value pairs
        :param featureset: list of lists containing the features to use
        :return: perf: RDD of key value pairs with classification performance
        """

        if self.nfeatures == 1:
            perf = data.mapValues(lambda x: [self.get(x)])
        else:
            if featureset is None:
                featureset = [[self.features[0]]]
            for i in featureset:
                assert array([item in i for item in self.features]).sum() != 0, "Feature set invalid"
            perf = data.mapValues(lambda x: map(lambda i: self.get(x, i), featureset))

        return perf


class GaussNaiveBayesClassifier(MassUnivariateClassifier):
    """Class for gaussian naive bayes classification"""

    def __init__(self, paramfile, cv):
        """Create classifier

        :param paramfile: string of filename or dictionary with parameters (see MassUnivariateClassifier)
        :param cv: number of cross validation folds (none if 0)
        """
        MassUnivariateClassifier.__init__(self, paramfile)

        self.cv = cv
        self.func = GaussianNB()

    def get(self, x, featureset=None):
        """Compute classification performance"""

        y = self.labels
        if self.nfeatures == 1:
            X = zeros((self.nsamples, 1))
            X[:, 0] = x
        else:
            X = zeros((self.nsamples, size(featureset)))
            for i in range(0, self.nsamples):
                inds = (self.samples == self.sampleids[i]) & (in1d(self.features, featureset))
                X[i, :] = x[inds]

        if self.cv > 0:
            return cross_validation.cross_val_score(self.func, X, y, cv=self.cv).mean()
        else:
            ypred = self.func.fit(X, y).predict(X)
            return array(y == ypred).mean()


class TTestClassifier(MassUnivariateClassifier):
    """Class for t test classification"""

    def __init__(self, paramfile, cv):
        """Create classifier

        :param paramfile: string of filename or dictionary with parameters (see MassUnivariateClassifer)
        """
        MassUnivariateClassifier.__init__(self, paramfile)

        self.func = ttest_ind
        unique = list(set(list(self.labels)))
        if len(unique) != 2:
            raise TypeError("Only two types of labels allowed for t-test classificaiton")
        if unique != set((0, 1)):
            self.labels = array(map(lambda i: 0 if i == unique[0] else 1, self.labels))

    def get(self, x, featureset=None):
        """Compute t-statistic

        :param x: vector of signals to use in classification
        :param featureset: which features to test"""

        if (self.nfeatures > 1) & (size(featureset) > 1):
            X = zeros((self.nsamples, size(featureset)))
            for i in range(0, size(featureset)):
                X[:, i] = x[self.features == featureset[i]]
            return float64(self.func(X[self.labels == 0, :], X[self.labels == 1, :])[0])

        else:
            if self.nfeatures > 1:
                x = x[self.features == featureset]
            return float64(self.func(x[self.labels == 0], x[self.labels == 1])[0])


CLASSIFIERS = {
    'gaussnaivebayes': GaussNaiveBayesClassifier,
    'ttest': TTestClassifier
}
