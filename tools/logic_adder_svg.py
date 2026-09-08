"""Compose the existing SOP geometry into one- and four-bit adder scenes."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from functools import lru_cache
from typing import Mapping

from .logic_adder import AdderDefinition
from .logic_circuit_svg import (
    CircuitLayout, CircuitScene, NodeLayout, Point, SceneGroup, SceneLabel, Wire,
    _points, _validate_values, _wire_segments, build_layout, render_scene_svg,
)


def _translate(point: Point, dx: float, dy: float) -> Point:
    return point[0] + dx, point[1] + dy


def _bottom(layout: CircuitLayout) -> float:
    """Include rail taps, which can extend below the last gate's box."""
    return min(*(point[1] for wire in layout.wires for point in wire.points),
               *(node.box[1] for node in layout.nodes if node.box))


def _junctions(scene: CircuitScene) -> tuple[tuple[str, Point], ...]:
    """Recompute branches after shared rails and carry trunks are merged.

    A former last tap becomes a junction when a rail continues into another
    SOP. Concatenating the original layouts' junction lists would miss it.
    """
    grouped: dict[str, list[tuple[Point, Point]]] = defaultdict(list)
    for source, start, end in _wire_segments(scene):
        grouped[source].append((start, end))
    result = []
    for source, segments in sorted(grouped.items()):
        candidates = {point for segment in segments for point in segment}
        for start, end in segments:
            if start[1] != end[1]:
                continue
            for first, last in segments:
                if (first[0] == last[0] and start[0] <= first[0] <= end[0]
                        and first[1] <= start[1] <= last[1]):
                    candidates.add((first[0], start[1]))
        for x, y in sorted(candidates):
            directions = set()
            for start, end in segments:
                if start[1] == end[1] == y and start[0] <= x <= end[0]:
                    if start[0] < x:
                        directions.add("left")
                    if x < end[0]:
                        directions.add("right")
                if start[0] == end[0] == x and start[1] <= y <= end[1]:
                    if start[1] < y:
                        directions.add("down")
                    if y < end[1]:
                        directions.add("up")
            if len(directions) >= 3:
                result.append((source, (x, y)))
    return tuple(result)


