from __future__ import annotations
from typing import Any, List, Optional, Sequence, Set, Union, overload

from dataclasses import dataclass
from enum import Enum
from random import Random

from ferrite.codegen.utils import flatten, indent, is_power_of_2


@dataclass
class Context:
    prefix: Optional[str] = None
    test_attempts: int = 4
    test_rng_seed = 0xdeadbeef


# FIXME: Remove global context
CONTEXT = Context()


class Name:

    def __init__(self, *args: Union[str, List[str], Name, None]):
        self.words: List[str] = []
        for arg in args:
            if isinstance(arg, Name):
                self.words += arg.words
            elif isinstance(arg, list):
                self.words += arg
            elif isinstance(arg, str):
                self.words.append(arg)
            elif arg is None:
                pass
            else:
                raise RuntimeError(f"Unsupported argument {type(arg).__name__}")

    def camel(self) -> str:
        return "".join([s[0].upper() + s[1:].lower() for s in self.words])

    def snake(self) -> str:
        return "_".join([s.lower() for s in self.words])

    @staticmethod
    def from_snake(snake: str) -> Name:
        return Name(snake.split("_"))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Name):
            raise NotImplementedError()
        return self.words == other.words

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Name):
            raise NotImplementedError()
        return not (self == other)

    def __repr__(self) -> str:
        return f"[" + ", ".join(self.words) + "]"


class Location(Enum):
    IMPORT = 0
    DECLARATION = 1
    DEFINITION = 2
    TEST = 3


class Source:

    def __init__(
        self,
        location: Location,
        items: Sequence[List[str]] = [],
        deps: List[Optional[Source]] = [],
    ):
        self.location = location
        self.items = ["\n".join(s) + "\n" for s in items]
        self.deps = [p for p in deps if p is not None]

    def collect(self, location: Location, used: Optional[Set[int]] = None) -> List[str]:
        if used is None:
            used = set()

        result = []

        for dep in self.deps:
            result.extend(dep.collect(location, used))

        if self.location == location:
            for item in self.items:
                item_hash = hash(item)
                if item_hash not in used:
                    result.append(item)
                    used.add(item_hash)

        return result

    def make_source(self, location: Location, separator: str = "\n") -> str:
        return separator.join(self.collect(location))


class Type:

    class NotImplemented(NotImplementedError):

        def __init__(self, owner: Type) -> None:
            super().__init__(f"{type(owner).__name__}: {owner.name}")

    @overload
    def __init__(self, name: Name, align: int, size: int) -> None:
        ...

    @overload
    def __init__(self, name: Name, align: int, size: None, min_size: int) -> None:
        ...

    def __init__(
        self,
        name: Name,
        align: int,
        size: Optional[int],
        min_size: Optional[int] = None,
    ) -> None:
        assert is_power_of_2(align)
        self.name = name
        self.align = align
        if size is None:
            assert min_size is not None
            self._size = None
            self.min_size = min_size
        else:
            assert size % align == 0
            self._size = size
            self.min_size = size

    def is_sized(self) -> bool:
        return self._size is not None

    def is_empty(self) -> bool:
        return self._size == 0

    @property
    def size(self) -> int:
        if self._size is not None:
            return self._size
        else:
            raise self.NotImplemented(self)

    # Runtime

    def load(self, data: bytes) -> Any:
        raise self.NotImplemented(self)

    def store(self, value: Any) -> bytes:
        raise self.NotImplemented(self)

    def default(self) -> Any:
        raise self.NotImplemented(self)

    def random(self, rng: Random) -> Any:
        raise self.NotImplemented(self)

    def is_instance(self, value: Any) -> bool:
        raise self.NotImplemented(self)

    def __instancecheck__(self, value: Any) -> bool:
        return self.is_instance(value)

    # Generation

    def c_type(self) -> str:
        raise self.NotImplemented(self)

    def c_size(self, obj: str) -> str:
        if self.size is not None:
            return str(self.size)
        else:
            raise self.NotImplemented(self)

    def _c_size_extent(self, obj: str) -> str:
        raise self.NotImplemented(self)

    def c_source(self) -> Optional[Source]:
        return None

    def rust_type(self) -> str:
        raise self.NotImplemented(self)

    def rust_size(self, obj: str) -> str:
        if self.size is not None:
            return f"<{self.rust_type()} as FlatSized>::SIZE"
        else:
            return f"<{self.rust_type()} as FlatBase>::size({obj})"

    def rust_source(self) -> Optional[Source]:
        return None

    def pyi_type(self) -> str:
        raise self.NotImplemented(self)

    def pyi_source(self) -> Optional[Source]:
        return None

    # Tests

    def c_check(self, var: str, obj: Any) -> List[str]:
        raise self.NotImplemented(self)

    def rust_check(self, var: str, obj: Any) -> List[str]:
        raise self.NotImplemented(self)

    def rust_object(self, obj: Any) -> str:
        raise self.NotImplemented(self)

    def _make_test_objects(self) -> List[Any]:
        rng = Random(CONTEXT.test_rng_seed)
        return [self.random(rng) for i in range(CONTEXT.test_attempts)]

    def _c_test_name(self) -> str:
        return Name(CONTEXT.prefix, self.name, "test").snake()

    def c_test_source(self) -> Source:
        objs = self._make_test_objects()
        return Source(
            Location.TEST, [[
                f"int {self._c_test_name()}(const uint8_t * const *data) {{",
                *indent([
                    f"const {self.c_type()} *obj;",
                    *flatten(
                        [[
                            f"obj = (const {self.c_type()} *)(data[{i}]);",
                            *self.c_check(f"(*obj)", obj),
                        ] for i, obj in enumerate(objs)],
                        sep=[""],
                    ),
                ]),
                f"}}",
            ]],
            deps=[self.c_source()]
        )

    def rust_test_source(self) -> Source:
        objs = self._make_test_objects()
        return Source(
            Location.TEST, [[
                f"extern \"C\" {{ fn {self._c_test_name()}(data: *const *const u8) -> c_int; }}",
                f"",
                f"#[test]",
                f"fn {self.name.snake()}() {{",
                *indent([
                    f"let data = vec![",
                    *indent(['b"' + "".join([f"\\x{b:02x}" for b in self.store(obj)]) + '"' for obj in objs]),
                    f"]",
                    "",
                    *flatten(
                        [[
                            f"let obj = {self.rust_type()}::reinterpret(&data[{i}]);",
                            *self.rust_check(f"(*obj)", obj),
                        ] for i, obj in enumerate(objs)],
                        sep=[""],
                    ),
                    "",
                    f"let raw_data = data.iter().map(|s| s.as_ptr()).collect::<Vec<_>>();",
                    f"assert_eq!(unsafe {{ {self._c_test_name()}(raw_data.as_ptr()) }}, 0);",
                ]),
                f"}}",
            ]],
            deps=[self.c_source()]
        )
