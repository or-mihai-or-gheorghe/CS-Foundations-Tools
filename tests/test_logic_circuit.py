"""Circuit semantics against truth tables and structural gate constraints."""

from dataclasses import FrozenInstanceError
from itertools import product
import unittest

from tools.logic_circuit import Circuit, Node, build_circuit, evaluate_circuit, gate_counts
from tools.logic_minimization import Cube, minimize_sop


class LogicCircuitTests(unittest.TestCase):
    def assert_structure(self, circuit):
        defined = set()
        arities = {"INPUT": 0, "CONST": 0, "NOT": 1, "AND": 2, "OR": 2}
        for node in circuit.nodes:
            self.assertNotIn(node.id, defined)
            self.assertIn(node.kind, arities)
            self.assertEqual(len(node.inputs), arities[node.kind])
            self.assertTrue(set(node.inputs) <= defined)
            defined.add(node.id)
        self.assertIn(circuit.output, defined)
        self.assertTrue(set(circuit.term_outputs) <= defined)
        self.assertEqual(
            tuple(node.variable for node in circuit.nodes if node.kind == "INPUT"),
            circuit.var_order,
        )

    def assert_truth_table(self, circuit, ones, dont_cares=()):
        for index, bits in enumerate(product((0, 1), repeat=len(circuit.var_order))):
            values = evaluate_circuit(circuit, dict(zip(circuit.var_order, bits)))
            self.assertEqual(set(values), {node.id for node in circuit.nodes})
            self.assertTrue(all(type(value) is int and value in (0, 1) for value in values.values()))
            if index not in dont_cares:
                self.assertEqual(values[circuit.output], int(index in ones), (index, bits, circuit))

    def test_all_boolean_functions_through_three_variables(self):
        for nvars in range(1, 4):
            for table in range(1 << (1 << nvars)):
                ones = {index for index in range(1 << nvars) if table & (1 << index)}
                with self.subTest(nvars=nvars, table=table):
                    result = minimize_sop(nvars, ones)
                    circuit = build_circuit(result.cover, result.var_order)
                    self.assert_structure(circuit)
                    self.assert_truth_table(circuit, ones)
                    self.assertEqual(len(circuit.term_outputs), len(result.cover))

    def test_dont_cares_custom_order_and_unused_variables(self):
        order = ("C", "A", "E")
        ones = {1, 3, 5}
        dont_cares = {0, 2, 7}
        result = minimize_sop(3, ones, dont_cares, var_order=order)
        circuit = build_circuit(result.cover, result.var_order)
        self.assertEqual(circuit.var_order, order)
        self.assert_structure(circuit)
        self.assert_truth_table(circuit, ones, dont_cares)

        result = minimize_sop(3, {4, 5, 6, 7}, var_order=order)
        circuit = build_circuit(result.cover, result.var_order)
        self.assertEqual(circuit.output, "input_C")
        self.assertEqual(gate_counts(circuit)["total"], 0)
        self.assertEqual(len(circuit.nodes), 3)
        self.assert_truth_table(circuit, {4, 5, 6, 7})

    def test_constants_and_direct_wires(self):
        for nvars in (1, 3, 5):
            order = tuple("ABCDE"[:nvars])
            for constant, cubes in ((0, ()), (1, (Cube(nvars, 0, 0),))):
                with self.subTest(nvars=nvars, constant=constant):
                    circuit = build_circuit(cubes, order)
                    self.assert_structure(circuit)
                    self.assertEqual(circuit.output, f"const_{constant}")
                    self.assertEqual(circuit.term_outputs, ("const_1",) if constant else ())
                    self.assertEqual(gate_counts(circuit), {"AND": 0, "OR": 0, "NOT": 0, "total": 0})
                    self.assert_truth_table(circuit, set(range(1 << nvars)) if constant else set())

        positive = build_circuit((Cube(1, 1, 1),), ("E",))
        negative = build_circuit((Cube(1, 1, 0),), ("E",))
        self.assertEqual(positive.output, "input_E")
        self.assertEqual(positive.term_outputs, ("input_E",))
        self.assertEqual(negative.output, "not_E")
        self.assertEqual(gate_counts(negative), {"AND": 0, "OR": 0, "NOT": 1, "total": 1})
        self.assert_truth_table(positive, {1})
        self.assert_truth_table(negative, {0})

    def test_not_sharing_and_term_order(self):
        cubes = (Cube(3, 0b101, 0b001), Cube(3, 0b110, 0b010))  # A'C + A'B
        circuit = build_circuit(cubes, ("A", "B", "C"))
        self.assert_structure(circuit)
        self.assertEqual(gate_counts(circuit), {"AND": 2, "OR": 1, "NOT": 1, "total": 4})
        self.assertEqual(sum(node.kind == "NOT" for node in circuit.nodes), 1)
        for bits in product((0, 1), repeat=3):
            a, b, c = bits
            values = evaluate_circuit(circuit, dict(zip(circuit.var_order, bits)))
            self.assertEqual(values[circuit.term_outputs[0]], int(not a and c))
            self.assertEqual(values[circuit.term_outputs[1]], int(not a and b))
            self.assertEqual(values[circuit.output], int(not a and (b or c)))

    def test_balanced_trees_and_determinism(self):
        order = tuple("ABCDE")
        product_cubes = (Cube(5, 0b11111, 0b11111),)
        sum_cubes = tuple(Cube(5, 1 << bit, 1 << bit) for bit in range(5))
        for cubes, kind in ((product_cubes, "AND"), (sum_cubes, "OR")):
            circuit = build_circuit(cubes, order)
            self.assert_structure(circuit)
            self.assertEqual(circuit, build_circuit(iter(cubes), iter(order)))
            self.assertEqual(gate_counts(circuit)[kind], 4)
            depths = {}
            for node in circuit.nodes:
                depths[node.id] = 0 if not node.inputs else 1 + max(depths[source] for source in node.inputs)
                if node.kind == kind:
                    self.assertLessEqual(abs(depths[node.inputs[0]] - depths[node.inputs[1]]), 1)
            self.assertEqual(depths[circuit.output], 3)
            self.assert_truth_table(circuit, {31} if kind == "AND" else set(range(1, 32)))

        ones = {1, 2, 4, 7}
        first = minimize_sop(3, ones)
        second = minimize_sop(3, reversed(sorted(ones)))
        self.assertEqual(build_circuit(first.cover, first.var_order), build_circuit(second.cover, second.var_order))

    def test_five_variable_parity_has_84_gates(self):
        ones = {index for index in range(32) if index.bit_count() % 2}
        result = minimize_sop(5, ones)
        circuit = build_circuit(result.cover, result.var_order)
        self.assert_structure(circuit)
        self.assertEqual(len(circuit.term_outputs), 16)
        self.assertEqual(gate_counts(circuit), {"AND": 64, "OR": 15, "NOT": 5, "total": 84})
        self.assert_truth_table(circuit, ones)

    def test_five_variable_kmap_regression(self):
        ones = {1, 2, 3, 6}
        result = minimize_sop(5, ones)
        circuit = build_circuit(result.cover, result.var_order)
        self.assert_structure(circuit)
        self.assert_truth_table(circuit, ones)

    def test_immutable_circuit_and_input_validation(self):
        circuit = build_circuit((Cube(1, 1, 0),), ("A",))
        with self.assertRaises(FrozenInstanceError):
            circuit.output = "input_A"
        with self.assertRaises(FrozenInstanceError):
            circuit.nodes[0].id = "changed"
        for assignment in ({}, {"A": 2}, {"A": "0"}, {"A": 0.0}, {"A": 0, "B": 1}):
            with self.subTest(assignment=assignment), self.assertRaises(ValueError):
                evaluate_circuit(circuit, assignment)
        self.assertEqual(evaluate_circuit(circuit, {"A": True})[circuit.output], 0)
        for order in ((), ("A", "A"), ("a",), ("F",)):
            with self.subTest(order=order), self.assertRaises(ValueError):
                build_circuit((), order)
        with self.assertRaises(ValueError):
            build_circuit((Cube(2, 0, 0),), ("A",))

    def test_evaluator_rejects_invalid_gate_shape_or_topology(self):
        input_a = Node("input_A", "INPUT", variable="A")
        for node in (Node("bad", "AND", ("input_A",)),
                     Node("bad", "NOT", ("later",)),
                     Node("bad", "XOR", ("input_A", "input_A"))):
            circuit = Circuit(("A",), (input_a, node), "bad", ("bad",))
            with self.subTest(node=node), self.assertRaises(ValueError):
                evaluate_circuit(circuit, {"A": 0})


if __name__ == "__main__":
    unittest.main()
