import abc
import collections
import copy
import inspect

import numpy as np
import scipy.stats
import tree

# https://docs.python.org/3/reference/datamodel.html#special-method-names
# https://docs.python.org/3/library/operator.html
BIN_OPS_SYNTAX_2_ATTR = {
    # comparison
    "<": "__lt__",
    "<=": "__le__",
    "==": "__eq__",
    "!=": "__ne__",
    ">": "__gt__",
    ">=": "__ge__",
    # numeric operators
    "+": "__add__",
    "-": "__sub__",
    "*": "__mul__",
    "@": "__matmul__",
    "/": "__truediv__",
    "//": "__floordiv__",
    "%": "__mod__",
    # __divmod__
    "**": "__pow__",
    # __lshift__
    # __rshift__
    "and": "__and__",
    "^": "__xor__",
    "or": "__or__",
}
BIN_OPS_ATTR_2_SYNTAX = {v: k for k, v in BIN_OPS_SYNTAX_2_ATTR.items()}

# unary operators
UNA_OPS_SYNTAX_2_ATTR = {
    "-": "__neg__",
    "+": "__pos__",
    "~": "__invert__",
}
UNA_OPS_ATTR_2_SYNTAX = {v: k for k, v in UNA_OPS_SYNTAX_2_ATTR.items()}


class Expression:

    # numerical operators
    def __add__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__add__"])

    def __radd__(self, other):
        return BinaryExpression(other, self, BIN_OPS_ATTR_2_SYNTAX["__add__"])

    def __sub__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__sub__"])

    def __mul__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__mul__"])

    def __rmul__(self, other):
        return BinaryExpression(other, self, BIN_OPS_ATTR_2_SYNTAX["__mul__"])

    def __matmul__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__matmul__"])

    def __truediv__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__truediv__"])

    def __floordiv__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__floordiv__"])

    def __mod__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__mod__"])

    # order and comparison operators
    def __lt__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__lt__"])

    def __le__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__le__"])

    def __eq__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__eq__"])

    def __ne__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__ne__"])

    def __gt__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__gt__"])

    def __ge__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__ge__"])

    # logic operators
    def __and__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__and__"])

    def __xor__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__xor__"])

    def __or__(self, other):
        return BinaryExpression(self, other, BIN_OPS_ATTR_2_SYNTAX["__or__"])

    # unary operators
    def __pos__(self):
        return UnaryExpression(UNA_OPS_ATTR_2_SYNTAX["__pos__"], self)

    def __neg__(self):
        return UnaryExpression(UNA_OPS_ATTR_2_SYNTAX["__neg__"], self)

    def __invert__(self):
        return UnaryExpression(UNA_OPS_ATTR_2_SYNTAX["__invert__"], self)

    def __getitem__(self, item):
        return ExpressionItemAccess(self, item)

    def __getattribute__(self, __name: str):
        try:
            return super().__getattribute__(__name)
        except AttributeError:
            return ExpressionAttributeAccess(self, __name)

    def __call__(self, *args, **kwargs):
        return ExpressionCallExpression(self, *args, **kwargs)

    def choices(self):
        memo = {}

        def choice_aux(o):

            if isinstance(o, Expression):

                if isinstance(o, VarExpression):
                    memo[o.id] = o
                else:
                    memo.update(o.choices())

            return memo

        tree.map_structure(choice_aux, self.__dict__)

        return memo

    def freeze(self, choice: dict):

        # propagate the materialization
        def freeze_aux(o):

            if isinstance(o, Expression):
                o.freeze(choice)

        tree.map_structure(freeze_aux, self.__dict__)

    def evaluate_children(self):

        # propagate the evaluation
        def evaluate_aux(o):

            if isinstance(o, Expression):
                eval_ = o.evaluate()
            else:
                eval_ = o
            return eval_

        self.__dict__ = tree.map_structure(evaluate_aux, self.__dict__)

    @abc.abstractmethod
    def evaluate(self):
        """Evaluate the value of the current expression."""
        raise NotImplementedError

    def variables(self):
        memo = {}

        def choice_aux(o):

            if isinstance(o, Expression):

                if isinstance(o, VarExpression) and not (o.id in memo):
                    memo[o.id] = o
                    memo.update(o.variables())
                else:
                    memo.update(o.variables())

            return memo

        tree.map_structure(choice_aux, self.__dict__)

        return memo

    def __copy__(self):
        cls = self.__class__
        obj = cls.__new__(cls)

        def copy_aux(obj):

            if isinstance(obj, Expression):
                return copy.copy(obj)
            else:
                return obj

        new__dict__ = tree.map_structure(copy_aux, self.__dict__)
        obj.__dict__.update(new__dict__)

        return obj

    def __deepcopy__(self, memo):
        cls = self.__class__
        obj = cls.__new__(cls)
        memo[id(self)] = obj
        obj.__dict__.update(copy.deepcopy(self.__dict__))
        return obj

    def clone(self, deep=False):
        if deep:
            c = copy.deepcopy(self)
        else:
            c = copy.copy(self)
        return c


