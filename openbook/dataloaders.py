from __future__ import annotations

import dataclasses
from asyncio import create_task, gather
from asyncio.futures import Future
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    Hashable,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

from strawberry.exceptions import WrongNumberOfResultsReturned

if TYPE_CHECKING:
    from asyncio.events import AbstractEventLoop


from django.db.models import Q
from strawberry.dataloader import DataLoader, AbstractCache, DefaultCache

from openbook_posts.models import Post as PostModel
from openbook_posts.models import PostComment as PostCommentModel


T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


@dataclass
class LoaderTask(Generic[K, V, T]):
    key: K
    context: V
    future: Future


@dataclass
class Batch2(Generic[K, V, T]):
    tasks: List[LoaderTask] = dataclasses.field(default_factory=list)
    dispatched: bool = False

    def add_task(self, key: Any, context: Any, future: Future) -> None:
        task = LoaderTask[K, V, T](key, context, future)
        self.tasks.append(task)

    def __len__(self) -> int:
        return len(self.tasks)


class MyDataLoader(DataLoader):
    batch: Optional[Batch2[K, T]] = None
    cache: bool = False
    cache_map: AbstractCache[K, T]

    def __init__(
        self,
        load_fn: Callable[[List[K], V], Awaitable[Sequence[Union[T, BaseException]]]],
        max_batch_size: Optional[int] = None,
        cache: bool = True,
        loop: Optional[AbstractEventLoop] = None,
        cache_map: Optional[AbstractCache[K, T]] = None,
        cache_key_fn: Optional[Callable[[K], Hashable]] = None,
    ):
        self.load_fn = load_fn
        self.max_batch_size = max_batch_size

        self._loop = loop

        self.cache = cache

        if self.cache:
            self.cache_map = DefaultCache(cache_key_fn) if cache_map is None else cache_map

    def load2(self, key1: K, context: V) -> Awaitable[T]:
        if self.cache:
            future = self.cache_map.get((key1, context))

            if future and not future.cancelled():
                return future

        future = self.loop.create_future()

        if self.cache:
            self.cache_map.set((key1, context), future)

        batch = get_current_batch(self)
        batch.add_task(key1, context, future)

        return future

    def load_many2(self, keys: Iterable[K], context: V) -> Awaitable[List[T]]:
        return gather(*[self.load2(key, context) for key in keys])


def should_create_new_batch(loader: MyDataLoader, batch: Batch2) -> bool:
    if batch.dispatched or loader.max_batch_size and len(batch) >= loader.max_batch_size:
        return True

    return False


def get_current_batch(loader: MyDataLoader) -> Batch2:
    if loader.batch and not should_create_new_batch(loader, loader.batch):
        return loader.batch

    loader.batch = Batch2()

    dispatch2(loader, loader.batch)

    return loader.batch


def dispatch2(loader: MyDataLoader, batch: Batch2) -> None:
    loader.loop.call_soon(create_task, dispatch_batch2(loader, batch))


async def dispatch_batch2(loader: MyDataLoader, batch: Batch2) -> None:
    batch.dispatched = True

    keys = [task.key for task in batch.tasks]
    context = [task.context for task in batch.tasks]
    print(context)
    if len(keys) == 0 or len(context) == 0:
        # Ensure batch is not empty
        # Unlikely, but could happen if the tasks are
        # overriden with preset values
        return

    # TODO: check if load_fn return an awaitable and it is a list

    try:
        values = await loader.load_fn(keys, context[0])
        values = list(values)

        if len(values) != len(batch):
            raise WrongNumberOfResultsReturned(expected=len(batch), received=len(values))

        for task, value in zip(batch.tasks, values):
            # Trying to set_result in a cancelled future would raise
            # asyncio.exceptions.InvalidStateError
            if task.future.cancelled():
                continue

            if isinstance(value, BaseException):
                task.future.set_exception(value)
            else:
                task.future.set_result(value)
    except Exception as e:
        for task in batch.tasks:
            task.future.set_exception(e)


async def load_posts(keys, context) -> List["Post"]:
    return [
        PostModel.objects.filter(Q(insights__id=insight) & PostModel.is_visible_query(context)) for insight in keys
    ]


async def load_comments(keys, context) -> List["PostComment"]:
    return [
        PostCommentModel.objects.filter(Q(post__insights__id=insight) & PostCommentModel.is_visible_query(context))
        for insight in keys
    ]
