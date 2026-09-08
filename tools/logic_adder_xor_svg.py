"""Compact, explicit gate drawings of the XOR-based full-adder network."""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from typing import Mapping

from .logic_adder import XorAdderDefinition
from .logic_adder_svg import _junctions
from .logic_circuit_svg import (
    CircuitScene, NodeLayout, SceneGroup, SceneLabel, Wire, _gate, _points,
    _validate_values, render_scene_svg,
)


@lru_cache(maxsize=2)
def build_xor_adder_scene(adder: XorAdderDefinition) -> CircuitScene:
    """Show all five gates per stage and connect the real carry gate outputs.

    The first XOR produces P=A XOR B. Its shared rail feeds the second XOR
    and the carry AND. Each stage retains both AND gates even when C0=0.
    """
    if len(adder.stages) not in (1, 4):
        raise ValueError("The lesson supports one or four full-adder stages.")
    four_bits = len(adder.stages) == 4
    positions: dict[str, NodeLayout] = {}
    wires: list[Wire] = []
    labels: list[SceneLabel] = []
    groups: list[SceneGroup] = []
    by_id = {node.id: node for node in adder.network.nodes}
    carry_rail = 17.5

    for stage in adder.stages:
        top = -11.0 * stage.index
        a, b, cin = stage.inputs
        p = f"fa{stage.index}.xor_ab"
        and_ab = f"fa{stage.index}.and_ab"
        and_carry = f"fa{stage.index}.and_carry"
        groups.append(SceneGroup((-0.75, top - 6.0, 17.0, top + 3.6)))
        header = (f"Bit {stage.index} ({'LSB' if stage.index == 0 else 'MSB'})"
                  if stage.index in (0, 3) else f"Bit {stage.index}") if four_bits else "1-bit full adder"
        labels.append(SceneLabel(header, (0.0, top + 2.9), align="left"))
        for source, x in ((a, 0.0), (b, 1.0)):
            positions[source] = NodeLayout(source, (x, top + 1.0))
        if stage.index == 0:
            positions[cin] = NodeLayout(cin, (7.0, top + 1.0))

        for node_id, x, y in ((p, 5.0, 0.0), (stage.sum_output, 10.0, 0.0),
                              (and_ab, 5.0, -3.0), (and_carry, 10.0, -5.0),
                              (stage.carry_output, 14.0, -4.0)):
            positions[node_id] = _gate(node_id, by_id[node_id].kind, x, top + y)

        def connect(source: str, target: str, index: int, *bends: tuple[float, float]) -> None:
            wires.append(Wire(source, target, index,
                              _points(positions[source].output, *bends, positions[target].inputs[index])))

        for target in (p, and_ab):
            for index, (source, x) in enumerate(((a, 0.0), (b, 1.0))):
                endpoint = positions[target].inputs[index]
                connect(source, target, index, (x, endpoint[1]))
        for target in (stage.sum_output, and_carry):
            endpoint = positions[target].inputs[0]
            connect(p, target, 0, (6.0, top), (6.0, endpoint[1]))
            endpoint = positions[target].inputs[1]
            if stage.index == 0:
                connect(cin, target, 1, (7.0, endpoint[1]))
            else:
                origin = positions[cin].output
                connect(cin, target, 1, (carry_rail, origin[1]),
                        (carry_rail, top + 2.4), (7.0, top + 2.4), (7.0, endpoint[1]))
        endpoint = positions[stage.carry_output].inputs[0]
        connect(and_ab, stage.carry_output, 0, (11.0, top - 3.0), (11.0, endpoint[1]))
        endpoint = positions[stage.carry_output].inputs[1]
        connect(and_carry, stage.carry_output, 1, (11.5, top - 5.0), (11.5, endpoint[1]))

        sum_endpoint = (15.0, top)
        wires.append(Wire(stage.sum_output, None, None,
                          _points(positions[stage.sum_output].output, sum_endpoint)))
        if stage.index == len(adder.stages) - 1:
            wires.append(Wire(stage.carry_output, None, None,
                              _points(positions[stage.carry_output].output, (15.0, top - 4.0))))

        names = (f"A{stage.index}", f"B{stage.index}", f"C{stage.index}") if four_bits else ("A", "B", "Cin")
        labels.extend((SceneLabel(names[0], (0.0, top + 1.6), a),
                       SceneLabel(names[1], (1.0, top + 2.2), b),
                       SceneLabel(names[2], (7.3, top + 1.1), cin, "left"),
                       SceneLabel(f"P{stage.index}" if four_bits else "P", (4.8, top - 1.6), p),
                       SceneLabel(f"S{stage.index}" if four_bits else "S",
                                  (sum_endpoint[0] + 0.2, top), stage.sum_output, "left")))
        internal = stage.index < len(adder.stages) - 1
        labels.append(SceneLabel(f"C{stage.index + 1}" if four_bits else "Cout",
                                 (15.2, top - 3.3 if internal else top - 4.0),
                                 stage.carry_output, "left"))

    if set(positions) != set(by_id):
        raise ValueError("The XOR adder scene must position every real network signal exactly once.")
    scene = CircuitScene(adder.network.nodes, tuple(positions[node.id] for node in adder.network.nodes),
                         tuple(wires), (), tuple(labels), margin=1.2, groups=tuple(groups))
    return replace(scene, junctions=_junctions(scene))


def render_xor_adder_svg(adder: XorAdderDefinition, scene: CircuitScene,
                         values: Mapping[str, int]) -> bytes:
    """Export all XOR/AND/OR gates and their current input/output signal state."""
    if scene.signals != adder.network.nodes:
        raise ValueError("The XOR adder scene belongs to a different network.")
    _validate_values(scene.signals, values)
    outputs = ", ".join(f"{output.name}={values[output.source]}" for output in adder.network.outputs)
    inputs = ", ".join(f"{node.variable}={values[node.id]}"
                       for node in adder.network.nodes if node.kind == "INPUT")
    carries = ("Internal carry: " + ", ".join(f"C{stage.index}={values[stage.inputs[2]]}" for stage in adder.stages)
               if len(adder.stages) == 4 else f"Carry input: Cin={values[adder.stages[0].inputs[2]]}")
    title = f"{'4-bit ripple-carry adder' if len(adder.stages) == 4 else '1-bit full adder'} with XOR: {outputs}"
    return render_scene_svg(scene, values, title=title,
                            description=f"XOR2/AND2/OR2 circuit. P = A XOR B. {inputs}. {outputs}. "
                                        f"{carries}. 0 is red; 1 is green. "
                                        "Dots connect wires; other crossings do not.")