class BinaryExpression(Expression):
    """left 'operation' right"""

    def __init__(self, left, right, operator):
        self.left = left
        self.right = right
        self.operator = operator

    def __repr__(self) -> str:
        return f"{self.left} {self.operator} {self.right}"

    def evaluate(self):

        self.evaluate_children()

        operator_implementation = getattr(
            self.left, BIN_OPS_SYNTAX_2_ATTR[self.operator]
        )

        return operator_implementation(self.right)


class UnaryExpression(Expression):
    """operation x"""

    def __init__(self, operator, x):
        self.operator = operator
        self.x = x

    def __repr__(self) -> str:
        return f"{self.operator}{self.x}"

    def evaluate(self):
        self.evaluate_children()

        operator_implementation = getattr(self.x, UNA_OPS_SYNTAX_2_ATTR[self.operator])

        return operator_implementation()


class FunctionCallExpression(Expression):
    def __init__(self, function_parent, function, *args, **kwargs) -> None:
        self.function_parent = function_parent
        self.function = function
        self.args = list(args)
        self.kwargs = kwargs

    def __repr__(self) -> str:
        args = str(self.args)[1:-1]

        kwargs = ""
        for i, (k, v) in enumerate(self.kwargs.items()):
            kwargs += f"{k}={v}"
            if i < len(self.kwargs) - 1:
                kwargs += ", "

        if args != "" and kwargs != "":
            args += ", "

        prefix = self.function_parent.__name__ if self.function_parent else ""
        fname = self.function.__name__
        if fname == "__call__" or fname == "__init__":
            fname = ""

        return (
            f"{prefix}{'.' if prefix and fname != '' else ''}{fname}({args + kwargs})"
        )

    def evaluate(self):

        res = self._evaluate()
        return res

    def _evaluate(self):

        self.evaluate_children()

        if self.function_parent:
            if self.function.__name__ == "__init__":
                # self.function_parent is a class by using the syntax
                # class(*args, **kwargs) we call __init__
                return self.function_parent(*self.args, **self.kwargs)
            else:
                return self.function(self.function_parent, *self.args, **self.kwargs)
        else:
            return self.function(*self.args, **self.kwargs)


class ExpressionItemAccess(Expression):
    def __init__(self, expression, item):
        self.expression = expression
        self.item = item

    def __repr__(self) -> str:
        return f"{self.expression}[{self.item}]"

    def evaluate(self):
        self.evaluate_children()

        return self.expression[self.item]


class ExpressionAttributeAccess(Expression):
    def __init__(self, expression, name):
        self.expression = expression
        self.name = name

    def __repr__(self) -> str:
        return f"{self.expression}.{self.name}"

    def evaluate(self):
        self.evaluate_children()

        return getattr(self.expression, self.name)


class ExpressionCallExpression(Expression):
    def __init__(self, expression, *args, **kwargs) -> None:
        self.expression = expression
        self.args = list(args)
        self.kwargs = kwargs

    def __repr__(self) -> str:
        args = str(self.args)[1:-1]

        kwargs = ""
        for i, (k, v) in enumerate(self.kwargs.items()):
            kwargs += f"{k}={v}"
            if i < len(self.kwargs) - 1:
                kwargs += ", "

        if args != "" and kwargs != "":
            args += ", "

        return f"{self.expression}({args + kwargs})"

    def choices(self):
        memo = self.expression.choices()

        def choice_aux(o):

            if isinstance(o, Expression):

                if isinstance(o, VarExpression):
                    memo[o.id] = o
                else:
                    memo.update(o.choices())

            return memo

        tree.map_structure(choice_aux, self.args)
        tree.map_structure(choice_aux, self.kwargs)

        return memo

    def freeze(self, choice: dict):

        self.expression.freeze(choice)

        # propagate the materialization
        def freeze_aux(o):

            if isinstance(o, Expression):
                o.freeze(choice)

        tree.map_structure(freeze_aux, self.args)
        tree.map_structure(freeze_aux, self.kwargs)

    def evaluate(self):

        self.evaluate_children()

        return self.expression(*self.args, **self.kwargs)


