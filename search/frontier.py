import heapq
from itertools import count

from .node import SearchNode


class BestFirstFrontier:
    def __init__(self):
        self._items: list[tuple[float, int, SearchNode]] = []
        self._counter = count()

    def push(self, node: SearchNode, priority: float) -> None:
        heapq.heappush(self._items, (-priority, next(self._counter), node))

    def pop(self) -> SearchNode:
        return heapq.heappop(self._items)[2]

    def __bool__(self) -> bool:
        return bool(self._items)
