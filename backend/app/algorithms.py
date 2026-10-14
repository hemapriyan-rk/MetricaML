"""The approved algorithm catalogue: the single source of truth.

Users submit configuration, never code. Every algorithm, hyperparameter, range and
constructor lives in this file, anything else is rejected, and the same catalogue
is sent to the UI so the parameter forms are generated from it.

Adding an algorithm = one entry here (label, family, cost, params, build). `cost`
(1 fast .. 3 slow) orders the "compare all algorithms" run so quick models go first.
"""
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.ensemble import (AdaBoostClassifier, AdaBoostRegressor, ExtraTreesClassifier, ExtraTreesRegressor,
                              GradientBoostingClassifier, GradientBoostingRegressor,
                              HistGradientBoostingClassifier, HistGradientBoostingRegressor,
                              RandomForestClassifier, RandomForestRegressor)
from sklearn.linear_model import (ElasticNet, Lasso, LinearRegression, LogisticRegression, Ridge, SGDClassifier,
                                  SGDRegressor)
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.svm import SVC, LinearSVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

COMPARE_KEY = "auto_compare"
COMPARE_LABEL = "Compare all algorithms"


def _int(name, label, default, lo, hi, hint=None):
    return {"name": name, "label": label, "type": "int", "default": default, "min": lo, "max": hi, "hint": hint}


def _float(name, label, default, lo, hi, hint=None, step="any"):
    return {"name": name, "label": label, "type": "float", "default": default, "min": lo, "max": hi,
            "step": step, "hint": hint}


def _choice(name, label, default, choices, hint=None):
    return {"name": name, "label": label, "type": "choice", "default": default, "choices": choices, "hint": hint}


def _depth(p):
    return None if p["max_depth"] == 0 else p["max_depth"]


_DEPTH_HINT = "0 means no limit"


def _entry(label, family, cost, description, params, build):
    return {"label": label, "family": family, "cost": cost, "description": description, "params": params,
            "build": build}


# Parameter groups shared by several algorithms
_TREE = [_int("max_depth", "Maximum depth", 5, 0, 30, _DEPTH_HINT),
         _int("min_samples_split", "Minimum samples to split", 2, 2, 100)]
_FOREST = [_int("n_estimators", "Number of trees", 50, 10, 300), *_TREE]
_BOOST = [_int("n_estimators", "Number of boosting rounds", 100, 10, 300),
          _float("learning_rate", "Learning rate", 0.1, 0.01, 1.0, "Smaller learns slower but often generalises better"),
          _int("max_depth", "Tree depth", 3, 1, 10)]
_HIST = [_int("max_iter", "Boosting rounds", 100, 10, 500),
         _float("learning_rate", "Learning rate", 0.1, 0.01, 1.0),
         _int("max_depth", "Maximum depth", 0, 0, 20, _DEPTH_HINT)]
_ADA = [_int("n_estimators", "Number of estimators", 50, 10, 300),
        _float("learning_rate", "Learning rate", 1.0, 0.01, 2.0)]
_KNN = [_int("n_neighbors", "Number of neighbors", 5, 1, 50),
        _choice("metric", "Distance metric", "euclidean", ["euclidean", "manhattan", "chebyshev"]),
        _choice("weights", "Weights", "uniform", ["uniform", "distance"], "Distance gives closer rows more say")]
_MLP = [_int("hidden_units", "Neurons per layer", 64, 4, 256),
        _int("hidden_layers", "Hidden layers", 1, 1, 3),
        _choice("activation", "Activation", "relu", ["relu", "tanh"]),
        _int("max_iter", "Maximum iterations", 150, 20, 300, "Training stops early when it stops improving")]


def _mlp_args(p, seed):
    return dict(hidden_layer_sizes=(p["hidden_units"],) * p["hidden_layers"], activation=p["activation"],
                max_iter=p["max_iter"], early_stopping=True, n_iter_no_change=10, random_state=seed)