class ObjectExpression(Expression):
    def __init__(self, obj):
        self._obj = obj

    def __call__(self, *args, **kwargs):

        if inspect.isclass(self._obj):
            return FunctionCallExpression(
                self._obj,
                self._obj.__init__,
                *args,
                **kwargs,
            )
        elif inspect.isfunction(self._obj) or (
            inspect.isbuiltin(self._obj) and not (inspect.ismethod(self._obj))
        ):
            return FunctionCallExpression(
                None,  # a function does not have a parent (stateless)
                self._obj,
                *args,
                **kwargs,
            )
        else:
            return FunctionCallExpression(
                self._obj,
                self._obj.__call__,
                *args,
                **kwargs,
            )

    def __repr__(self):
        return self._obj.__repr__()

    def evaluate(self):
        self.evaluate_children()

        return self._obj


class VarExpression(Expression):

    value = None
    var_id = 0

    def __init__(self, name: str = None) -> None:
        super().__init__()
        self._name = name
        self.var_id = VarExpression.var_id
        VarExpression.var_id += 1

    def __eq__(self, other):
        return type(self) is type(other) and self.value == other.value

    def sample(self, size=None, rng=None, memo=None):

        if rng is None:
            rng = np.random.RandomState()

        # memoization in case the same VarExpression is used at different places
        if isinstance(memo, dict) and id(self) in memo:
            return memo[self.id]

        s = self._sample(size=size, rng=rng, memo=memo)

        if isinstance(memo, dict):
            memo[self.id] = s

        return s

    @abc.abstractmethod
    def _sample(self, size=None, rng=None, memo=None):
        raise NotImplementedError

    @property
    def id(self):
        if self._name:
            return self._name
        else:
            return str(self.var_id)

    def freeze(self, choice: dict):
        self.value = choice[self.id]

    def evaluate(self):
        if isinstance(self.value, Expression):
            return self.value.evaluate()
        elif tree.is_nested(self.value):
            return tree.map_structure(
                lambda x: x.evaluate() if isinstance(x, Expression) else x, self.value
            )
        else:
            return self.value

    def choices(self):
        return {self.id: self}


class List(VarExpression):
    """Represent a categorical choice.

    Args:
        values (iterable): an interable with possible values.
        k (int, optional): the number of values selected in values. Defaults to None.
        replace (bool, optional): draw from values with replacement. Defaults to False.
        invariant (bool, optional): values is permutation invariant (e.g., a list of same object types). Defaults to True.
    """

    def __init__(self, values, k=None, replace=False, invariant=False, name=None):

        super().__init__(name=name)
        self._values = list(values)
        self._k = k
        self._replace = replace
        self._invariant = invariant

    def __repr__(self) -> str:
        if not (self.value is None):
            return self.value.__repr__()
        else:
            str_ = str(self._values)
            if self._k:
                str_ += f", k={self._k}"
            if self._replace:
                str_ += f", replace={self._replace}"
            if self._invariant:
                str_ += f", invariant={self._invariant}"
            return f"List(id={self.id}, {str_})"

    def _getitem(self, item):
        if np.issubdtype(type(item), np.integer):
            return self._values[item]
        elif isinstance(item, collections.abc.Iterable):
            return [self._values[i] for i in item]
        else:
            raise ValueError(f"index of List should be int or iterable but is {item} with type '{type(item)}'!")

    def _length(self):
        return len(self._values)

    def __eq__(self, other):
        b = super().__eq__(other)
        return (
            b
            and self._values == other._values
            and self._k == other._k
            and self._replace == other._replace
        )

    def freeze(self, choice: dict):

        if self._k is None:  # "replace" is ignored (only 1 sample is drawn)
            idx = choice[self.id]

            # equivalent to constant 0
            if self._invariant:
                assert idx == 0

            # equivalent to categorical of len(values)
            else:
                assert 0 <= idx and idx < self._length()
                

        else:  # k >= 1

            # equivalent to constant k so "replace" is ignored
            if self._invariant:
                
                if isinstance(self._k, VarExpression):
                    # TODO: add assert
                    idx = [i for i in range(choice[self._k.id])]
                else:
                    # TODO: add assert
                    idx = [i for i in range(choice[self.id])]

            # k Categorical of len(values)
            else:
                idx = choice[self.id]
                assert isinstance(idx, list), "should be a list of 'k' indexes"
                
        self.value = self._getitem(idx)

        if isinstance(idx, collections.abc.Iterable):
            for i in idx:
                if isinstance(self.value[i], Expression):
                    self.value[i].freeze(choice)
        else:
            if isinstance(self.value, Expression):
                self.value.freeze(choice)

    def _sample(self, size=None, rng=None, memo=None):

        if self._k is None:  # "replace" is ignored (only 1 sample is drawn)

            # equivalent to constant 0
            if self._invariant:
                idx = np.zeros((size,)) if size else 0

            # equivalent to categorical of len(values)
            else:
                idx = rng.choice(self._length(), size=size)

        else:  # k >= 1

            # equivalent to constant k so "replace" is ignored
            if self._invariant:
                if isinstance(self._k, VarExpression):
                    idx = self._k.sample(size, rng, memo)
                else:
                    idx = np.full((size,), self._k)

            # k Categorical of len(values)
            else:

                if isinstance(self._k, VarExpression):
                    sample_size = self._k.sample(size, rng, memo)

                    if size:  # sample size is an array
                        idx = [
                            rng.choice(
                                self._length(),
                                size=sample_size[i],
                                replace=self._replace,
                            ).tolist()
                            for i in range(size)
                        ]
                    else:  # sample size is a scalar
                        idx = rng.choice(
                            self._length(),
                            size=sample_size,
                            replace=self._replace,
                        )
                else:  # self._k is and int
                    idx = rng.choice(
                        self._length(),
                        size=self._k,
                        replace=self._replace,
                    )

        return idx

    def child_choices(self):
        memo = {}

        if isinstance(self._k, Expression):
            memo[self._k.id] = self._k.choices()

        for i in range(len(self)):
            value_i = self._getitem(i)
            if isinstance(value_i, Expression):
                memo[value_i.id] = value_i.choices()

        return memo

    # def sub_choice(self):

    #     choices = []
    #     if isinstance(self._k, Expression):
    #         choices.extend(self._k.choice())

    #     for i in range(len(self)):
    #         if isinstance(self._getitem(i), Expression):
    #             choices.extend(self._getitem(i).choice())

    #     return choices


