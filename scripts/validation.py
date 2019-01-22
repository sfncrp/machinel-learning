from __future__ import division

import nn
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import random as rnd
import utils as u
import json
import metrics

from itertools import product
from tqdm import tqdm


class KFoldCrossValidation(object):
    """
    This class represents a wrapper for the implementation of the classic
    k-fold cross validation algorithm, as described in Deep Learning pag.
    120.

    Attributes
    ----------
    dataset: numpy.ndarray
        the full dataset obtained by stiking the design matrix X with the
        target column vector y

    folds: list
        a list containing nfold chunks of the original dataset

    results: list
        a list containing the generalization assessment measures
        generated by every algorithm's iteration for each fold.

    aggregated_results: dict
        a dictionary containing assessment values and aggregates for each
        metric

    """

    def __init__(self, X, y, neural_net, nfolds=3, shuffle=False, **kwargs):
        """
        The class' constructor.

        Parameters
        ----------
        X: numpy.ndarray
            the design matrix

        y: numpy.ndarray
            the target column vector

        neural_net: nn.NeuralNetwork
            the neural network that has to be cross validated

        nfolds: int
            the number of folds to be applied in the algorithm
            (Default value = 3)

        shuffle: bool
            choosing if the dataset must be shuffled
            (Default value = False)

        kwargs: dict
            a dictionary which contains the parameters for the neural
            network's initialization

        Returns
        -------
        """
        assert X.shape[0] == y.shape[0]

        self.dataset = np.hstack((X, y))
        self.folds = list()
        self.results = list()

        self.fold_results = []

        if shuffle:
            np.random.shuffle(self.dataset)

        self.set_folds(nfolds)
        self.validate(X, y, neural_net, nfolds)

    def set_folds(self, nfolds):
        """
        This function splits the dataset into nfolds folds.

        Parameters
        ----------
        nfolds: int
            the number of folds to be applied in the algorithm

        Returns
        -------
        """
        record_per_fold = int(self.dataset.shape[0] / nfolds)
        low = 0
        high = low + record_per_fold

        for i in np.arange(nfolds):
            self.folds.append(self.dataset[low:high] if i !=
                              nfolds - 1 else self.dataset[low:])

            low = high
            high += record_per_fold

    def validate(self, X, y, neural_net, nfolds, plot_curves=False, **kwargs):
        """
        This function implements the core of the k-fold cross validation
        algorithm. For each fold, the neural network is trained using the
        training set created for that fold, and is tested on the respective
        test set. Finally, the error between the test's target and the
        predicted one is collected.

        Parameters
        ----------
        X. numpy.ndarray
            the design matrix

        y: numpy.ndarray
            the target column vector

        neural_net: nn.NeuralNetwork
            the neural network that has to be cross validated

        nfolds: int
            the number of folds to be applied in the algorithm

        plot_curves: bool
            whether or not to plot the learning curve for each one of the
            cross validation's iterations

        kwargs: dict
            a dictionary which contains the parameters for the neural
            network's initialization

        Returns
        -------
        """
        for i in tqdm(np.arange(nfolds),
                      desc='{}-FOLD CROSS VALIDATION PROGRESS'.format(nfolds)):

            train_set = np.vstack([self.folds[j] for j in np.arange(
                len(self.folds)) if j != i])

            X_train, y_train = np.hsplit(train_set, [X.shape[1]])
            X_va, y_va = np.hsplit(self.folds[i], [X.shape[1]])

            neural_net.train(X_train, y_train, X_va, y_va)

            # assessment = self.model_assessment(X_va, y_va, model=neural_net)
            assessment = {'mse': neural_net.error_per_epochs_va[-1]}
            self.results.append(assessment)
            # self.results.append(loss)

            fold_results = {
                'id_fold': i+1,
                'mse': neural_net.error_per_epochs_va[-1],
                # 'epochs_x': list(np.arange(len(neural_net.error_per_epochs))),
                'error_per_epochs': neural_net.error_per_epochs,
                'error_per_epochs_va': neural_net.error_per_epochs_va,
                'hyperparams': neural_net.get_params()
            }
            if neural_net.task == 'classifier':
                y_pred = neural_net.predict(X_va)
                y_pred = np.round(y_pred)
                bca = metrics.BinaryClassifierAssessment(y_pred, y_va, printing=False)
                fold_results['accuracy'] = bca.accuracy
                fold_results['f1_score'] = bca.f1_score

            if neural_net.task == 'regression':
                # add mean euclidean error
                pass

            self.fold_results.append(fold_results)
            neural_net.reset()

            if plot_curves:
                plt.plot(range(len(neural_net.error_per_epochs)),
                         neural_net.error_per_epochs,
                         label='FOLD {}, VALIDATION ERROR: {}'.
                         format(i, round(assessment['mse'], 2)))

        self.aggregated_results = self.aggregate_assessments()

        if plot_curves:
            plt.title('LEARNING CURVES FOR A {}-FOLD CROSS VALIDATION.\nMEAN '
                      'VALIDATION ERROR {}, VARIANCE {}.'.
                      format(nfolds, round(
                        self.aggregated_results['mse']['mean'], 2),
                        round(self.aggregated_results['mse']['std'], 2)),
                      fontsize=8)
            plt.ylabel('ERROR PER EPOCH')
            plt.xlabel('EPOCHS')
            plt.grid()
            plt.legend(fontsize=8)
            plt.savefig('../images/{}_fold_cross_val_lcs.pdf'.
                        format(nfolds), bbox_inches='tight')
            plt.close()

        return self.aggregated_results

    def model_assessment(self, X_va, y_va, model):
        """
        Computes assessment measures for each fold evaluation.

        Parameters
        ----------
        X_va: numpy.ndarray
            the validation design matrix

        y_va: numpy.ndarray
            the validation target column vector

        model : nn.NeuralNetwork
            the model to use for the validation phase

        Returns
        -------
        assessment : dict
            dictionary with structure { metric: estimated value}.
        """

        assessment = dict()
        y_pred = model.predict(X_va)
        assessment['mse'] = metrics.mse(y_va, y_pred)
        # possibile aggiungere altre metriche al dizionario
        return assessment

    def aggregate_assessments(self):
        """
        Computes aggregation measures for each assessment metric.

        Parameters
        ----------

        Returns
        -------
        out : dict
            dictionary containing folds results and aggregates.
            out = {metric: {'mean': 0, 'std': 0, 'median': 0, 'values': []}}

        """

        metrics = self.results[0].keys()

        out = {metric: {'values': []} for metric in metrics}
        for res in self.results:
            for metric in metrics:
                out[metric]['values'].append(res[metric])

        for metric in metrics:
            out[metric]['mean'] = np.mean(out[metric]['values'])
            out[metric]['std'] = np.std(out[metric]['values'])
            out[metric]['median'] = np.median(out[metric]['values'])

        return out