CATALOGUE = {
    "classification": {
        "logistic_regression": _entry(
            "Logistic Regression", "Linear", 1,
            "A fast linear baseline. Works well when classes are roughly separable by a straight boundary.",
            [_float("C", "Regularisation strength (C)", 1.0, 0.001, 100, "Higher values fit the training data more closely"),
             _int("max_iter", "Maximum iterations", 300, 50, 2000),
             _choice("class_weight", "Class weights", "none", ["none", "balanced"], "Balanced helps when one class is rare")],
            lambda p, s: LogisticRegression(C=p["C"], max_iter=p["max_iter"],
                                            class_weight=None if p["class_weight"] == "none" else "balanced",
                                            random_state=s)),
        "sgd_classifier": _entry(
            "SGD Classifier", "Linear", 1,
            "A linear model trained with stochastic gradient descent. Very fast, even on large datasets.",
            [_choice("loss", "Loss function", "hinge", ["hinge", "log_loss", "modified_huber"],
                     "Hinge acts like a linear SVM, log loss like logistic regression"),
             _float("alpha", "Regularisation (alpha)", 0.0001, 0.000001, 1.0),
             _int("max_iter", "Maximum iterations", 200, 5, 1000)],
            lambda p, s: SGDClassifier(loss=p["loss"], alpha=p["alpha"], max_iter=p["max_iter"], random_state=s)),
        "lda": _entry(
            "Linear Discriminant Analysis", "Linear", 1,
            "Finds the directions that best separate the classes. Fast and works well with few rows.",
            [_choice("solver", "Solver", "svd", ["svd", "lsqr"])],
            lambda p, s: LinearDiscriminantAnalysis(solver=p["solver"])),
        "naive_bayes": _entry(
            "Gaussian Naive Bayes", "Probabilistic", 1,
            "Applies Bayes' rule assuming features are independent. Instant to train and a handy baseline.",
            [_choice("var_smoothing", "Variance smoothing", "1e-9", ["1e-9", "1e-8", "1e-7", "1e-6", "1e-5"],
                     "Larger values make it more tolerant of unusual rows")],
            lambda p, s: GaussianNB(var_smoothing=float(p["var_smoothing"]))),
        "knn": _entry(
            "K-Nearest Neighbors", "Neighbors", 2,
            "Predicts from the closest training rows. Simple and intuitive, slower on large datasets.",
            _KNN,
            lambda p, s: KNeighborsClassifier(n_neighbors=p["n_neighbors"], metric=p["metric"], weights=p["weights"])),
        "decision_tree": _entry(
            "Decision Tree", "Trees and ensembles", 1,
            "A readable set of yes/no splits. Fast, but can overfit if allowed to grow deep.",
            [*_TREE, _choice("criterion", "Criterion", "gini", ["gini", "entropy", "log_loss"])],
            lambda p, s: DecisionTreeClassifier(max_depth=_depth(p), min_samples_split=p["min_samples_split"],
                                                criterion=p["criterion"], random_state=s)),
        "random_forest": _entry(
            "Random Forest", "Trees and ensembles", 2,
            "Many decision trees voting together. A strong all-round choice for tabular data.",
            [*_FOREST, _choice("criterion", "Criterion", "gini", ["gini", "entropy"])],
            lambda p, s: RandomForestClassifier(n_estimators=p["n_estimators"], max_depth=_depth(p),
                                                min_samples_split=p["min_samples_split"], criterion=p["criterion"],
                                                n_jobs=1, random_state=s)),
        "extra_trees": _entry(
            "Extra Trees", "Trees and ensembles", 2,
            "Like a random forest but with more randomness in the splits. Often as accurate and faster to train.",
            [*_FOREST, _choice("criterion", "Criterion", "gini", ["gini", "entropy"])],
            lambda p, s: ExtraTreesClassifier(n_estimators=p["n_estimators"], max_depth=_depth(p),
                                              min_samples_split=p["min_samples_split"], criterion=p["criterion"],
                                              n_jobs=1, random_state=s)),
        "gradient_boosting": _entry(
            "Gradient Boosting", "Trees and ensembles", 3,
            "Builds small trees one after another, each correcting the last one's mistakes. Often the most accurate on tables.",
            [*_BOOST, _float("subsample", "Row sample per round", 1.0, 0.5, 1.0, "Below 1 adds randomness and can reduce overfitting")],
            lambda p, s: GradientBoostingClassifier(n_estimators=p["n_estimators"], learning_rate=p["learning_rate"],
                                                    max_depth=p["max_depth"], subsample=p["subsample"],
                                                    random_state=s)),
        "hist_gradient_boosting": _entry(
            "Histogram Gradient Boosting", "Trees and ensembles", 2,
            "A much faster form of gradient boosting that bins the values first. Suited to larger datasets.",
            _HIST,
            lambda p, s: HistGradientBoostingClassifier(max_iter=p["max_iter"], learning_rate=p["learning_rate"],
                                                        max_depth=_depth(p), random_state=s)),
        "adaboost": _entry(
            "AdaBoost", "Trees and ensembles", 2,
            "Boosts many very small trees, giving more weight to rows the earlier ones got wrong.",
            _ADA,
            lambda p, s: AdaBoostClassifier(n_estimators=p["n_estimators"], learning_rate=p["learning_rate"],
                                            random_state=s)),
        "svm": _entry(
            "Support Vector Machine", "Margin", 3,
            "Finds the widest margin between classes. Accurate on small and medium data, slow on large data.",
            [_float("C", "Regularisation strength (C)", 1.0, 0.01, 100),
             _choice("kernel", "Kernel", "rbf", ["rbf", "linear", "poly"]),
             _choice("gamma", "Gamma", "scale", ["scale", "auto"])],
            lambda p, s: SVC(C=p["C"], kernel=p["kernel"], gamma=p["gamma"], random_state=s)),
        "mlp": _entry(
            "Neural Network (MLP)", "Neural network", 3,
            "A small feed-forward neural network. Can capture complex patterns; needs more rows and more time.",
            _MLP,
            lambda p, s: MLPClassifier(**_mlp_args(p, s))),
    },
    "regression": {
        "linear_regression": _entry(
            "Linear Regression", "Linear", 1,
            "Fits a straight-line relationship between the features and the target.",
            [_choice("fit_intercept", "Fit intercept", "yes", ["yes", "no"])],
            lambda p, s: LinearRegression(fit_intercept=p["fit_intercept"] == "yes")),
        "ridge": _entry(
            "Ridge Regression", "Linear", 1,
            "Linear regression with a penalty that keeps coefficients small and stable.",
            [_float("alpha", "Regularisation strength (alpha)", 1.0, 0.001, 1000)],
            lambda p, s: Ridge(alpha=p["alpha"], random_state=s)),
        "lasso": _entry(
            "Lasso Regression", "Linear", 1,
            "Linear regression that can shrink unhelpful features to exactly zero, so it also selects features.",
            [_float("alpha", "Regularisation strength (alpha)", 0.1, 0.0001, 100)],
            lambda p, s: Lasso(alpha=p["alpha"], max_iter=5000, random_state=s)),
        "elasticnet": _entry(
            "Elastic Net", "Linear", 1,
            "A blend of Ridge and Lasso penalties. Handles groups of related features well.",
            [_float("alpha", "Regularisation strength (alpha)", 0.1, 0.0001, 100),
             _float("l1_ratio", "Lasso share (l1 ratio)", 0.5, 0.0, 1.0, "0 is pure Ridge, 1 is pure Lasso")],
            lambda p, s: ElasticNet(alpha=p["alpha"], l1_ratio=p["l1_ratio"], max_iter=5000, random_state=s)),
        "sgd_regressor": _entry(
            "SGD Regressor", "Linear", 1,
            "A linear model trained with stochastic gradient descent. Very fast, even on large datasets.",
            [_choice("loss", "Loss function", "squared_error", ["squared_error", "huber"],
                     "Huber is less thrown off by extreme values"),
             _float("alpha", "Regularisation (alpha)", 0.0001, 0.000001, 1.0),
             _int("max_iter", "Maximum iterations", 200, 5, 1000)],
            lambda p, s: SGDRegressor(loss=p["loss"], alpha=p["alpha"], max_iter=p["max_iter"], random_state=s)),
        "knn_regressor": _entry(
            "K-Nearest Neighbors Regressor", "Neighbors", 2,
            "Predicts the average of the closest training rows.",
            _KNN,
            lambda p, s: KNeighborsRegressor(n_neighbors=p["n_neighbors"], metric=p["metric"], weights=p["weights"])),
        "decision_tree_regressor": _entry(
            "Decision Tree Regressor", "Trees and ensembles", 1,
            "Splits the data into regions and predicts the average of each region.",
            [*_TREE, _choice("criterion", "Criterion", "squared_error", ["squared_error", "friedman_mse"])],
            lambda p, s: DecisionTreeRegressor(max_depth=_depth(p), min_samples_split=p["min_samples_split"],
                                               criterion=p["criterion"], random_state=s)),
        "random_forest_regressor": _entry(
            "Random Forest Regressor", "Trees and ensembles", 2,
            "Many regression trees averaged together. Handles non-linear patterns well.",
            [*_FOREST, _choice("criterion", "Criterion", "squared_error", ["squared_error", "friedman_mse"])],
            lambda p, s: RandomForestRegressor(n_estimators=p["n_estimators"], max_depth=_depth(p),
                                               min_samples_split=p["min_samples_split"], criterion=p["criterion"],
                                               n_jobs=1, random_state=s)),
        "extra_trees_regressor": _entry(
            "Extra Trees Regressor", "Trees and ensembles", 2,
            "Like a random forest but with more randomness in the splits. Often as accurate and faster to train.",
            [*_FOREST, _choice("criterion", "Criterion", "squared_error", ["squared_error", "friedman_mse"])],
            lambda p, s: ExtraTreesRegressor(n_estimators=p["n_estimators"], max_depth=_depth(p),
                                             min_samples_split=p["min_samples_split"], criterion=p["criterion"],
                                             n_jobs=1, random_state=s)),
        "gradient_boosting_regressor": _entry(
            "Gradient Boosting Regressor", "Trees and ensembles", 3,
            "Builds small trees one after another, each correcting the last one's errors. Often the most accurate on tables.",
            [*_BOOST, _float("subsample", "Row sample per round", 1.0, 0.5, 1.0, "Below 1 adds randomness and can reduce overfitting")],
            lambda p, s: GradientBoostingRegressor(n_estimators=p["n_estimators"], learning_rate=p["learning_rate"],
                                                   max_depth=p["max_depth"], subsample=p["subsample"],
                                                   random_state=s)),
        "hist_gradient_boosting_regressor": _entry(
            "Histogram Gradient Boosting Regressor", "Trees and ensembles", 2,
            "A much faster form of gradient boosting that bins the values first. Suited to larger datasets.",
            _HIST,
            lambda p, s: HistGradientBoostingRegressor(max_iter=p["max_iter"], learning_rate=p["learning_rate"],
                                                       max_depth=_depth(p), random_state=s)),
        "adaboost_regressor": _entry(
            "AdaBoost Regressor", "Trees and ensembles", 2,
            "Boosts many small trees, focusing on the rows with the biggest errors.",
            _ADA,
            lambda p, s: AdaBoostRegressor(n_estimators=p["n_estimators"], learning_rate=p["learning_rate"],
                                           random_state=s)),
        "linear_svr": _entry(
            "Linear Support Vector Regressor", "Margin", 2,
            "A support vector machine for numbers, with a linear kernel. Scales to many rows.",
            [_float("C", "Regularisation strength (C)", 1.0, 0.01, 100)],
            lambda p, s: LinearSVR(C=p["C"], max_iter=5000, dual="auto", random_state=s)),
        "mlp_regressor": _entry(
            "Neural Network Regressor (MLP)", "Neural network", 3,
            "A small feed-forward neural network for numbers. Can capture complex patterns; needs more rows and time.",
            _MLP,
            lambda p, s: MLPRegressor(**_mlp_args(p, s))),
    },
}