@lru_cache(maxsize=2)
def build_adder_scene(adder: AdderDefinition) -> CircuitScene:
    """Stack complete SOP branches, then complete full-adder stages.

    Only the prefixes from shared inputs are rerouted. All AND/OR trees keep
    their already-tested SOP geometry. Carry signals use the preceding gate's
    real ID and position, never an extra input node or a simulated wire value.
    """
    if len(adder.stages) not in (1, 4):
        raise ValueError("The lesson supports one or four full-adder stages.")
    sum_layout = build_layout(adder.sum_circuit)
    carry_layout = build_layout(adder.carry_circuit)
    by_kind = {node.id: node.kind for node in adder.sum_circuit.nodes}
    carry_kinds = {node.id: node.kind for node in adder.carry_circuit.nodes}
    dx_carry = (min(node.output[0] for node in sum_layout.nodes if by_kind[node.id] == "AND")
                - min(node.output[0] for node in carry_layout.nodes if carry_kinds[node.id] == "AND"))
    dy_carry = _bottom(sum_layout) - 2.0
    stage_bottom = min(_bottom(sum_layout), _bottom(carry_layout) + dy_carry)
    stage_pitch = -stage_bottom + 5.0
    right_rail = max(sum_layout.output[0], carry_layout.output[0] + dx_carry) + 4.0
    four_bits = len(adder.stages) == 4
    positions: dict[str, NodeLayout] = {}
    wires: list[Wire] = []
    labels: list[SceneLabel] = []
    groups: list[SceneGroup] = []

    for stage in adder.stages:
        top = -stage.index * stage_pitch
        groups.append(SceneGroup((-0.75, top + stage_bottom - 0.8,
                                  right_rail - 1.5, top + 3.8)))
        header = (f"Bit {stage.index} ({'LSB' if stage.index == 0 else 'MSB'})"
                  if stage.index in (0, 3) else f"Bit {stage.index}") if four_bits else "1-bit full adder"
        labels.append(SceneLabel(header, (0.0, top + 3.0), align="left"))
        input_origins = {source: (float(index), top) for index, source in enumerate(stage.inputs)}
        for index, source in enumerate(stage.inputs):
            name = (f"{'ABC'[index]}{stage.index}" if four_bits else ("A", "B", "Cin")[index])
            x, y = input_origins[source]
            # Indexed names and Cin are wider than the original A/B/C labels.
            # Stagger their text while keeping the familiar input rail spacing.
            if stage.index > 0 and index == 2:
                # This rail arrives from above; its label must sit beside it.
                labels.append(SceneLabel(name, (x + 0.35, y + 0.5), source, "left"))
            else:
                labels.append(SceneLabel(name, (x, y + (1.1 if index == 1 else 0.5)), source))

        for branch, circuit, layout, mappings, dx, dy in (
            ("sum", adder.sum_circuit, sum_layout, stage.sum_nodes, 0.0, top),
            ("carry", adder.carry_circuit, carry_layout, stage.carry_nodes, dx_carry, top + dy_carry),
        ):
            mapping = dict(mappings)
            local_inputs = {node.id for node in circuit.nodes if node.kind == "INPUT"}
            for node in layout.nodes:
                if node.id in local_inputs and (branch == "carry" or
                        (stage.index > 0 and mapping[node.id] == stage.inputs[2])):
                    continue
                box = node.box
                global_id = mapping[node.id]
                positions[global_id] = NodeLayout(
                    global_id, _translate(node.output, dx, dy),
                    tuple(_translate(point, dx, dy) for point in node.inputs),
                    None if box is None else (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy),
                )

            for wire in layout.wires:
                if wire.target is None and branch == "carry" and stage.index < len(adder.stages) - 1:
                    continue  # Internal carry has a continuation, not an external port.
                source = mapping[wire.source]
                points = tuple(_translate(point, dx, dy) for point in wire.points)
                if wire.source in local_inputs:
                    origin = input_origins[source]
                    if branch == "carry":
                        # The original second point is the tap on this input's
                        # rail. Keep the existing route from that tap to its gate.
                        points = _points(origin, (origin[0], points[1][1]), *points[2:])
                    if stage.index > 0 and source == stage.inputs[2]:
                        carry_origin = positions[source].output
                        points = _points(carry_origin, (right_rail, carry_origin[1]),
                                         (right_rail, top + 1.5), (origin[0], top + 1.5), *points)
                wires.append(Wire(source, mapping[wire.target] if wire.target else None,
                                  wire.input_index, points))

            prefix = "S" if branch == "sum" else "Cout"
            first_term = layout.terms[0].position
            labels.append(SceneLabel("Sum" if branch == "sum" else "Carry",
                                     _translate(first_term, dx, dy + 2.0)))
            for term in layout.terms:
                labels.append(SceneLabel(f"{prefix}:T{term.number}",
                                         _translate(term.position, dx, dy + 0.4), mapping[term.source]))
            output = _translate(layout.output, dx, dy)
            name = (f"S{stage.index}" if branch == "sum" else f"C{stage.index + 1}") if four_bits else prefix
            # Intermediate carry labels sit above the continuing wire. External
            # outputs use the same endpoint and label placement as the K-map.
            internal = branch == "carry" and stage.index < len(adder.stages) - 1
            labels.append(SceneLabel(name, (output[0] + 0.2, output[1] + (0.6 if internal else 0.0)),
                                     mapping[circuit.output], "left"))

    expected = {node.id for node in adder.network.nodes}
    if set(positions) != expected:
        raise ValueError("The adder scene must position every real network signal exactly once.")
    scene = CircuitScene(adder.network.nodes, tuple(positions[node.id] for node in adder.network.nodes),
                         tuple(wires), (), tuple(labels), margin=1.2, groups=tuple(groups))
    return replace(scene, junctions=_junctions(scene))


def render_adder_svg(adder: AdderDefinition, scene: CircuitScene, values: Mapping[str, int]) -> bytes:
    """Export the complete state, including internal carry wires, as one SVG."""
    if scene.signals != adder.network.nodes:
        raise ValueError("The adder scene belongs to a different network.")
    _validate_values(scene.signals, values)
    outputs = ", ".join(f"{output.name}={values[output.source]}" for output in adder.network.outputs)
    inputs = ", ".join(f"{node.variable}={values[node.id]}"
                       for node in adder.network.nodes if node.kind == "INPUT")
    carries = ("Internal carry: " + ", ".join(f"C{stage.index}={values[stage.inputs[2]]}" for stage in adder.stages)
               if len(adder.stages) == 4 else f"Carry input: Cin={values[adder.stages[0].inputs[2]]}")
    title = f"{'4-bit ripple-carry adder' if len(adder.stages) == 4 else '1-bit full adder'}: {outputs}"
    return render_scene_svg(scene, values, title=title,
                            description=f"AND2/OR2 circuit with unary NOT. {inputs}. {outputs}. "
                                        f"{carries}. 0 is red; 1 is green. "
                                        "Dots connect wires; other crossings do not.")