class ModelSelectionCV(object):
    """
    Model selection using repeated Cross Validation.

    Attributes
    ----------
    grid: HyperGrid or HyperRandomGrid
        a grid of hyperparameters' configurations

    repetitions: int
        the number of times cross validation has to be repeted

    n_iter: int
        a placeholder for the current iteration
    """
    def __init__(self, grid, repetitions=1,
                 fname='../data/model_selection_results.json'):
        """
        The class' constructor.

        Parameters
        ----------
        grid:
            a grid of hyperparameters

        repetitions: int
            cross validation repetitions
            (Default value = 1)

        Returns
        -------
        """
        if grid is not None:
            self.grid = grid
            self.repetitions = repetitions

        self.fname = fname

    def search(self, X_design, y_design, nfolds=3, ntrials=7,
               save_results=True, fname=None, **kwargs):
        """
        This function searches for the best hyperparamenters' configugation
        through a search space of hyperparameters.

        Parameters
        ----------
        X_design: numpy.ndarray
            the design matrix

        y_design: numpy.ndarray
            the column target vector

        nfolds: int
            the number of folds to be applied in the algorithm
            (Default value = 3)

        save_results: bool
            whether or not to save the results as a JSON file
            (Default value = True)

        fname: str
            where to save the results obtained at the end of the searching
            phase
            (Default value = '../data/model_selection_results.json')

        Returns
        -------
        """
        self.n_iter = self.repetitions * len(self.grid)*ntrials

        if fname is None:
            fname = self.fname

        if save_results:
            with open(fname, 'w') as f:
                f.write('{"out": [')

        i = 0

        for rep in tqdm(range(self.repetitions),
                        desc="CROSS VALIDATION'S REPETITION PROGRESS"):
            dataset = np.hstack((X_design, y_design))
            np.random.shuffle(dataset)
            X_design, y_design = np.hsplit(dataset,
                                           [X_design.shape[1]])

            for hyperparams in tqdm(self.grid,
                                    desc='GRID SEARCH {}'
                                    .format(kwargs['par_name']
                                            if 'par_name' in kwargs else '')):
                # instanciate neural network

                for trial in tqdm(range(ntrials), desc="TRIALS"):
                    # repeated inizialization of the net
                    neural_net = nn.NeuralNetwork(X_design, y_design,
                                                  **hyperparams)

                    cross_val = KFoldCrossValidation(
                        X_design, y_design,
                        neural_net, nfolds=nfolds,
                        shuffle=False)

                    i += 1
                    out = dict()
                    out['hyperparams'] = neural_net.get_params()
                    out['errors'] = cross_val.aggregated_results
                    out['fold_results'] = cross_val.fold_results
                    out['id_grid'] = i
                    out['id_trial'] = trial
                    # fold results
                    for res in out['fold_results']:
                        res['id_grid'] = i
                        res['id_trial'] = trial

                if save_results:
                    with open(fname, 'a') as f:
                        json.dump(out, f, indent=4)
                        if i != self.n_iter:
                            f.write(',\n')
                        else:
                            f.write('\n ]}')

    def load_results(self, fname=None):
        """
        This function loads the JSON file which contains the results for
        every hyperparaments' configuration.

        Parameters
        ----------
        fname: str
            the path to the JSON file which contains the results
            (Default value = '../data/model_selection_results.json')

        Returns
        -------
        The file which contains the results.
        """
        if fname is None:
            fname = self.fname
        with open(fname, 'r') as f:
            data = json.load(f)
        return data

    def select_best_hyperparams(self, error='mse', metric='mean', top=1,
                                fname=None):
        """
        Selection of the best hyperparameters

        Parameters
        ----------
        error: str
            error used
            (Default value = 'mse')

        metric: str
            the metric for evaluating the best hyperparameters' configuration
            (Default value = 'mean')

        top: int
            number of best hyperparameters
            (Default value = 1)

        Returns
        -------
        A list containing the values for the best hyperparameters'
        configuration
        """
        if fname is None:
            fname = self.fname
        data = self.load_results(fname=fname)
        errors = [res['errors'][error][metric] for res in data['out']]
        best_indexes = (np.argsort(errors))[:top]

        return list(np.array(data['out'])[best_indexes])

    def select_best_model(self, X_design, y_design, X_va=None, y_va=None,
                          fname=None):
        """
        This function retrains the model with the best hyperparams'
        configuration

        Parameters
        ----------
        X_design: numpy.ndarray
            the design matrix

        y_design: numpy.ndarray
            the target column vector

        fname: str
            the path to the file which contains the results for the best
            hyperparameters' search phase

        Returns
        -------
        The model trained with the best hyperparameters' configuration.
        """
        if fname is None:
            fname = self.fname

        best = self.select_best_hyperparams(top=1, fname=fname)
        best_hyperparams = best[0]['hyperparams']

        neural_net = nn.NeuralNetwork(X_design, y_design,
                                      **best_hyperparams)
        neural_net.train(X_design, y_design, X_va, y_va)

        return neural_net

    def load_results_pandas(self, fname=None, flat=True):
        """ Load grid results in pandas DataFrame format """

        if fname is None:
            fname = self.fname

        grid_results = self.load_results()
        grid_results = grid_results['out']
        result = grid_results[0]

        grid_results_flat = []
        for result in grid_results:

            fold_results = (result['fold_results'])
            fold_results_flat = []
            for res in fold_results:
                fold_results_flat.append(flat_fold_results(res))

            grid_results_flat.extend(fold_results_flat)

        df = pd.DataFrame(grid_results_flat)
        # re-ordering
        df = df[['id_grid', 'id_fold'] +
                [c for c in df if c not in ['id_grid', 'id_fold']]]

        if flat:
            return df2df_flat(df=df)
        else:
            return df


