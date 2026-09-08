"""Exact, dependency-free SOP minimization for at most five variables."""

from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from typing import Iterable, Sequence


VARIABLES = "ABCDE"


def _validate_nvars(nvars: int) -> None:
    if type(nvars) is not int or not 1 <= nvars <= 5:
        raise ValueError("Number of variables must be an integer in 1..5.")


def normalize_var_order(nvars: int, var_order=None) -> tuple[str, ...]:
    """Uppercase and validate the first n names, preserving their MSB order.

    Strings may separate names with whitespace or commas. Additional names after
    the first n are ignored; duplicate names inside the selected prefix are errors.
    """
    _validate_nvars(nvars)
    if var_order is None:
        return tuple(VARIABLES[:nvars])
    if isinstance(var_order, str):
        names = tuple(ch for ch in var_order.upper() if not ch.isspace() and ch != ",")[:nvars]
    else:
        try:
            names = tuple(var_order)[:nvars]
        except TypeError as exc:
            raise ValueError("Variable order must contain names from A to E.") from exc
        names = tuple(name.strip().upper() if isinstance(name, str) else name for name in names)
    if len(names) != nvars or any(type(name) is not str or name not in VARIABLES or len(name) != 1 for name in names):
        raise ValueError(f"Provide {nvars} variable names from A to E.")
    if len(set(names)) != nvars:
        raise ValueError("The selected variable names must be distinct.")
    return names


@dataclass(frozen=True)
class Cube:
    """A Boolean cube: m is covered exactly when m & care_mask == value_mask."""

    nvars: int
    care_mask: int
    value_mask: int

    def __post_init__(self) -> None:
        _validate_nvars(self.nvars)
        limit = 1 << self.nvars
        if (type(self.care_mask) is not int or type(self.value_mask) is not int
                or not 0 <= self.care_mask < limit or not 0 <= self.value_mask < limit
                or self.value_mask & ~self.care_mask):
            raise ValueError("Cube masks must fit its variables; values may set only cared bits.")

    @property
    def literals(self) -> tuple[int | None, ...]:
        return tuple(
            (self.value_mask >> shift) & 1 if (self.care_mask >> shift) & 1 else None
            for shift in reversed(range(self.nvars))
        )

    @property
    def pattern(self) -> str:
        return "".join("-" if value is None else str(value) for value in self.literals)

    @property
    def literal_count(self) -> int:
        return self.care_mask.bit_count()

    @property
    def covered_minterms(self) -> frozenset[int]:
        return frozenset(m for m in range(1 << self.nvars) if m & self.care_mask == self.value_mask)

    def to_term(self, var_order: Sequence[str]) -> str:
        return cube_to_term(self, var_order)


def cube_to_term(cube: Cube, var_order: Sequence[str]) -> str:
    names = normalize_var_order(cube.nvars, var_order)
    terms = [name if value else f"{name}'" for name, value in zip(names, cube.literals) if value is not None]
    return "·".join(terms) or "1"


@dataclass(frozen=True)
class MinimizationResult:
    nvars: int
    var_order: tuple[str, ...]
    ones: frozenset[int]
    dont_cares: frozenset[int]
    primes: tuple[Cube, ...]
    cover: tuple[Cube, ...]

    @property
    def terms(self) -> tuple[str, ...]:
        return tuple(cube.to_term(self.var_order) for cube in self.cover)

    @property
    def sop(self) -> str:
        return " + ".join(self.terms) or "0"

    @property
    def cost(self) -> tuple[int, int, tuple[str, ...]]:
        return (len(self.cover), sum(cube.literal_count for cube in self.cover),
                tuple(cube.pattern for cube in self.cover))


def _minterms(nvars: int, values: Iterable[int], label: str) -> frozenset[int]:
    try:
        values = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{label} must be an iterable of integer minterms.") from exc
    if any(type(value) is not int or not 0 <= value < 1 << nvars for value in values):
        raise ValueError(f"{label} must contain integers in 0..{(1 << nvars) - 1}.")
    return frozenset(values)


