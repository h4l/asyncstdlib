from typing import Callable, TypeVar, Awaitable, Union, Any

from ._core import ScopedIter, awaitify as _awaitify, Sentinel
from .builtins import anext, AnyIterable
from ._utility import public_module

from ._lrucache import lru_cache, CacheInfo, LRUAsyncCallable

__all__ = ["lru_cache", "CacheInfo", "LRUAsyncCallable", "reduce", "cached_property"]


T = TypeVar("T")


__REDUCE_SENTINEL = Sentinel("<no default>")


class AwaitableValue:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    # noinspection PyUnreachableCode
    def __await__(self):
        return self.value
        yield


@public_module(__name__, "cached_property")
class CachedProperty:
    def __init__(self, getter: Callable[[Any], Awaitable[T]]):
        self.__wrapped__ = getter
        self._name = getter.__name__
        self.__doc__ = getter.__doc__

    def __set_name__(self, owner, name):
        # Check whether we can store anything on the instance
        # Note that this is a failsafe, and might fail ugly.
        # People who are clever enough to avoid this heuristic
        # should also be clever enough to know the why and what.
        if not any("__dict__" in dir(cls) for cls in owner.__mro__):
            raise TypeError(
                "'cached_property' requires '__dict__' "
                f"on {owner.__name__!r} to store {name}"
            )
        self._name = name

    # noinspection Annotator
    async def __get__(self, instance, owner):
        if instance is None:
            return self
        attributes = instance.__dict__
        try:
            return attributes[self._name]
        except KeyError:
            value = await self.__wrapped__(instance)
            if self._name not in attributes:
                attributes[self._name] = AwaitableValue(value)
            return value


cached_property = CachedProperty


async def reduce(
    function: Union[Callable[[T, T], T], Callable[[T, T], Awaitable[T]]],
    iterable: AnyIterable[T],
    initial: T = __REDUCE_SENTINEL,
) -> T:
    """
    Reduce an (async) iterable by cumulative application of an (async) function

    :raises TypeError: if ``iterable`` is empty and ``initial`` is not given

    Applies the ``function`` from the beginning of ``iterable``, as if executing
    ``await function(current, anext(iterable))`` until ``iterable`` is exhausted.
    Note that the output of ``function`` should be valid as its first input.

    The optional ``initial`` is prepended to all items of ``iterable``
    when applying ``function``. If the combination of ``initial``
    and ``iterable`` contains exactly one item, it is returned without
    calling ``function``.
    """
    async with ScopedIter(iterable) as item_iter:
        try:
            value = (
                initial if initial is not __REDUCE_SENTINEL else await anext(item_iter)
            )
        except StopAsyncIteration:
            raise TypeError("reduce() of empty sequence with no initial value")
        function = _awaitify(function)
        async for head in item_iter:
            value = await function(value, head)
        return value
