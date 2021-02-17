from typing import Any

class DelayedQueue:
    delay_sec: Any = ...
    def __init__(self, delay: Any) -> None: ...
    def put(self, element: Any, delay: bool = ...) -> None: ...
    def close(self) -> None: ...
    def get(self): ...
    def remove(self, predicate: Any): ...