def public_catalogue() -> dict:
    """The catalogue without the constructors, for the UI."""
    return {
        pt: [{"key": key, **{k: v for k, v in spec.items() if k not in ("build", "cost")}}
             for key, spec in algos.items()]
        for pt, algos in CATALOGUE.items()
    }


def algorithm_label(problem_type: str, key: str) -> str:
    return COMPARE_LABEL if key == COMPARE_KEY else CATALOGUE[problem_type][key]["label"]


def default_params(problem_type: str, key: str) -> dict:
    return {p["name"]: p["default"] for p in CATALOGUE[problem_type][key]["params"]}


def validate_params(problem_type: str, key: str, raw: dict | None) -> dict:
    """Return a cleaned copy of the hyperparameters or raise ValueError."""
    if problem_type not in CATALOGUE:
        raise ValueError("Problem type must be classification or regression.")
    if key == COMPARE_KEY:
        return {}
    if key not in CATALOGUE[problem_type]:
        raise ValueError(f"'{key}' is not an available {problem_type} algorithm.")
    raw = raw or {}
    clean = {}
    for spec in CATALOGUE[problem_type][key]["params"]:
        name = spec["name"]
        value = raw.get(name, spec["default"])
        if spec["type"] == "choice":
            if value not in spec["choices"]:
                raise ValueError(f"{spec['label']} must be one of: {', '.join(spec['choices'])}.")
        else:
            if isinstance(value, bool):
                raise ValueError(f"{spec['label']} must be a number.")
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise ValueError(f"{spec['label']} must be a number.")
            if number != number or number in (float("inf"), float("-inf")):
                raise ValueError(f"{spec['label']} must be a finite number.")
            if spec["type"] == "int":
                if number != int(number):
                    raise ValueError(f"{spec['label']} must be a whole number.")
                value = int(number)
            else:
                value = number
            if not spec["min"] <= value <= spec["max"]:
                raise ValueError(f"{spec['label']} must be between {spec['min']} and {spec['max']}.")
        clean[name] = value
    return clean


def build_estimator(problem_type: str, key: str, params: dict, random_state: int):
    try:
        build = CATALOGUE[problem_type][key]["build"]
    except KeyError:
        raise ValueError(f"Unknown algorithm '{key}'.")
    return build(params, random_state)
