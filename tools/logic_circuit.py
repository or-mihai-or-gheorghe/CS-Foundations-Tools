"""Build and evaluate two-input gate circuits from structured SOP cubes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, Mapping

if TYPE_CHECKING:
    from .logic_minimization import Cube


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    inputs: tuple[str, ...] = ()
    variable: str | None = None
    constant: int | None = None


@dataclass(frozen=True)
class Circuit:
    var_order: tuple[str, ...]
    nodes: tuple[Node, ...]
    output: str
    term_outputs: tuple[str, ...]


@dataclass(frozen=True)
class SignalOutput:
    name: str
    source: str


@dataclass(frozen=True)
class LogicNetwork:
    """A gate network with named outputs, including internal carry connections."""

    var_order: tuple[str, ...]
    nodes: tuple[Node, ...]
    outputs: tuple[SignalOutput, ...]


def build_circuit(cubes: Iterable[Cube], var_order: Iterable[str]) -> Circuit:
    """Compile ordered cubes without parsing SOP text or changing their order.

    Each cube's literals follow var_order, including variables eliminated from
    the SOP. AND trees are separate per term; NOT sources are shared. Term
    roots retain the minimizer's order so circuit labels match its SOP/groups.
    """
    variables = tuple(var_order)
    if not 1 <= len(variables) <= 5 or len(set(variables)) != len(variables):
        raise ValueError("Variable order must contain 1 to 5 distinct variables.")
    if any(variable not in ("A", "B", "C", "D", "E") for variable in variables):
        raise ValueError("Circuit variables must be uppercase A to E.")

    selected = tuple(cubes)
    literals_by_term = []
    for cube in selected:
        literals = tuple(cube.literals)
        if cube.nvars != len(variables) or len(literals) != len(variables):
            raise ValueError("Every cube must use the circuit's variable count.")
        if any(value is not None and (type(value) is not int or value not in (0, 1))
               for value in literals):
            raise ValueError("Cube literals must be 0, 1, or None.")
        literals_by_term.append(literals)

    nodes = [Node(f"input_{variable}", "INPUT", variable=variable) for variable in variables]
    negated = {}
    for index, variable in enumerate(variables):
        if any(literals[index] == 0 for literals in literals_by_term):
            node_id = f"not_{variable}"
            nodes.append(Node(node_id, "NOT", (f"input_{variable}",)))
            negated[variable] = node_id

    def balanced_tree(signals: tuple[str, ...], kind: str, prefix: str) -> str:
        next_index = 0

        def combine(inputs: tuple[str, ...]) -> str:
            nonlocal next_index
            if len(inputs) == 1:
                return inputs[0]
            midpoint = len(inputs) // 2
            left = combine(inputs[:midpoint])
            right = combine(inputs[midpoint:])
            node_id = f"{prefix}_{next_index}"
            next_index += 1
            nodes.append(Node(node_id, kind, (left, right)))
            return node_id

        return combine(signals)

    term_outputs = []
    constant_one_added = False
    for term_index, literals in enumerate(literals_by_term):
        signals = tuple(
            negated[variable] if value == 0 else f"input_{variable}"
            for variable, value in zip(variables, literals)
            if value is not None
        )
        if not signals:
            if not constant_one_added:
                nodes.append(Node("const_1", "CONST", constant=1))
                constant_one_added = True
            term_outputs.append("const_1")
        else:
            term_outputs.append(balanced_tree(signals, "AND", f"and_t{term_index}"))

    if not term_outputs:
        nodes.append(Node("const_0", "CONST", constant=0))
        output = "const_0"
    else:
        output = balanced_tree(tuple(term_outputs), "OR", "or")

    return Circuit(variables, tuple(nodes), output, tuple(term_outputs))


def evaluate_circuit(circuit: Circuit, assignment: Mapping[str, int | bool]) -> dict[str, int]:
    """Return each signal's 0/1 value for one assignment of the full domain."""
    values = _evaluate_nodes(circuit.nodes, circuit.var_order, assignment)
    if circuit.output not in values:
        raise ValueError("Circuit output is not a defined signal.")
    return values


def evaluate_network(network: LogicNetwork, assignment: Mapping[str, int | bool]) -> dict[str, int]:
    """Evaluate the actual gates once and validate every named output."""
    if (not network.var_order or len(set(network.var_order)) != len(network.var_order)
            or any(not isinstance(name, str) or not name for name in network.var_order)):
        raise ValueError("Network inputs must have distinct, nonempty names.")
    inputs = tuple(node.variable for node in network.nodes if node.kind == "INPUT")
    if len(inputs) != len(network.var_order) or set(inputs) != set(network.var_order):
        raise ValueError("Define exactly one input node for each network variable.")
    names = tuple(output.name for output in network.outputs)
    if not names or len(set(names)) != len(names) or any(not name for name in names):
        raise ValueError("Network outputs must have distinct, nonempty names.")
    values = _evaluate_nodes(network.nodes, network.var_order, assignment)
    if any(output.source not in values for output in network.outputs):
        raise ValueError("Every network output must reference a defined signal.")
    return values


def _evaluate_nodes(nodes: tuple[Node, ...], var_order: tuple[str, ...],
                    assignment: Mapping[str, int | bool]) -> dict[str, int]:
    if set(assignment) != set(var_order):
        raise ValueError("Provide exactly one 0/1 value for every circuit variable.")
    if any(type(value) not in (int, bool) or value not in (0, 1) for value in assignment.values()):
        raise ValueError("Circuit inputs must be 0 or 1.")

    arities = {"INPUT": 0, "CONST": 0, "NOT": 1, "AND": 2, "OR": 2}
    values: dict[str, int] = {}
    for node in nodes:
        if node.id in values:
            raise ValueError(f"Duplicate circuit signal: {node.id}.")
        if node.kind not in arities or len(node.inputs) != arities[node.kind]:
            raise ValueError(f"Invalid gate kind or input count for {node.id}.")
        if any(source not in values for source in node.inputs):
            raise ValueError(f"Circuit is not in topological order at {node.id}.")
        if node.kind == "INPUT":
            if node.variable not in assignment:
                raise ValueError(f"Unknown input variable for {node.id}.")
            value = int(assignment[node.variable])
        elif node.kind == "CONST":
            if type(node.constant) is not int or node.constant not in (0, 1):
                raise ValueError(f"Invalid constant for {node.id}.")
            value = node.constant
        elif node.kind == "NOT":
            value = 1 - values[node.inputs[0]]
        elif node.kind == "AND":
            value = values[node.inputs[0]] & values[node.inputs[1]]
        else:
            value = values[node.inputs[0]] | values[node.inputs[1]]
        values[node.id] = value

    return values


def gate_counts(circuit: Circuit | LogicNetwork) -> dict[str, int]:
    """Count real logic gates, excluding input/constant sources and wires."""
    counts = {kind: sum(node.kind == kind for node in circuit.nodes) for kind in ("AND", "OR", "NOT")}
    counts["total"] = sum(counts.values())
    return counts
