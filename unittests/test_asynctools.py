import asyncstdlib as a

from .utility import sync, asyncify


@sync
async def test_nested_lifetime():
    async_iterable = asyncify(range(10))
    values = []
    async with a.scoped_iter(async_iterable) as a1:
        values.append(await a.anext(a1))
        async with a.scoped_iter(a1) as a2:
            values.append(await a.anext(a2))
            print(a2)
        print(a1)
        # original iterator is not closed by inner scope
        async for value in a1:
            values.append(value)
    assert values == list(range(10))


@sync
async def test_borrow_explicitly():
    async_iterable = asyncify(range(10))
    values = []
    borrowed_aiterable = a.borrow(async_iterable)
    values.append(await a.anext(async_iterable))
    values.append(await a.anext(borrowed_aiterable))
    await a.borrow(borrowed_aiterable).aclose()
    values.append(await a.anext(borrowed_aiterable))
    await borrowed_aiterable.aclose()
    values.append(await a.anext(async_iterable))
    assert values == list(range(4))
    async for value in async_iterable:
        values.append(value)
    assert values == list(range(10))