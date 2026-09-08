"""Adder semantics checked against arithmetic, including text-to-wire ordering."""

from dataclasses import replace
from itertools import product
import unittest

from tools.logic_adder import (
    FULL_ADDER_TABLE, build_four_bit_adder, build_full_adder, evaluate_four_bit,
    build_xor_four_bit_adder, build_xor_full_adder, operand_assignment, parse_operand,
)
from tools.logic_circuit import SignalOutput, evaluate_circuit, evaluate_network, gate_counts


class FullAdderTests(unittest.TestCase):
    def test_all_truth_rows_and_both_standalone_branches(self):
        adder = build_full_adder()
        stage = adder.stages[0]
        for index, (a, b, carry) in enumerate(product((0, 1), repeat=3)):
            with self.subTest(a=a, b=b, carry=carry):
                total = a + b + carry
                self.assertEqual(FULL_ADDER_TABLE[index], (a, b, carry, total % 2, total // 2))
                values = evaluate_network(adder.network, {"A": a, "B": b, "Cin": carry})
                self.assertEqual(values[stage.sum_output], total % 2)
                self.assertEqual(values[stage.carry_output], total // 2)
                for circuit, mapping in ((adder.sum_circuit, stage.sum_nodes),
                                         (adder.carry_circuit, stage.carry_nodes)):
                    local = evaluate_circuit(circuit, {"A": a, "B": b, "C": carry})
                    self.assertEqual(local, {source: values[target] for source, target in mapping})

    def test_kmap_groups_have_the_same_order_as_sop_terms(self):
        adder = build_full_adder()
        self.assertEqual([tuple(sorted(c.covered_minterms)) for c in adder.sum_result.cover],
                         [(1,), (2,), (4,), (7,)])
        self.assertEqual([tuple(sorted(c.covered_minterms)) for c in adder.carry_result.cover],
                         [(3, 7), (5, 7), (6, 7)])
        self.assertEqual(adder.carry_result.terms, ("B·C", "A·C", "A·B"))

    def test_real_carry_connections_and_repeated_gate_structure(self):
        one = build_full_adder()
        four = build_four_bit_adder()
        self.assertEqual(gate_counts(one.network), {"AND": 11, "OR": 5, "NOT": 3, "total": 19})
        self.assertEqual(gate_counts(four.network), {"AND": 44, "OR": 20, "NOT": 12, "total": 76})
        self.assertEqual(tuple(output.name for output in four.network.outputs),
                         ("S3", "S2", "S1", "S0", "C4"))
        for adder, input_count in ((one, 3), (four, 8)):
            network = adder.network
            nodes = {node.id: node for node in network.nodes}
            self.assertEqual(len(nodes), len(network.nodes))
            self.assertEqual(sum(node.kind == "INPUT" for node in network.nodes), input_count)
            self.assertEqual(tuple(node.variable for node in network.nodes if node.kind == "INPUT"),
                             network.var_order)
            seen = set()
            for node in network.nodes:
                self.assertEqual(len(node.inputs), {"INPUT": 0, "CONST": 0, "NOT": 1,
                                                   "AND": 2, "OR": 2}[node.kind])
                self.assertTrue(set(node.inputs) <= seen)
                seen.add(node.id)
            for stage in adder.stages:
                for mapping in (dict(stage.sum_nodes), dict(stage.carry_nodes)):
                    self.assertEqual(tuple(mapping[f"input_{v}"] for v in "ABC"), stage.inputs)
        nodes = {node.id: node for node in four.network.nodes}
        self.assertEqual(nodes[four.stages[0].inputs[2]].kind, "CONST")
        self.assertEqual(nodes[four.stages[0].inputs[2]].constant, 0)
        for previous, stage in zip(four.stages, four.stages[1:]):
            self.assertEqual(stage.inputs[2], previous.carry_output)
            self.assertEqual(nodes[stage.inputs[2]].kind, "OR")

    def test_all_256_operand_pairs_and_every_intermediate_carry(self):
        adder = build_four_bit_adder()
        for a, b in product(range(16), repeat=2):
            with self.subTest(a=a, b=b):
                result = evaluate_four_bit(adder, f"{a:04b}", f"{b:04b}")
                self.assertEqual(result.sum_bits, f"{(a + b) % 16:04b}")
                self.assertEqual(result.carry_out, (a + b) // 16)
                self.assertEqual(result.full_bits, f"{a + b:05b}")
                carry = 0
                for i, actual in enumerate(result.stages):
                    ai, bi = (a >> i) & 1, (b >> i) & 1
                    total = ai + bi + carry
                    self.assertEqual(actual, (i, ai, bi, carry, total % 2, total // 2))
                    carry = total // 2

    def test_operand_validation_and_msb_lsb_mapping(self):
        self.assertEqual(parse_operand(" \t0001\n"), "0001")
        for invalid in ("", "0", "111", "11111", "0b01", "10 1", "1012", "１２３４", None, 1):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_operand(invalid)
        assignment = operand_assignment("0001", "1000")
        self.assertEqual({key for key, value in assignment.items() if value}, {"A0", "B3"})
        for bits in ("0001", "1000"):
            self.assertEqual(evaluate_four_bit(build_four_bit_adder(), bits, "0000").sum_bits, bits)
        with self.assertRaises(ValueError):
            evaluate_four_bit(build_full_adder(), "0000", "0000")

    def test_network_rejects_invalid_bindings_outputs_and_gate_order(self):
        network = build_full_adder().network
        assignment = {"A": 1, "B": 0, "Cin": 1}
        invalid = (
            replace(network, outputs=(SignalOutput("S", "missing"),)),
            replace(network, outputs=(network.outputs[0], network.outputs[0])),
            replace(network, nodes=network.nodes + (network.nodes[0],)),
            replace(network, nodes=tuple(reversed(network.nodes))),
        )
        for candidate in invalid:
            with self.subTest(candidate=candidate.outputs), self.assertRaises(ValueError):
                evaluate_network(candidate, assignment)
        for candidate in ({"A": 1, "B": 0}, {**assignment, "C0": 0}, {**assignment, "A": 2}):
            with self.subTest(assignment=candidate), self.assertRaises(ValueError):
                evaluate_network(network, candidate)


class XorAdderTests(unittest.TestCase):
    def test_all_eight_full_adder_states_match_arithmetic_and_sop(self):
        adder = build_xor_full_adder()
        sop = build_full_adder()
        for a, b, cin in product((0, 1), repeat=3):
            with self.subTest(a=a, b=b, cin=cin):
                assignment = {"A": a, "B": b, "Cin": cin}
                values = evaluate_network(adder.network, assignment)
                sop_values = evaluate_network(sop.network, assignment)
                actual = tuple(values[output.source] for output in adder.network.outputs)
                expected = tuple(sop_values[output.source] for output in sop.network.outputs)
                self.assertEqual(actual, expected)
                self.assertEqual(actual, ((a + b + cin) % 2, (a + b + cin) // 2))
                self.assertEqual(values["fa0.xor_ab"], a ^ b)
                self.assertEqual(values["fa0.and_ab"], a & b)
                self.assertEqual(values["fa0.and_carry"], (a ^ b) & cin)

    def test_all_256_pairs_and_each_carry_match_arithmetic_and_sop(self):
        adder = build_xor_four_bit_adder()
        sop = build_four_bit_adder()
        for a, b in product(range(16), repeat=2):
            with self.subTest(a=a, b=b):
                operands = (f"{a:04b}", f"{b:04b}")
                result = evaluate_four_bit(adder, *operands)
                sop_result = evaluate_four_bit(sop, *operands)
                self.assertEqual(result.full_bits, f"{a + b:05b}")
                self.assertEqual(result.sum_bits, f"{(a + b) % 16:04b}")
                self.assertEqual(result.carry_out, (a + b) // 16)
                self.assertEqual(result.stages, sop_result.stages)
                carry = 0
                for i, actual in enumerate(result.stages):
                    ai, bi = (a >> i) & 1, (b >> i) & 1
                    total = ai + bi + carry
                    self.assertEqual(actual, (i, ai, bi, carry, total % 2, total // 2))
                    carry = total // 2

    def test_five_gates_per_stage_and_actual_internal_carry_connections(self):
        one = build_xor_full_adder()
        four = build_xor_four_bit_adder()
        self.assertIs(one, build_xor_full_adder())
        self.assertIs(four, build_xor_four_bit_adder())
        self.assertEqual(gate_counts(one.network), {"AND": 2, "OR": 1, "NOT": 0, "XOR": 2, "total": 5})
        self.assertEqual(gate_counts(four.network), {"AND": 8, "OR": 4, "NOT": 0, "XOR": 8, "total": 20})
        for adder, reference in ((one, build_full_adder()), (four, build_four_bit_adder())):
            self.assertEqual(adder.network.var_order, reference.network.var_order)
            self.assertEqual(tuple(output.name for output in adder.network.outputs),
                             tuple(output.name for output in reference.network.outputs))
            nodes = {node.id: node for node in adder.network.nodes}
            self.assertEqual(len(nodes), len(adder.network.nodes))
            seen = set()
            for node in adder.network.nodes:
                self.assertTrue(set(node.inputs) <= seen)
                self.assertEqual(len(node.inputs), 0 if node.kind in ("INPUT", "CONST") else 2)
                seen.add(node.id)
            for stage in adder.stages:
                a, b, cin = stage.inputs
                prefix = f"fa{stage.index}."
                self.assertEqual(nodes[prefix + "xor_ab"].inputs, (a, b))
                self.assertEqual(nodes[stage.sum_output].inputs, (prefix + "xor_ab", cin))
                self.assertEqual(nodes[prefix + "and_ab"].inputs, (a, b))
                self.assertEqual(nodes[prefix + "and_carry"].inputs, (prefix + "xor_ab", cin))
                self.assertEqual(nodes[stage.carry_output].inputs,
                                 (prefix + "and_ab", prefix + "and_carry"))
                self.assertEqual((stage.sum_nodes, stage.carry_nodes), ((), ()))
        self.assertEqual(one.stages[0].inputs, ("input_A", "input_B", "input_Cin"))
        nodes = {node.id: node for node in four.network.nodes}
        self.assertEqual(nodes[four.stages[0].inputs[2]].kind, "CONST")
        self.assertEqual(nodes[four.stages[0].inputs[2]].constant, 0)
        for previous, stage in zip(four.stages, four.stages[1:]):
            self.assertEqual(stage.inputs[2], previous.carry_output)
        with self.assertRaises(ValueError):
            evaluate_four_bit(one, "0000", "0000")


if __name__ == "__main__":
    unittest.main()
