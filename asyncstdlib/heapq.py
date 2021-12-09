from typing import Generic, AsyncIterator, Tuple, List
import heapq as _heapq

from .builtins import aiter, enumerate as a_enumerate
from ._typing import AnyIterable, LT


class _KeyIter(Generic[LT]):
    __slots__ = ("head", "tail", "reverse", "head_key", "key")

    def __init__(self, head: LT, tail: AsyncIterator[LT], reverse: bool, head_key, key):
        self.head = head
        self.head_key = head_key
        self.tail = tail
        self.key = key
        self.reverse = reverse

    @classmethod
    async def from_iters(
        cls, iterables: Tuple[AnyIterable[LT]], reverse: bool, key
    ) -> "AsyncIterator[_KeyIter[LT]]":
        for iterable in iterables:
            iterator = aiter(iterable)
            try:
                head = await iterator.__anext__()
            except StopAsyncIteration:
                pass
            else:
                yield cls(head, iterator, reverse, await key(head), key)

    async def pull_head(self) -> bool:
        """
        Pulling the next ``head`` element from the iterator and signal success
        """
        try:
            self.head = head = await self.tail.__anext__()
        except StopAsyncIteration:
            return False
        else:
            self.head_key = self.key(head) if self.key is not None else head
            return True

    def __lt__(self, other: "_KeyIter[LT]"):
        return self.reverse ^ (self.head_key < other.head_key)


async def merge(
    *iterables: AnyIterable[LT], key=None, reverse: bool = False
) -> AsyncIterator[LT]:
    """
    Merge all pre-sorted (async) ``iterables`` into a single sorted iterator

    This works similar to ``sorted(chain(*iterables), key=key, reverse=reverse)`` but
    operates lazily: at any moment only one item of each iterable is stored for the
    comparison. This allows merging streams of pre-sorted items, such as timestamped
    records from multiple sources.

    The optional ``key`` argument specifies a one-argument (async) callable, which
    provides a substitute for determining the sort order of each item.
    The special value and default :py:data:`None` represents the identity functions,
    comparing items directly.

    The default sort order is ascending, that is items with ``a < b`` imply ``a``
    is yielded before ``b``. Use ``reverse=True`` for descending sort order.
    The ``iterables`` must be pre-sorted in the same order.
    """
    iter_heap: List[Tuple[_KeyIter, int]] = [
        (itr, idx if not reverse else -idx)
        async for idx, itr
        in a_enumerate(_KeyIter.from_iters(iterables, reverse, key))
    ]
    try:
        _heapq.heapify(iter_heap)
        # there are at least two iterators that need merging
        while len(iter_heap) > 1:
            while True:
                itr, idx = iter_heap[0]
                yield itr.head
                if await itr.pull_head():
                    _heapq.heapreplace(iter_heap, (itr, idx))
                else:
                    _heapq.heappop(iter_heap)
        # there is only one iterator left, no need for merging
        if iter_heap:
            itr, idx = iter_heap[0]
            yield itr.head
            async for item in itr.tail:
                yield item
    finally:
        for itr, _ in iter_heap:
            try:
                aclose = itr.tail.aclose  # type: ignore
            except AttributeError:
                pass
            else:
                await aclose()
