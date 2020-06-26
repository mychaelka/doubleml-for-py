import numpy as np
from sklearn.utils import check_X_y
from sklearn.model_selection import KFold
from sklearn.model_selection import GridSearchCV

from .double_ml import DoubleML, DoubleMLData
from .helper import _dml_cross_val_predict


class DoubleMLPLIV(DoubleML):
    """
    Double machine learning for partially linear IV regression models

    Parameters
    ----------
    data :
        ToDo
    x_cols :
        ToDo
    y_col :
        ToDo
    d_cols :
        ToDo
    z_col :
        ToDo
    ml_learners :
        ToDo
    n_folds :
        ToDo
    n_rep_cross_fit :
        ToDo
    inf_model :
        ToDo
    dml_procedure :
        ToDo
    draw_sample_splitting :
        ToDo

    Examples
    --------
    >>> import doubleml as dml
    >>> dml.DoubleMLPLIV()

    Notes
    -----
    **Partially linear IV regression (PLIV)** models take the form

    .. math::

        Y - D \\theta_0 =  g_0(X) + \zeta, & &\mathbb{E}(\zeta | Z, X) = 0,

        Z = m_0(X) + V, & &\mathbb{E}(V | X) = 0.

    """
    def __init__(self,
                 obj_dml_data,
                 ml_learners,
                 n_folds=5,
                 n_rep_cross_fit=1,
                 inf_model='DML2018',
                 dml_procedure='dml1',
                 draw_sample_splitting=True):
        super().__init__(obj_dml_data,
                         ml_learners,
                         n_folds,
                         n_rep_cross_fit,
                         inf_model,
                         dml_procedure,
                         draw_sample_splitting)
        self._g_params = None
        self._m_params = None
        self._r_params = None

    def _check_inf_method(self, inf_model):
        if isinstance(inf_model, str):
            valid_inf_model = ['DML2018']
            # check whether its worth implementing the IV_type as well
            # In CCDHNR equation (4.7) a score of this type is provided;
            # however in the following paragraph it is explained that one might
            # still need to estimate the DML2018 type first
            if inf_model not in valid_inf_model:
                raise ValueError('invalid inf_model ' + inf_model +
                                 '\n valid inf_model ' + valid_inf_model)
        else:
            if not callable(inf_model):
                raise ValueError('inf_model should be either a string or a callable.'
                                 ' %r was passed' % inf_model)
        return inf_model

    def _check_data(self, obj_dml_data):
        return
    
    def _ml_nuisance_and_score_elements(self, obj_dml_data, smpls, n_jobs_cv):
        ml_g = self.ml_learners['ml_g']
        ml_m = self.ml_learners['ml_m']
        ml_r = self.ml_learners['ml_r']
        
        X, y = check_X_y(obj_dml_data.x, obj_dml_data.y)
        X, z = check_X_y(X, obj_dml_data.z)
        X, d = check_X_y(X, obj_dml_data.d)
        
        # nuisance g
        g_hat = _dml_cross_val_predict(ml_g, X, y, smpls=smpls, n_jobs=n_jobs_cv)
        
        # nuisance m
        m_hat = _dml_cross_val_predict(ml_m, X, z, smpls=smpls, n_jobs=n_jobs_cv)
        
        # nuisance r
        r_hat = _dml_cross_val_predict(ml_r, X, d, smpls=smpls, n_jobs=n_jobs_cv)
        
        # compute residuals
        u_hat = y - g_hat
        v_hat = z - m_hat
        w_hat = d - r_hat

        inf_model = self.inf_model
        self._check_inf_method(inf_model)
        if isinstance(self.inf_model, str):
            if inf_model == 'DML2018':
                score_a = -np.multiply(w_hat, v_hat)
            score_b = np.multiply(v_hat, u_hat)
        elif callable(self.inf_model):
            score_a, score_b = self.inf_model(y, z, d, g_hat, m_hat, r_hat, smpls)


        return score_a, score_b

    def _ml_nuisance_tuning(self, obj_dml_data, smpls, param_grids, scoring_methods, n_folds_tune, n_jobs_cv):
        ml_g = self.ml_learners['ml_g']
        ml_m = self.ml_learners['ml_m']
        ml_r = self.ml_learners['ml_r']

        X, y = check_X_y(obj_dml_data.x, obj_dml_data.y)
        X, z = check_X_y(X, obj_dml_data.z)
        X, d = check_X_y(X, obj_dml_data.d)

        if scoring_methods is None:
            scoring_methods = {'scoring_methods_g': None,
                               'scoring_methods_m': None,
                               'scoring_methods_r': None}

        g_tune_res = [None] * len(smpls)
        m_tune_res = [None] * len(smpls)
        r_tune_res = [None] * len(smpls)

        for idx, (train_index, test_index) in enumerate(smpls):
            # cv for ml_g
            g_tune_resampling = KFold(n_splits=n_folds_tune)
            g_grid_search = GridSearchCV(ml_g, param_grids['param_grid_g'],
                                         scoring=scoring_methods['scoring_methods_g'],
                                         cv=g_tune_resampling)
            g_tune_res[idx] = g_grid_search.fit(X[train_index, :], y[train_index])

            # cv for ml_m
            m_tune_resampling = KFold(n_splits=n_folds_tune)
            m_grid_search = GridSearchCV(ml_m, param_grids['param_grid_m'],
                                         scoring=scoring_methods['scoring_methods_m'],
                                         cv=m_tune_resampling)
            m_tune_res[idx] = m_grid_search.fit(X[train_index, :], z[train_index])

            # cv for ml_r
            r_tune_resampling = KFold(n_splits=n_folds_tune)
            r_grid_search = GridSearchCV(ml_r, param_grids['param_grid_r'],
                                         scoring=scoring_methods['scoring_methods_r'],
                                         cv=r_tune_resampling)
            r_tune_res[idx] = r_grid_search.fit(X[train_index, :], d[train_index])

        g_best_params = [xx.best_params_ for xx in g_tune_res]
        m_best_params = [xx.best_params_ for xx in m_tune_res]
        r_best_params = [xx.best_params_ for xx in r_tune_res]

        params = {'g_params': g_best_params,
                  'm_params': m_best_params,
                  'r_params': r_best_params}

        tune_res = {'g_tune': g_tune_res,
                    'm_tune': m_tune_res,
                    'r_tune': r_tune_res}

        res = {'params': params,
               'tune_res': tune_res}

        return(res)

    def _set_ml_nuisance_params(self, params):
        self._g_params = params['g_params']
        self._m_params = params['m_params']
        self._r_params = params['r_params']

