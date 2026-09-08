"""Independent semantic checks for the bounded exact SOP minimizer."""

from dataclasses import FrozenInstanceError
from itertools import combinations, product
import random
import unittest

from tools.logic_minimization import Cube, cube_segments, minimize_sop, normalize_var_order


def pattern_support(pattern):
    return frozenset(
        minterm for minterm in range(2 ** len(pattern))
        if all(literal == "-" or literal == bit
               for literal, bit in zip(pattern, format(minterm, f"0{len(pattern)}b")))
    )


def cube_from_pattern(pattern):
    care = int("".join("0" if literal == "-" else "1" for literal in pattern), 2)
    value = int(pattern.replace("-", "0"), 2)
    return Cube(len(pattern), care, value)


def gray_grid(nvars):
    row_bits = {1: 0, 2: 1, 3: 1, 4: 2, 5: 2}[nvars]
    column_bits = nvars - row_bits
    return tuple(tuple(((row ^ (row >> 1)) << column_bits) | (col ^ (col >> 1))
                       for col in range(2 ** column_bits))
                 for row in range(2 ** row_bits))


def exhaustive_oracle(catalog, ones, dont_cares):
    """Try every subset of prime patterns, independently of the production DP."""
    allowed = ones | dont_cares
    valid = [(pattern, support) for pattern, support in catalog
             if support & ones and support <= allowed]
    primes = sorted((pattern, support) for pattern, support in valid
                    if not any(support < other for _, other in valid))
    for term_count in range(len(primes) + 1):
        feasible = []
        for selection in combinations(primes, term_count):
            covered = frozenset().union(*(support for _, support in selection))
            if ones <= covered:
                patterns = tuple(pattern for pattern, _ in selection)
                feasible.append((term_count, sum(len(p) - p.count("-") for p in patterns), patterns))
        if feasible:
            return min(feasible), tuple(pattern for pattern, _ in primes)
    raise AssertionError("A singleton minterm is always a valid covering cube.")