def flat_fold_results(fold_res):
    """ Convert KCrossValidation results to flat format """

    fold_res_flat = dict()
    for info, info_val in fold_res.items():
        if info != 'hyperparams':
            fold_res_flat[info] = info_val

    for par, par_value in fold_res['hyperparams'].items():
        if type(par_value) is not list:
            fold_res_flat[par] = par_value
        else:
            # handle list type parameters
            for i, el in enumerate(par_value):
                if i == 0:
                    # maintain name for first list element
                    fold_res_flat[par] = el
                else:
                    fold_res_flat[par+'_'+str(i)] = el

    fold_res_flat['hyperparams'] = fold_res['hyperparams']
    return fold_res_flat


def df2df_flat(df):
    """ Flat the learning curves in a pandas DataFrame """

    new_rows = []

    for irow in range(df.shape[0]):

        row = df.iloc[irow]

        row_others = row.copy()
        row_others.drop(['error_per_epochs', 'error_per_epochs_va'])

        errors = row['error_per_epochs']

        for i, error in enumerate(errors):
            new_row = row_others.copy()
            new_row['error_per_epochs'] = error
            new_row['error_per_epochs_va'] = row['error_per_epochs_va'][i]
            # new_row['epochs_x'] = row['epochs_x'][i]
            new_rows.append(new_row)

    new_df = pd.DataFrame(new_rows)
    return new_df


