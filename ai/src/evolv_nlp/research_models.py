from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.linear_model import LogisticRegression


class TwoStageClassifier(ClassifierMixin, BaseEstimator):
    """Predict a parent task first, then its subtype. Scores are not calibrated."""

    def __init__(self, root_estimator, parent_map):
        self.root_estimator = root_estimator
        self.parent_map = parent_map

    def fit(self, X, y, sample_weight=None):
        y = np.asarray(y)
        parents = np.asarray([self.parent_map[label] for label in y])
        self.classes_ = np.unique(y)
        self.root_ = clone(self.root_estimator)
        self.root_.fit(X, parents, sample_weight=sample_weight)
        self.children_ = {}
        for parent in np.unique(parents):
            mask = parents == parent
            children = np.unique(y[mask])
            if len(children) == 1:
                self.children_[parent] = str(children[0])
            else:
                child = LogisticRegression(C=2.0, max_iter=2000, class_weight="balanced", random_state=42)
                child.fit(X[mask], y[mask], sample_weight=sample_weight[mask] if sample_weight is not None else None)
                self.children_[parent] = child
        return self

    def predict(self, X):
        parents = self.root_.predict(X)
        result = parents.astype(object)
        for parent in np.unique(parents):
            mask = parents == parent
            child = self.children_[parent]
            result[mask] = child if isinstance(child, str) else child.predict(X[mask])
        return result.astype(str)


class ResearchTextModel:
    """Explicit native predict() contract; no uncalibrated pseudo-probabilities."""

    def __init__(self, features, classifier, reducer=None):
        self.features = features
        self.classifier = classifier
        self.reducer = reducer
        self.classes_ = classifier.classes_

    def predict(self, texts):
        X = self.features.transform(texts)
        if self.reducer is not None:
            X = self.reducer.transform(X)
        return self.classifier.predict(X)