class ExactMinimizationTests(unittest.TestCase):
    def assert_semantics(self, result):
        covered = frozenset().union(*(pattern_support(cube.pattern) for cube in result.cover))
        self.assertLessEqual(result.ones, covered)
        self.assertLessEqual(covered, result.ones | result.dont_cares)
        self.assertEqual(tuple(cube.pattern for cube in result.cover), tuple(sorted(cube.pattern for cube in result.cover)))
        for cube in result.primes:
            support = pattern_support(cube.pattern)
            self.assertTrue(support & result.ones)
            self.assertLessEqual(support, result.ones | result.dont_cares)
            self.assertEqual(cube.covered_minterms, support)

    def test_all_6561_three_variable_ternary_tables_against_subset_oracle(self):
        catalog = [("".join(pattern), pattern_support("".join(pattern)))
                   for pattern in product("-01", repeat=3)]
        for table in product((0, 1, 2), repeat=8):
            ones = frozenset(m for m, value in enumerate(table) if value == 1)
            dont_cares = frozenset(m for m, value in enumerate(table) if value == 2)
            result = minimize_sop(3, ones, dont_cares)
            expected, primes = exhaustive_oracle(catalog, ones, dont_cares)
            self.assertEqual(result.cost, expected, table)
            self.assertEqual(tuple(cube.pattern for cube in result.primes), primes, table)
            self.assert_semantics(result)

    def test_ki003_and_noncontiguous_implicants(self):
        result = minimize_sop(5, {1, 2, 3, 6})
        self.assertEqual(result.cost, (2, 8, ("00-10", "000-1")))
        self.assert_semantics(result)
        self.assertEqual(frozenset().union(*(cube.covered_minterms for cube in result.cover)), {1, 2, 3, 6})

        result = minimize_sop(5, {0, 2, 4, 6})
        self.assertEqual(result.cost, (1, 3, ("00--0",)))
        self.assertEqual(result.sop, "A'·B'·E'")
        self.assertEqual(cube_segments(result.cover[0], gray_grid(5)),
                         ((0, 0, 1, 1), (0, 3, 1, 2), (0, 7, 1, 1)))
        expanded = minimize_sop(5, {0, 2}, {4, 6})
        self.assertEqual(expanded.cover, result.cover)
        self.assert_semantics(expanded)

    def test_exact_cover_beats_greedy_and_has_canonical_ties(self):
        result = minimize_sop(3, {1, 2, 3, 4, 5, 6})
        self.assertEqual(result.cost, (3, 6, ("-01", "01-", "1-0")))
        repeated = minimize_sop(3, [6, 5, 4, 3, 2, 1, 1])
        self.assertEqual(result, repeated)

    def test_constants_preserve_the_input_domain(self):
        for nvars in range(1, 6):
            domain = set(range(2 ** nvars))
            for dont_cares in (set(), domain, {0}):
                result = minimize_sop(nvars, set(), dont_cares)
                self.assertEqual(result.sop, "0")
                self.assertEqual(result.cover, ())
                self.assertEqual(result.cost, (0, 0, ()))
                self.assertEqual(len(result.var_order), nvars)
            for ones, dont_cares in ((domain, set()), ({0}, domain - {0})):
                result = minimize_sop(nvars, ones, dont_cares)
                self.assertEqual(result.sop, "1")
                self.assertEqual(result.cover, (Cube(nvars, 0, 0),))
                self.assertEqual(result.cost, (1, 0, ("-" * nvars,)))
                self.assert_semantics(result)

    def test_seeded_five_variable_samples(self):
        rng = random.Random(20260908)
        for _ in range(150):
            table = [rng.randrange(3) for _ in range(32)]
            ones = {m for m, value in enumerate(table) if value == 1}
            dont_cares = {m for m, value in enumerate(table) if value == 2}
            result = minimize_sop(5, ones, dont_cares, "edcba")
            self.assert_semantics(result)
            self.assertEqual(result, minimize_sop(5, sorted(ones, reverse=True), sorted(dont_cares), "EDCBA"))

    def test_variable_order_prefix_validation_and_term_mapping(self):
        self.assertEqual(normalize_var_order(3, "abcde"), ("A", "B", "C"))
        self.assertEqual(normalize_var_order(5, "ABCDEA"), tuple("ABCDE"))
        self.assertEqual(normalize_var_order(3, "c, a, b, d, e"), ("C", "A", "B"))
        self.assertEqual(normalize_var_order(2, (" e ", "d", "a")), ("E", "D"))
        for order in ("AaBCD", "AB", "A?BC", ("A", "B", 3), ("AA", "B", "C")):
            with self.subTest(order=order), self.assertRaises(ValueError):
                normalize_var_order(3, order)
        result = minimize_sop(5, {0, 2, 4, 6}, var_order="EDCBA")
        self.assertEqual(result.sop, "E'·D'·A'")
        self.assertEqual(result.cover[0].literals, (0, 0, None, None, 0))

    def test_invalid_domains_and_masks(self):
        for nvars in (0, 6, -1, True, 3.0):
            with self.subTest(nvars=nvars), self.assertRaises(ValueError):
                minimize_sop(nvars, set())
        for ones, dont_cares in (({-1}, set()), ({8}, set()), ({1}, {1}),
                                 ([1, True], set()), ([1, 1.0], set()), ({1}, {8})):
            with self.subTest(ones=ones, dont_cares=dont_cares), self.assertRaises(ValueError):
                minimize_sop(3, ones, dont_cares)
        for args in ((0, 0, 0), (6, 0, 0), (3, 8, 0), (3, 0, 1), (3, -1, 0), (3, True, 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                Cube(*args)

    def test_results_are_immutable_and_detached_from_inputs(self):
        ones, dont_cares, order = {0}, {1}, ["A", "B"]
        result = minimize_sop(2, ones, dont_cares, order)
        ones.add(3)
        dont_cares.clear()
        order.reverse()
        self.assertEqual(result.ones, {0})
        self.assertEqual(result.dont_cares, {1})
        self.assertEqual(result.var_order, ("A", "B"))
        with self.assertRaises(FrozenInstanceError):
            result.nvars = 3
        with self.assertRaises(FrozenInstanceError):
            result.cover[0].care_mask = 0


class CubeGeometryTests(unittest.TestCase):
    def test_all_363_cubes_have_exact_nonoverlapping_segments(self):
        count = 0
        for nvars in range(1, 6):
            grid = gray_grid(nvars)
            for pattern_tuple in product("-01", repeat=nvars):
                pattern = "".join(pattern_tuple)
                cube = cube_from_pattern(pattern)
                segments = cube_segments(cube, grid)
                represented = []
                for row, column, height, width in segments:
                    self.assertGreater(height, 0)
                    self.assertGreater(width, 0)
                    self.assertLessEqual(row + height, len(grid))
                    self.assertLessEqual(column + width, len(grid[0]))
                    represented.extend(grid[row + dr][column + dc]
                                       for dr in range(height) for dc in range(width))
                self.assertEqual(frozenset(represented), pattern_support(pattern), pattern)
                self.assertEqual(len(represented), len(set(represented)), pattern)
                self.assertEqual(cube.pattern, pattern)
                count += 1
        self.assertEqual(count, 363)

    def test_mapping_validation(self):
        cube = Cube(2, 0, 0)
        for grid in ((), ((),), ((0, 1), (2,)), ((0, 1), (2, 2)), ((0, 1), (2, 4)), ((False, 1), (2, 3))):
            with self.subTest(grid=grid), self.assertRaises(ValueError):
                cube_segments(cube, grid)


if __name__ == "__main__":
    unittest.main()