class Holdout():
    """ Validation Holdout method """
    def __init__(self, X, y, split_perc=[0.5, 0.25, 0.25]):
        """
        Initialization for the Holdout class

        Parameters
        ----------
        X : numpy.ndarray
        y : numpy.ndarray
        split_perc : list
            split percentages

        Returns
        -------

        """
        df = np.hstack((X, y))
        np.random.shuffle(df)

        p = df.shape[0]
        tr_perc = split_perc[0]
        va_perc = split_perc[1]
        # ts_perc = split_perc[2]

        split_train = int(tr_perc*p)
        split_design = int((tr_perc+va_perc)*p)

        design_set = df[:split_design, :]
        train_set = df[:split_train, :]
        validation_set = df[split_train:split_design, :]
        test_set = df[split_design:, :]

        self.X_design, self.y_design = np.hsplit(design_set, [X.shape[1]])
        self.X_train, self.y_train = np.hsplit(train_set, [X.shape[1]])
        self.X_va, self.y_va = np.hsplit(validation_set, [X.shape[1]])
        self.X_test, self.y_test = np.hsplit(test_set, [X.shape[1]])

    def model_selection(self, grid, plot=False, fpath='../images/'):
        """
        Holdout model selection

        Parameters
        ----------
        grid : instance of HyperRandomGrid class
            hyperparameter grid
        plot : bool
            if plot=True plots the learning curve for each grid parameter

        fpath : str
            path for images storing
        Returns
        -------
        neural network object
        """

        self.fpath = fpath
        params = []
        errors_va = []
        for i, pars in enumerate(grid):

            net = nn.NeuralNetwork(self.X_train, self.y_train, **pars)
            net.train(self.X_train, self.y_train)
            print('trained')
            params.append(net.get_params())
            # assess on validation set
            errors_va.append(
                net.predict(self.X_va, self.y_va)/(self.X_va.shape[0])
            )
            if plot is True:
                u.plot_error(net, fname=fpath
                             + 'learning_curve_{}.png'.format(i))

        # choosing the best hyperparameters
        self.best_index = np.argmin(errors_va)
        best_hyperparams = params[self.best_index]

        # retraining on design set
        net_retrained = nn.NeuralNetwork(hidden_sizes=best_hyperparams
                                         .pop('hidden_sizes'))
        net_retrained.train(self.X_design, self.y_design, **best_hyperparams)

        df_pars = pd.DataFrame(list(grid))
        df_pars['error'] = errors_va

        self.best_hyperparams = best_hyperparams
        self.df_pars = df_pars
        self.model = net_retrained

        return self.model


