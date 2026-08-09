#!/usr/bin/env python3
r"""Bilinear (rank-K matrix-factorized) logistic regression for 2D neural decoding.

WHY THIS EXISTS
    Every 2D decoder in this project so far (v5, v6) flattened each trial's (N x T) matrix --
    N units/channels by T time bins -- into one N*T vector and PCA'd it down. That destroys the
    laminar/spatial topology and the temporal continuity, and the PCA components carry no
    interpretable spatial or temporal meaning. This model instead constrains the weight matrix
    to be low rank:

        W = sum_{k=1..K} u_k v_k^T ,    logit = <W, X> + b = sum_k u_k^T X v_k

    so parameters drop from O(N*T) to O(K(N+T)), and u_k is directly a SPATIAL (laminar depth /
    unit) profile while v_k is a TEMPORAL filter -- both readable, which the PCA pipeline's
    components are not.

HOW IT IS FITTED (exact alternating least-logistic-loss, no approximation)
    The objective is biconvex: linear in U with V held fixed, and linear in V with U held fixed.
    Both half-steps are therefore ordinary L2 logistic regressions on a re-shaped design:
        fix V:  <W, X_i> = sum_{n,k} U[n,k] * (X_i V)[n,k]   -> features (X_i V).ravel(), NK long
        fix U:  <W, X_i> = sum_{k,t} V[t,k] * (U^T X_i)[k,t] -> features (U^T X_i).ravel(), KT long
    Alternate until the training log-loss stops improving. Biconvex, not jointly convex: the
    solution depends on the (seeded) initialization of V, so `random_state` is part of the
    result, not a formality. Convergence is to a local optimum -- stated plainly rather than
    implied away.

MULTICLASS
    One-vs-rest: one bilinear model per class, giving one interpretable (u, v) pair PER CLASS,
    then a softmax over the K decision values for calibrated probabilities. A shared-factor
    multinomial formulation would tangle the class weights with u_k and make the recovered
    spatial profile non-identifiable, so OvR is the deliberate choice here.
"""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss


class BilinearLogisticRegression:
    """Rank-K bilinear logistic regression on (n_trials, N, T) inputs.

    Attributes after fit (all per-class, indexed by ``classes_``):
        U_ : (n_classes, N, K) spatial profiles
        V_ : (n_classes, T, K) temporal filters
        intercept_ : (n_classes,)
        n_iter_run_ : list of iterations actually used per class
    """

    def __init__(self, rank=2, C=1.0, n_iter=20, tol=1e-4, random_state=None, standardize=True,
                 class_weight="balanced"):
        self.rank = rank
        self.C = C
        self.class_weight = class_weight
        self.n_iter = n_iter
        self.tol = tol
        self.random_state = random_state
        self.standardize = standardize

    # ---- internals -------------------------------------------------------
    def _scale_fit(self, X):
        if not self.standardize:
            self.mean_, self.std_ = 0.0, 1.0
            return X
        self.mean_ = X.mean(axis=0)
        self.std_ = X.std(axis=0)
        self.std_[self.std_ < 1e-9] = 1.0
        return (X - self.mean_) / self.std_

    def _scale(self, X):
        return X if not self.standardize else (X - self.mean_) / self.std_

    def _fit_binary(self, X, y):
        n, N, T = X.shape
        K = min(self.rank, N, T)
        rng = np.random.default_rng(self.random_state)
        V = rng.standard_normal((T, K)) / np.sqrt(T)
        U = None
        b = 0.0
        prev_loss = np.inf
        iters = 0
        for it in range(self.n_iter):
            # --- step 1: fix V, solve for U ---
            A = np.einsum("int,tk->ink", X, V).reshape(n, N * K)
            lr = LogisticRegression(C=self.C, max_iter=1000, random_state=self.random_state,
                                    class_weight=self.class_weight)
            lr.fit(A, y)
            U = lr.coef_.reshape(N, K)
            b = float(lr.intercept_[0])

            # --- step 2: fix U, solve for V ---
            B = np.einsum("nk,int->ikt", U, X).reshape(n, K * T)
            lr2 = LogisticRegression(C=self.C, max_iter=1000, random_state=self.random_state,
                                     class_weight=self.class_weight)
            lr2.fit(B, y)
            V = lr2.coef_.reshape(K, T).T
            b = float(lr2.intercept_[0])

            iters = it + 1
            p = _sigmoid(_bilinear_score(X, U, V, b))
            loss = log_loss(y, np.clip(p, 1e-9, 1 - 1e-9), labels=[0, 1])
            if prev_loss - loss < self.tol:
                break
            prev_loss = loss
        return U, V, b, iters

    # ---- API -------------------------------------------------------------
    def fit(self, X, y):
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y)
        X = self._scale_fit(X)
        self.classes_ = np.unique(y)
        Us, Vs, bs, its = [], [], [], []
        for c in self.classes_:
            yc = (y == c).astype(int)
            U, V, b, it = self._fit_binary(X, yc)
            Us.append(U); Vs.append(V); bs.append(b); its.append(it)
        self.U_ = np.stack(Us)
        self.V_ = np.stack(Vs)
        self.intercept_ = np.array(bs)
        self.n_iter_run_ = its
        return self

    def decision_function(self, X):
        X = self._scale(np.asarray(X, dtype=np.float64))
        return np.stack(
            [_bilinear_score(X, self.U_[i], self.V_[i], self.intercept_[i])
             for i in range(len(self.classes_))],
            axis=1,
        )

    def predict_proba(self, X):
        D = self.decision_function(X)
        D = D - D.max(axis=1, keepdims=True)
        E = np.exp(D)
        return E / E.sum(axis=1, keepdims=True)

    def predict(self, X):
        return self.classes_[np.argmax(self.decision_function(X), axis=1)]

    def score(self, X, y):
        return float(np.mean(self.predict(X) == np.asarray(y)))

    def n_parameters(self):
        n_cls, N, K = self.U_.shape
        T = self.V_.shape[1]
        return int(n_cls * (K * (N + T) + 1))


def _bilinear_score(X, U, V, b):
    return np.einsum("int,nk,tk->i", X, U, V) + b


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -50, 50)))