class Int(VarExpression):
    """Defines an discrete variable.

    Args:
        low (int): the lower bound of the variable discrete interval.
        high (int): the upper bound of the variable discrete interval.
    """

    def __init__(self, low: int, high: int, name: str = None):
        super().__init__(name=name)
        self._low = low
        self._high = high
        self._dist = scipy.stats.randint # Default Distribution

    def __repr__(self) -> str:
        if not (self.value is None):
            return self.value.__repr__()
        else:
            return f"Int(id={self.id}, low={self._low}, high={self._high})"

    def __eq__(self, other):
        b = super().__eq__(other)
        return b and self._high == other._upper and self._low == other._lower

    def freeze(self, choice: dict):

        choice = choice[self.id]

        if not (
            isinstance(self._low, VarExpression)
            or isinstance(self._high, VarExpression)
        ):
            if self._low > choice or choice > self._high:
                raise ValueError(
                    f"choice for variable {self} should be between [{self._low}, {self._high}] but is {choice}"
                )
        self.value = choice

    def _sample(self, size=None, rng=None, memo=None):

        low = (
            self._low.sample(size=size, rng=rng, memo=memo)
            if isinstance(self._low, VarExpression)
            else self._low
        )
        high = (
            self._high.sample(size=size, rng=rng, memo=memo)
            if isinstance(self._high, VarExpression)
            else self._high
        )

        return self._dist.rvs(low, high+1, size=size, random_state=rng)

class Float(VarExpression):
    """Defines a continuous variable.

    Args:
        low (float): the lower bound of the variable continuous interval.
        high (float): the upper bound of the variable continuous interval.
    """

    def __init__(self, low: float, high: float, name: str = None):
        super().__init__(name=name)
        self._low = low
        self._high = high
        self._dist = scipy.stats.uniform

    def __repr__(self) -> str:
        if not (self.value is None):
            return self.value.__repr__()
        else:
            return f"Float(id={self.id}, low={self._low}, high={self._high})"

    def __eq__(self, other):
        b = super().__eq__(other)
        return b and self._high == other._upper and self._low == other._lower

    def freeze(self, choice):

        choice = choice[self.id]

        if not (
            isinstance(self._low, VarExpression)
            or isinstance(self._high, VarExpression)
        ):
            if self._low > choice or choice > self._high:
                raise ValueError(
                    f"choice for variable {self} should be between [{self._low}, {self._high}] but is {choice}"
                )
        self.value = choice

    def _sample(self, size=None, rng=None, memo=None):

        low = (
            self._low.sample(size=size, rng=rng, memo=memo)
            if isinstance(self._low, VarExpression)
            else self._low
        )
        high = (
            self._high.sample(size=size, rng=rng, memo=memo)
            if isinstance(self._high, VarExpression)
            else self._high
        )

        return self._dist.rvs(loc=low, scale=high - low, size=size, random_state=rng)