class HyperGrid():
    """ HyperGrid Class"""

    def __init__(self, param_ranges, size, random=True, seed=None):
        """
        HyperGrid instanciates a random or uniform grid using
        the given parameters ranges.

        The random grid iterator is reset after each use,
        allowing immediate reuse of the same grid.

        Parameters
        ----------
        param_ranges : dict
            dictionary containing ranges interval for each parameter.

        size: int
            size of the grid. For a random grid represent the grid size.
            For a uniform grid is the step size of each dimension.

        random: bool
            choose random grid or random grid
            (Default value = True)

        seed: int
            random seed initialization.

        Returns
        -------

        """
        self.size = size
        self.n = 0  # iterator counter
        if type(param_ranges) is not dict:
            raise TypeError("Insert a dictionary of parameters ranges")
        self.param_ranges = param_ranges
        self.types = self.get_types()
        self.random = random

        if self.random:
            self.next = self.next_random
            if seed is not None:
                # seed inizialization
                self.seed = seed
                rnd.seed(self.seed)
            else:
                # random initialization
                rnd.seed()
                self.seed = rnd.randint(0, 2**32)
                rnd.seed(self.seed)

        else:
            self.next = self.next_uniform
            self.vec_size = size
            self.set_uniform_grid()

        # print('GENERATING AN HYPERPARAMETER GRID OF LENGTH {}'
        #       .format(self.__len__()))

    def get_types(self):
        """
        Get the type of each parameter

        Parameters
        ----------

        Returns
        -------
        types : dict
        dictionary containing each parameter type
        """

        types = dict()
        for par, interval in self.param_ranges.items():
            if (type(interval) is int) or \
               (type(interval) is float) or \
               (type(interval) is str):
                types[par] = 'constant'
            elif type(interval) is list:
                types[par] = list
            elif type(interval[0]) is int and type(interval[1] is int):
                types[par] = int
            elif type(interval[0]) is float and type(interval[1] is float):
                types[par] = float
            else:
                raise TypeError('Check interval type')
        return types

    def __iter__(self):
        return self

    def next_random(self):
        """
        Iterator next method,
        returns the next grid record

        Parameters
        ----------
        Returns
        -------
        x_grid : dict
        Randomized parameter dictionary
        """
        if self.n == 0:
            rnd.seed(self.seed)

        x_grid = dict()
        for par, interval in self.param_ranges.items():
            if self.types[par] is int:
                x_grid[par] = rnd.randint(interval[0], interval[1])
            elif self.types[par] is float:
                x_grid[par] = rnd.uniform(interval[0], interval[1])
            elif self.types[par] is list:
                x_grid[par] = []
                for el in interval:
                    if (type(el) is int):
                        x_grid[par].append(el)
                    elif type(el) is tuple:
                        x_grid[par].append(rnd.randint(el[0], el[1]))
            elif self.types[par] == 'constant':
                x_grid[par] = interval

        self.n += 1
        if self.n == self.size+1:
            self.n = 0
            # set random seed at exit
            rnd.seed()
            raise StopIteration
        else:
            return x_grid

    def set_uniform_grid(self):

        # generate grid vectors
        par_vectors = dict()
        for par, interval in self.param_ranges.items():
            if self.types[par] is int:
                par_vectors[par] = np.linspace(interval[0],
                                               interval[1],
                                               self.vec_size, dtype=int)
            elif self.types[par] is float:
                par_vectors[par] = np.linspace(interval[0],
                                               interval[1],
                                               self.vec_size, dtype=float)
            elif self.types[par] is list:
                # list parameters must be flatten
                for i, el in enumerate(interval):
                    if type(el) is int:
                        par_vectors[par+str(i)] = [el]
                    elif type(el) is tuple:
                        if type(el[0]) is int:
                            par_vectors[par+str(i)] = (
                                np.linspace(el[0],
                                            el[1],
                                            self.vec_size, dtype=int))
                        elif type(el[0]) is float:
                            par_vectors[par+str(i)] = (
                                np.linspace(el[0],
                                            el[1],
                                            self.vec_size, dtype=float))
            elif self.types[par] == 'constant':
                par_vectors[par] = [interval]

        # cartesian product
        self.grid_iter = (product(*par_vectors.values()))

        # store dictionary for indexing the grid
        self.flat_params_indexes = dict()
        for i, el in enumerate(par_vectors):
            self.flat_params_indexes[el] = i

    def next_uniform(self):
        """
        Iterator next method,
        returns the next grid record

        Parameters
        ----------
        Returns
        -------
        d : dict
        Next grid record
        """
        record = self.grid_iter.next()

        d = dict()
        for i, par in enumerate(self.param_ranges):
            if self.types[par] is list:
                # merging list type params
                d[par] = []
                for i in range(len(self.param_ranges[par])):
                    d[par].append(record[self.flat_params_indexes[par+str(i)]])
            else:
                d[par] = record[self.flat_params_indexes[par]]

        return d

    def reset(self):
        """Reset the grid, to use again the iterator """
        if self.random:
            rnd.seed(self.seed)
            self.n = 0
        else:
            self.set_uniform_grid()

    def get_par_index(self, index):
        self.reset()
        for i in range(index+1):
            params = self.next()
        return params

    def __len__(self):
        """ Returns the grid length """
        if self.random:
            return self.size
        else:
            grid_dims = len(self.flat_params_indexes.keys())
            n_const = 0
            for k, v in self.types.items():
                if v == 'constant':
                    n_const += 1
            return self.size**(grid_dims-n_const)

    def get_as_dict(self):
        """ get the grid as a dict """
        self.reset()
        grid_dict = {par: [] for par in self.param_ranges.keys()}

        for record in self:
            for par, values in record.items():
                grid_dict[par].append(
                    values)

        return grid_dict
