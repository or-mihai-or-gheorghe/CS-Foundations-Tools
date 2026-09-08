"""Fixed full-adder lesson circuits using minimized SOPs or shared XOR gates."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Mapping

from .logic_circuit import (
    Circuit, LogicNetwork, Node, SignalOutput, build_circuit, evaluate_network,
)
from .logic_minimization import MinimizationResult, minimize_sop


# The arithmetic specification is independent of the compiled gate network.
FULL_ADDER_TABLE = tuple(
    (a, b, cin, (a + b + cin) % 2, (a + b + cin) // 2)
    for a in (0, 1) for b in (0, 1) for cin in (0, 1)
)


@dataclass(frozen=True)
class AdderStage:
    index: int
    inputs: tuple[str, str, str]
    sum_output: str
    carry_output: str
    sum_nodes: tuple[tuple[str, str], ...]
    carry_nodes: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class AdderDefinition:
    network: LogicNetwork
    stages: tuple[AdderStage, ...]
    sum_result: MinimizationResult
    carry_result: MinimizationResult
    sum_circuit: Circuit
    carry_circuit: Circuit


@dataclass(frozen=True)
class XorAdderDefinition:
    network: LogicNetwork
    stages: tuple[AdderStage, ...]


@dataclass(frozen=True)
class AdderEvaluation:
    values: Mapping[str, int]
    sum_bits: str
    carry_out: int
    full_bits: str
    stages: tuple[tuple[int, int, int, int, int, int], ...]


@lru_cache(maxsize=1)
def build_full_adder() -> AdderDefinition:
    return _build_adder(four_bits=False)


@lru_cache(maxsize=1)
def build_four_bit_adder() -> AdderDefinition:
    return _build_adder(four_bits=True)


@lru_cache(maxsize=1)
def build_xor_full_adder() -> XorAdderDefinition:
    return _build_xor_adder(four_bits=False)


@lru_cache(maxsize=1)
def build_xor_four_bit_adder() -> XorAdderDefinition:
    return _build_xor_adder(four_bits=True)


def _build_xor_adder(*, four_bits: bool) -> XorAdderDefinition:
    var_order = (tuple(f"{operand}{i}" for operand in "AB" for i in reversed(range(4)))
                 if four_bits else ("A", "B", "Cin"))
    nodes = [Node(f"input_{name}", "INPUT", variable=name) for name in var_order]
    carry = "const_C0" if four_bits else "input_Cin"
    if four_bits:
        nodes.append(Node(carry, "CONST", constant=0))
    stages = []
    for i in range(4 if four_bits else 1):
        a, b = (f"input_A{i}", f"input_B{i}") if four_bits else ("input_A", "input_B")
        prefix = f"fa{i}."
        xor_ab, xor_sum = prefix + "xor_ab", prefix + "xor_sum"
        and_ab, and_carry, or_carry = (prefix + name for name in ("and_ab", "and_carry", "or_carry"))
        nodes.extend((
            Node(xor_ab, "XOR", (a, b)),
            Node(xor_sum, "XOR", (xor_ab, carry)),
            Node(and_ab, "AND", (a, b)),
            Node(and_carry, "AND", (xor_ab, carry)),
            Node(or_carry, "OR", (and_ab, and_carry)),
        ))
        stages.append(AdderStage(i, (a, b, carry), xor_sum, or_carry, (), ()))
        carry = or_carry
    outputs = (tuple(SignalOutput(f"S{stage.index}", stage.sum_output) for stage in reversed(stages))
               + (SignalOutput("C4", carry),) if four_bits else
               (SignalOutput("S", stages[0].sum_output), SignalOutput("Cout", carry)))
    return XorAdderDefinition(LogicNetwork(var_order, tuple(nodes), outputs), tuple(stages))


def _build_adder(*, four_bits: bool) -> AdderDefinition:
    sum_result = minimize_sop(3, {m for m, row in enumerate(FULL_ADDER_TABLE) if row[3]})
    carry_result = minimize_sop(3, {m for m, row in enumerate(FULL_ADDER_TABLE) if row[4]})
    sum_circuit = build_circuit(sum_result.cover, tuple("ABC"))
    carry_circuit = build_circuit(carry_result.cover, tuple("ABC"))
    var_order = (tuple(f"{operand}{i}" for operand in "AB" for i in reversed(range(4)))
                 if four_bits else ("A", "B", "Cin"))
    nodes = [Node(f"input_{name}", "INPUT", variable=name) for name in var_order]
    carry = "const_C0" if four_bits else "input_Cin"
    if four_bits:
        nodes.append(Node(carry, "CONST", constant=0))
    stages = []
    for i in range(4 if four_bits else 1):
        a, b = (f"input_A{i}", f"input_B{i}") if four_bits else ("input_A", "input_B")
        inputs = (a, b, carry)

        def clone(circuit: Circuit, branch: str) -> dict[str, str]:
            mapping = dict(zip(("input_A", "input_B", "input_C"), inputs))
            for node in circuit.nodes:
                if node.kind == "INPUT":
                    continue
                node_id = f"fa{i}.{branch}.{node.id}"
                mapped_inputs = tuple(mapping[source] for source in node.inputs)
                mapping[node.id] = node_id
                nodes.append(Node(node_id, node.kind, mapped_inputs,
                                  variable=node.variable, constant=node.constant))
            return mapping

        sum_nodes = clone(sum_circuit, "sum")
        carry_nodes = clone(carry_circuit, "carry")
        stage = AdderStage(i, inputs, sum_nodes[sum_circuit.output],
                           carry_nodes[carry_circuit.output], tuple(sum_nodes.items()),
                           tuple(carry_nodes.items()))
        stages.append(stage)
        carry = stage.carry_output
    outputs = (tuple(SignalOutput(f"S{stage.index}", stage.sum_output) for stage in reversed(stages))
               + (SignalOutput("C4", carry),) if four_bits else
               (SignalOutput("S", stages[0].sum_output), SignalOutput("Cout", carry)))
    network = LogicNetwork(var_order, tuple(nodes), outputs)
    return AdderDefinition(network, tuple(stages), sum_result, carry_result,
                           sum_circuit, carry_circuit)


def parse_operand(text: str) -> str:
    """Keep leading zeros; accept only four binary digits after outer whitespace."""
    if not isinstance(text, str) or re.fullmatch(r"[01]{4}", text.strip()) is None:
        raise ValueError("Enter exactly four binary digits (0 or 1), for example 0101.")
    return text.strip()


def operand_assignment(a: str, b: str) -> dict[str, int]:
    return {f"{name}{i}": int(bit)
            for name, text in (("A", parse_operand(a)), ("B", parse_operand(b)))
            for i, bit in enumerate(reversed(text))}


def evaluate_four_bit(adder: AdderDefinition | XorAdderDefinition, a: str, b: str) -> AdderEvaluation:
    if len(adder.stages) != 4:
        raise ValueError("Use the four-bit adder for two four-bit operands.")
    values = evaluate_network(adder.network, operand_assignment(a, b))
    sum_bits = "".join(str(values[stage.sum_output]) for stage in reversed(adder.stages))
    carry_out = values[adder.stages[-1].carry_output]
    stages = tuple((stage.index, *(values[source] for source in stage.inputs),
                    values[stage.sum_output], values[stage.carry_output])
                   for stage in adder.stages)
    return AdderEvaluation(values, sum_bits, carry_out, f"{carry_out}{sum_bits}", stages)
