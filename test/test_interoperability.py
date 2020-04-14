# Copyright 2019 IBM Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
import warnings
import random
import sys
import lale.operators as Ops
from lale.lib.lale import ConcatFeatures
from lale.lib.lale import NoOp
from lale.lib.sklearn import KNeighborsClassifier
from lale.lib.sklearn import LinearSVC
from lale.lib.sklearn import LogisticRegression
from lale.lib.sklearn import MinMaxScaler
from lale.lib.sklearn import MLPClassifier
from lale.lib.sklearn import Nystroem
from lale.lib.sklearn import OneHotEncoder
from lale.lib.sklearn import PCA
from lale.lib.sklearn import TfidfVectorizer
from lale.lib.sklearn import MultinomialNB
from lale.lib.sklearn import SimpleImputer
from lale.lib.sklearn import SVC
from lale.lib.xgboost import XGBClassifier
from lale.lib.sklearn import PassiveAggressiveClassifier
from lale.lib.sklearn import StandardScaler
from lale.lib.sklearn import FeatureAgglomeration
from typing import List

import sklearn.datasets

from lale.sklearn_compat import make_sklearn_compat
from lale.search.lale_smac import get_smac_space, lale_trainable_op_from_config
from lale.search.op2hp import hyperopt_search_space

@unittest.skip("Skipping here because travis-ci fails to allocate memory. This runs on internal travis.")
class TestResNet50(unittest.TestCase):
    def test_init_fit_predict(self):
        import torchvision.datasets as datasets
        import torchvision.transforms as transforms
        from lale.lib.pytorch import ResNet50

        transform = transforms.Compose([transforms.ToTensor()])

        data_train = datasets.FakeData(size = 50, num_classes=2 , transform = transform)#, target_transform = transform)
        clf = ResNet50(num_classes=2,num_epochs = 1)
        clf.fit(data_train)
        predicted = clf.predict(data_train)


class TestResamplers(unittest.TestCase):

    def setUp(self):
        from sklearn.datasets import make_classification
        from sklearn.model_selection import train_test_split
        X, y = make_classification(n_classes=2, class_sep=2,
            weights=[0.1, 0.9], n_informative=3, n_redundant=1, flip_y=0,
            n_features=20, n_clusters_per_class=1, n_samples=1000, random_state=10)
        self.X_train, self.X_test, self.y_train, self.y_test =  train_test_split(X, y)    

def create_function_test_resampler(res_name):
    def test_resampler(self):
        from lale.lib.sklearn import PCA, Nystroem, LogisticRegression, RandomForestClassifier
        from lale.lib.lale import NoOp, ConcatFeatures
        X_train, y_train = self.X_train, self.y_train
        X_test, y_test = self.X_test, self.y_test
        import importlib
        module_name = ".".join(res_name.split('.')[0:-1])
        class_name = res_name.split('.')[-1]
        module = importlib.import_module(module_name)

        class_ = getattr(module, class_name)
        with self.assertRaises(ValueError):
            res = class_()

        #test_schemas_are_schemas
        from lale.helpers import validate_is_schema
        validate_is_schema(class_.input_schema_fit())
        validate_is_schema(class_.input_schema_predict())
        validate_is_schema(class_.output_schema_predict())
        validate_is_schema(class_.hyperparam_schema())

        #test_init_fit_predict
        from lale.operators import make_pipeline
        pipeline1 = PCA() >> class_(operator=make_pipeline(LogisticRegression()))
        trained = pipeline1.fit(X_train, y_train)
        predictions = trained.predict(X_test)

        pipeline2 = class_(operator=make_pipeline(PCA(), LogisticRegression()))
        trained = pipeline2.fit(X_train, y_train)
        predictions = trained.predict(X_test)

        #test_with_hyperopt
        from lale.lib.lale import Hyperopt
        optimizer = Hyperopt(estimator=PCA >> class_(operator=make_pipeline(LogisticRegression())), max_evals = 1, show_progressbar=False)
        trained_optimizer = optimizer.fit(X_train, y_train)
        predictions = trained_optimizer.predict(X_test)

        pipeline3 = class_(operator= PCA() >> (Nystroem & NoOp) >> ConcatFeatures >> LogisticRegression())
        optimizer = Hyperopt(estimator=pipeline3, max_evals = 1, show_progressbar=False)
        trained_optimizer = optimizer.fit(X_train, y_train)
        predictions = trained_optimizer.predict(X_test)

        pipeline4 = (PCA >> class_(operator=make_pipeline(Nystroem())) & class_(operator=make_pipeline(Nystroem()))) >> ConcatFeatures >> LogisticRegression()
        optimizer = Hyperopt(estimator=pipeline4, max_evals = 1, scoring='roc_auc', show_progressbar=False)
        trained_optimizer = optimizer.fit(X_train, y_train)
        predictions = trained_optimizer.predict(X_test)

        #test_cross_validation
        from lale.helpers import cross_val_score
        cv_results = cross_val_score(pipeline1, X_train, y_train, cv = 2)
        self.assertEqual(len(cv_results), 2)

        #test_to_json
        pipeline1.to_json()

    test_resampler.__name__ = 'test_{0}'.format(res_name.split('.')[-1])
    return test_resampler

resamplers = ['lale.lib.imblearn.SMOTE',
              'lale.lib.imblearn.SMOTEENN',
              'lale.lib.imblearn.ADASYN',
              'lale.lib.imblearn.BorderlineSMOTE',
              'lale.lib.imblearn.SVMSMOTE',
              'lale.lib.imblearn.RandomOverSampler',
              'lale.lib.imblearn.CondensedNearestNeighbour',
              'lale.lib.imblearn.EditedNearestNeighbours',
              'lale.lib.imblearn.RepeatedEditedNearestNeighbours',
              'lale.lib.imblearn.AllKNN',
              'lale.lib.imblearn.InstanceHardnessThreshold']

for res in resamplers:
    setattr(
        TestResamplers,
        'test_{0}'.format(res.split('.')[-1]),
        create_function_test_resampler(res)
    )

class TestImblearn(unittest.TestCase):
    def setUp(self):
        from sklearn.datasets import make_classification
        from sklearn.model_selection import train_test_split
        X, y = make_classification(n_classes=2, class_sep=2,
            weights=[0.1, 0.9], n_informative=3, n_redundant=1, flip_y=0,
            n_features=20, n_clusters_per_class=1, n_samples=1000, random_state=10)
        self.X_train, self.X_test, self.y_train, self.y_test =  train_test_split(X, y)    

    def test_decision_function(self):
        from lale.lib.imblearn import SMOTE
        from lale.operators import make_pipeline
        from lale.lib.sklearn import RandomForestClassifier
        smote = SMOTE(operator=make_pipeline(RandomForestClassifier()))
        trained = smote.fit(self.X_train, self.y_train)
        trained.predict(self.X_test)
        with self.assertRaises(AttributeError):
            trained.decision_function(self.X_test)