def _prime_cubes(nvars: int, ones: frozenset[int], dont_cares: frozenset[int]) -> tuple[Cube, ...]:
    allowed = ones | dont_cares
    valid = []
    for literals in product((None, 0, 1), repeat=nvars):
        care = value = 0
        for literal in literals:
            care = (care << 1) | (literal is not None)
            value = (value << 1) | (literal == 1)
        cube = Cube(nvars, care, value)
        support = cube.covered_minterms
        if support & ones and support <= allowed:
            valid.append((cube, support))
    return tuple(sorted(
        (cube for cube, support in valid if not any(support < other for _, other in valid)),
        key=lambda cube: cube.pattern,
    ))


def minimize_sop(nvars: int, ones: Iterable[int], dont_cares: Iterable[int] = (),
                 var_order=None) -> MinimizationResult:
    """Minimize (terms, literal occurrences, sorted cube patterns) exactly.

    Don't-cares permit cube expansion but never require coverage. With no required
    ones, choose F=0, including the entirely unspecified truth table.
    """
    _validate_nvars(nvars)
    names = normalize_var_order(nvars, var_order)
    ones = _minterms(nvars, ones, "Ones")
    dont_cares = _minterms(nvars, dont_cares, "Don't-cares")
    if ones & dont_cares:
        raise ValueError("A minterm cannot be both one and don't-care.")
    if not ones:
        return MinimizationResult(nvars, names, ones, dont_cares, (), ())

    primes = _prime_cubes(nvars, ones, dont_cares)
    supports = tuple(sum(1 << m for m in cube.covered_minterms) for cube in primes)
    candidates = {m: tuple(i for i, support in enumerate(supports) if support & (1 << m))
                  for m in sorted(ones)}
    if any(not options for options in candidates.values()):
        raise RuntimeError("Internal error: a required minterm has no implicant.")

    @lru_cache(maxsize=None)
    def solve(uncovered: int) -> tuple[int, int, tuple[int, ...]]:
        if not uncovered:
            return (0, 0, ())
        pivot = min((m for m in candidates if uncovered & (1 << m)),
                    key=lambda m: (len(candidates[m]), m))
        solutions = []
        for index in candidates[pivot]:
            rest = solve(uncovered & ~supports[index])
            # Indices follow sorted patterns, so index ties equal pattern ties.
            solutions.append((1 + rest[0], primes[index].literal_count + rest[1],
                              tuple(sorted((index,) + rest[2]))))
        return min(solutions)

    best = solve(sum(1 << m for m in ones))
    cover = tuple(primes[index] for index in best[2])
    solve.cache_clear()
    return MinimizationResult(nvars, names, ones, dont_cares, primes, cover)


def cube_segments(cube: Cube, cell_to_min: Sequence[Sequence[int]]) -> tuple[tuple[int, int, int, int], ...]:
    """Return exact non-wrapping (row, column, height, width) drawing segments.

    Each minterm must occur once in the rectangular mapping. Horizontal runs are
    merged vertically when identical; separated segments remain one logical cube.
    """
    try:
        grid = tuple(tuple(row) for row in cell_to_min)
    except TypeError as exc:
        raise ValueError("Cell mapping must be a rectangular grid.") from exc
    if not grid or not grid[0] or any(len(row) != len(grid[0]) for row in grid):
        raise ValueError("Cell mapping must be a nonempty rectangular grid.")
    flat = tuple(m for row in grid for m in row)
    if (len(flat) != 1 << cube.nvars or any(type(m) is not int for m in flat)
            or set(flat) != set(range(1 << cube.nvars))):
        raise ValueError("Cell mapping must contain every minterm exactly once.")
    covered = cube.covered_minterms
    segments = []
    active = {}
    for row_index, row in enumerate(grid):
        runs = []
        for column, minterm in enumerate(row):
            if minterm in covered:
                if runs and runs[-1][0] + runs[-1][1] == column:
                    start, width = runs[-1]
                    runs[-1] = (start, width + 1)
                else:
                    runs.append((column, 1))
        next_active = {}
        for column, width in runs:
            key = (column, width)
            if key in active:
                index = active[key]
                start_row, _, height, _ = segments[index]
                segments[index] = (start_row, column, height + 1, width)
            else:
                index = len(segments)
                segments.append((row_index, column, 1, width))
            next_active[key] = index
        active = next_active
    return tuple(sorted(segments))
