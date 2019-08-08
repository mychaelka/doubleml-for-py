import numpy as np
import pytest
import math

from sklearn.datasets import make_spd_matrix
from sklearn.model_selection import KFold
from sklearn.ensemble import RandomForestRegressor
from sklearn.base import clone

from dml.dml_plr import DoubleMLPLR

def g(x):
    return np.power(np.sin(x),2)

def m(x,nu=0.,gamma=1.):
    return 0.5/np.pi*(np.sinh(gamma))/(np.cosh(gamma)-np.cos(x-nu))


@pytest.fixture(scope="module")
def generate_data1():
    # setting parameters
    N = 500
    k=10
    theta=0.5
    b= [1/k for k in range(1,11)]
    sigma = make_spd_matrix(k)
    
    # number of data sets
    n_datasets = 10
    
    # generating data
    np.random.seed(1111)
    datasets = []
    for i in range(n_datasets):
        X = np.random.multivariate_normal(np.ones(k),sigma,size=[N,])
        G = g(np.dot(X,b))
        M = m(np.dot(X,b))
        D = M+np.random.standard_normal(size=[500,])
        Y = np.dot(theta,D)+G+np.random.standard_normal(size=[500,])
        xx = {'X': X, 'y': Y, 'd': D}
        datasets.append(xx)
    
    return datasets

@pytest.mark.parametrize('idx', range(10))
def test_dml_plr(generate_data1, idx):
    resampling = KFold(n_splits=2, shuffle=False)
    
    # Set machine learning methods for m & g
    ml_m = RandomForestRegressor(max_depth=2, n_estimators=10)
    ml_g = RandomForestRegressor(max_depth=2, n_estimators=10)
    
    ml_learners = {'ml_m': clone(ml_m),
                   'ml_g': clone(ml_g)}
    dml_plr_obj = DoubleMLPLR(resampling,
                              ml_learners,
                              'dml1',
                              'IV-type')
    data = generate_data1[idx]
    np.random.seed(3141)
    res = dml_plr_obj.fit(data['X'], data['y'], data['d'])
    
    np.random.seed(3141)
    res_manual = dml_cross_fitting(data['y'], data['X'], data['d'],
                                   clone(ml_m), clone(ml_g), resampling)
    
    assert math.isclose(res.coef_, res_manual, rel_tol=1e-9, abs_tol=0.0)
    
    return
    

def dml_cross_fitting(Y, X, D, ml_m, ml_g, resampling):
    thetas = np.zeros(resampling.get_n_splits())
    for idx, (train_index, test_index) in enumerate(resampling.split(X)):
        ghat = ml_g.fit(X[train_index],Y[train_index]).predict(X[test_index])
        mhat = ml_m.fit(X[train_index],D[train_index]).predict(X[test_index])
        
        vhat = D[test_index] - mhat
        thetas[idx] = np.mean(np.dot(vhat, (Y[test_index] - ghat)))/np.mean(np.dot(vhat, D[test_index]))
    theta_hat = np.mean(thetas)
    
    return theta_hat
