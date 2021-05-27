import logging
import re
from typing import Callable, List, Optional, Tuple, Union

import pytest


RecordFilter = Callable[[logging.LogRecord], bool]


class LogPile:
    __slots__ = ('_records',)

    _records: List[logging.LogRecord]

    def __init__(self):
        self._records = []

    def __len__(self):
        return len(self._records)

    def __iter__(self):
        return iter(self._records)

    # `assert pile.empty()` is more readable than `assert not pile`
    def empty(self) -> bool:
        """Return True if the pile is empty, False otherwise."""
        return not self._records

    def _add(self, record):
        self._records.append(record)

    def _partition(
        self,
        func: Optional[RecordFilter] = None,
        *,
        name: Optional[str] = None,
        message: Optional[str] = None,
    ) -> Tuple[List[logging.LogRecord], List[logging.LogRecord]]:
        filters = []
        if func is not None:
            filters.append(func)

        if name is not None:

            def _filter(record):
                # The same behavior as for `logging.Filter(name=...)`
                return (
                    record.name == name
                    or record.name.startswith(f'{name}.')
                )

            filters.append(_filter)

        if message is not None:

            def _filter(record):
                return re.search(message, record.getMessage())

            filters.append(_filter)

        matching = []
        rest = []
        for record in self._records:
            if all(matches(record) for matches in filters):
                matching.append(record)
            else:
                rest.append(record)
        return matching, rest

    def find(
        self,
        func: Optional[RecordFilter] = None,
        *,
        name: Optional[str] = None,
        message: Optional[str] = None,
    ) -> List[logging.LogRecord]:
        """Return list of matching log records."""
        matching, _ = self._partition(func, name=name, message=message)
        return matching

    def pop(
        self,
        func: Optional[RecordFilter] = None,
        *,
        name: Optional[str] = None,
        message: Optional[str] = None,
    ) -> List[logging.LogRecord]:
        """Return list of matching log records and remove them from the pile.
        """
        matching, rest = self._partition(func, name=name, message=message)

        # Atomically update without locks
        count = len(matching) + len(rest)
        self._records[:count] = rest

        return matching


class LogHandler(logging.Handler):
    __slots__ = ('_pile',)

    def __init__(self, pile):
        self._pile = pile

    def handle(self, record):
        self._pile._records.append(record)


class LogDog:
    __slots__ = ('_logger', '_handler', '_orig_level', '_level')

    def __init__(self, name=None, level=None):
        self._logger = logging.getLogger(name)
        self._level = level

    def __enter__(self):
        pile = LogPile()
        self._handler = LogHandler(pile)
        if self._level is not None:
            self._handler.setLevel(self._level)

        self._logger.addHandler(self._handler)

        if self._level is not None:
            self._orig_level = self._logger.level
            # Argument `level` can be `None`, `int` or `str`, while
            # `handler.level` is always `int` (converted by `setLevel()`
            # method)
            self._logger.setLevel(min(self._orig_level, self._handler.level))

        return pile

    def __exit__(self, type, value, traceback):
        if self._level is not None:
            self._logger.setLevel(self._orig_level)

        self._logger.removeHandler(self._handler)


@pytest.fixture
def logdog():
    """Scoped log capturing and testing tool."""
    return LogDog
