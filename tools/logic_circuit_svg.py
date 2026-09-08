"""Deterministic placement and SVG drawings of two-input SOP circuits."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from html import escape
import math
import re
from typing import Mapping
import xml.etree.ElementTree as ET

import schemdraw
from schemdraw import elements as elm, logic

from .logic_circuit import Circuit, Node


Point = tuple[float, float]
Box = tuple[float, float, float, float]
SIGNAL_COLORS = {0: "#dc2626", 1: "#15803d"}
GATE_COLOR = "#17212b"
_GATE_WIDTH = {"AND": 1.85, "OR": 1.9, "XOR": 1.9, "NOT": 0.89}
_COLUMN = 3.5
_LEAF_GAP = 1.15


@dataclass(frozen=True)
class NodeLayout:
    id: str
    output: Point
    inputs: tuple[Point, ...] = ()
    box: Box | None = None


@dataclass(frozen=True)
class Wire:
    source: str
    target: str | None
    input_index: int | None
    points: tuple[Point, ...]


@dataclass(frozen=True)
class TermLabel:
    number: int
    source: str
    position: Point


@dataclass(frozen=True)
class CircuitLayout:
    circuit: Circuit
    nodes: tuple[NodeLayout, ...]
    wires: tuple[Wire, ...]
    junctions: tuple[tuple[str, Point], ...]
    terms: tuple[TermLabel, ...]
    output: Point


@dataclass(frozen=True)
class SceneLabel:
    text: str
    position: Point
    source: str | None = None
    align: str = "center"


@dataclass(frozen=True)
class SceneGroup:
    box: Box


@dataclass(frozen=True)
class CircuitScene:
    """Positioned signals and labels, independent of the number of outputs."""

    signals: tuple[Node, ...]
    nodes: tuple[NodeLayout, ...]
    wires: tuple[Wire, ...]
    junctions: tuple[tuple[str, Point], ...]
    labels: tuple[SceneLabel, ...]
    margin: float = 0.8
    groups: tuple[SceneGroup, ...] = ()


def _gate(node_id: str, kind: str, x: float, y: float) -> NodeLayout:
    width = _GATE_WIDTH[kind]
    offsets = (0.0,) if kind == "NOT" else (0.25, -0.25)
    return NodeLayout(node_id, (x, y), tuple((x - width, y + dy) for dy in offsets),
                      (x - width, y - 0.5, x, y + 0.5))


def _points(*points: Point) -> tuple[Point, ...]:
    result: list[Point] = []
    for point in points:
        if not result or point != result[-1]:
            result.append(point)
    return tuple(result)


def build_layout(circuit: Circuit) -> CircuitLayout:
    """Place shared input/NOT rails, separate term bands, and an OR tree.

    Logical edges retain their complete endpoint paths. Shared rail segments
    are merged when drawing; dots mark only real branches of the same signal.
    Crossings of different signals have no connection dot.
    """
    by_id = {node.id: node for node in circuit.nodes}
    if len(by_id) != len(circuit.nodes) or circuit.output not in by_id:
        raise ValueError("Circuit signals must have unique, defined IDs.")
    if len(set(circuit.term_outputs)) != len(circuit.term_outputs):
        raise ValueError("Draw the canonical SOP cover without duplicate term roots.")
    placed: dict[str, NodeLayout] = {}
    rails: dict[str, float] = {}
    taps: dict[str, set[Point]] = defaultdict(set)
    wires: list[Wire] = []
    inputs = [node for node in circuit.nodes if node.kind == "INPUT"]
    inversions = [node for node in circuit.nodes if node.kind == "NOT"]
    for index, node in enumerate(inputs):
        placed[node.id] = NodeLayout(node.id, (float(index), 0.0))
        rails[node.id] = float(index)
    inverter_x = float(len(inputs) + 1)
    for index, node in enumerate(inversions):
        if len(node.inputs) != 1 or by_id[node.inputs[0]].kind != "INPUT":
            raise ValueError("SOP inverters must have one original input.")
        placed[node.id] = _gate(node.id, "NOT", inverter_x, -2.0 - index * 1.6)
        rails[node.id] = inverter_x + 1.0 + index
    rail_right = max(rails.values(), default=0.0)
    and_left = rail_right + 1.4
    term_top = min((p.output[1] for p in placed.values()), default=0.0) - 2.0
    for node in circuit.nodes:
        if node.kind == "CONST":
            placed[node.id] = NodeLayout(node.id, (and_left, term_top))

    def source_path(node_id: str, y: float) -> tuple[Point, ...]:
        origin = placed[node_id].output
        if node_id in rails:
            rail_x = rails[node_id]
            tap = (rail_x, y)
            taps[node_id].add(tap)
            return _points(origin, (rail_x, origin[1]), tap)
        return _points(origin, (origin[0], y))

    def connect(source: str, target: str, index: int, prefix: tuple[Point, ...]) -> None:
        endpoint = placed[target].inputs[index]
        elbow_x = endpoint[0] - 0.45
        path = _points(*prefix, (elbow_x, prefix[-1][1]), (elbow_x, endpoint[1]), endpoint)
        wires.append(Wire(source, target, index, path))

    for node in inversions:
        connect(node.inputs[0], node.id, 0, source_path(node.inputs[0], placed[node.id].output[1]))

    term_positions: dict[str, Point] = {}
    term_depths: list[int] = []
    for root in circuit.term_outputs:
        leaf_index = 0

        def place_term(node_id: str) -> tuple[float, int]:
            nonlocal leaf_index
            node = by_id[node_id]
            if node.kind != "AND":
                if node.kind not in ("INPUT", "NOT", "CONST"):
                    raise ValueError("A SOP term may contain only literals and two-input AND gates.")
                y = term_top - leaf_index * _LEAF_GAP
                leaf_index += 1
                return y, 0
            if len(node.inputs) != 2 or node_id in placed:
                raise ValueError("Each term must have its own two-input AND tree.")
            children = [place_term(child) for child in node.inputs]
            depth = max(level for _, level in children) + 1
            y = sum(child_y for child_y, _ in children) / 2
            placed[node_id] = _gate(node_id, "AND", and_left + depth * _COLUMN, y)
            for index, (child, (child_y, _)) in enumerate(zip(node.inputs, children)):
                prefix = source_path(child, child_y) if by_id[child].kind != "AND" else (placed[child].output,)
                connect(child, node_id, index, prefix)
            return y, depth

        root_y, depth = place_term(root)
        term_positions[root] = (0.0, root_y)
        term_depths.append(depth)
        term_top -= max(leaf_index - 1, 0) * _LEAF_GAP + 1.8

    term_x = and_left + max(term_depths, default=0) * _COLUMN + 1.5
    term_positions = {node_id: (term_x, point[1]) for node_id, point in term_positions.items()}

    def term_path(node_id: str) -> tuple[Point, ...]:
        point = term_positions[node_id]
        prefix = source_path(node_id, point[1]) if by_id[node_id].kind in ("INPUT", "NOT", "CONST") else (placed[node_id].output,)
        return _points(*prefix, point)

    def place_or(node_id: str) -> tuple[Point, int]:
        if node_id in term_positions:
            return term_positions[node_id], 0
        node = by_id[node_id]
        if node.kind != "OR" or len(node.inputs) != 2:
            raise ValueError("The SOP output must be a tree of two-input OR gates.")
        children = [place_or(child) for child in node.inputs]
        depth = max(level for _, level in children) + 1
        y = sum(point[1] for point, _ in children) / 2
        placed[node_id] = _gate(node_id, "OR", term_x + depth * _COLUMN, y)
        for index, child in enumerate(node.inputs):
            prefix = term_path(child) if child in term_positions else (placed[child].output,)
            connect(child, node_id, index, prefix)
        return placed[node_id].output, depth

    if circuit.term_outputs:
        root_point, _ = place_or(circuit.output)
        output_prefix = term_path(circuit.output) if circuit.output in term_positions else (root_point,)
    else:
        if by_id[circuit.output].kind != "CONST":
            raise ValueError("An empty SOP cover must have a constant output.")
        root_point = placed[circuit.output].output
        output_prefix = (root_point,)
    output = (max(root_point[0], term_x) + 2.0, root_point[1])
    wires.append(Wire(circuit.output, None, None, _points(*output_prefix, output)))
    if set(placed) != set(by_id):
        raise ValueError("The circuit contains gates outside its SOP trees.")

    junctions = []
    for node_id, points in taps.items():
        if len(points) > 1:
            bottom = min(point[1] for point in points)
            junctions.extend((node_id, point) for point in sorted(points) if point[1] > bottom)
    terms = tuple(TermLabel(index + 1, root, term_positions[root]) for index, root in enumerate(circuit.term_outputs))
    return CircuitLayout(circuit, tuple(placed[node.id] for node in circuit.nodes), tuple(wires),
                         tuple(junctions), terms, output)


def _wire_segments(layout: CircuitLayout | CircuitScene) -> tuple[tuple[str, Point, Point], ...]:
    """Merge overlapping collinear segments only when they carry one signal."""
    grouped: dict[tuple[str, str, float], list[tuple[float, float]]] = defaultdict(list)
    for wire in layout.wires:
        for start, end in zip(wire.points, wire.points[1:]):
            if start[1] == end[1]:
                grouped[(wire.source, "H", start[1])].append(tuple(sorted((start[0], end[0]))))
            elif start[0] == end[0]:
                grouped[(wire.source, "V", start[0])].append(tuple(sorted((start[1], end[1]))))
            else:
                raise ValueError("Circuit wires must be orthogonal.")
    segments = []
    for (source, axis, fixed), intervals in sorted(grouped.items()):
        merged: list[list[float]] = []
        for low, high in sorted(intervals):
            if merged and low <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], high)
            else:
                merged.append([low, high])
        for low, high in merged:
            if axis == "H":
                segments.append((source, (low, fixed), (high, fixed)))
            else:
                segments.append((source, (fixed, low), (fixed, high)))
    return tuple(segments)


def _validate_values(nodes: tuple[Node, ...], values: Mapping[str, int]) -> None:
    if set(values) != {node.id for node in nodes} or any(
        type(value) not in (int, bool) or value not in (0, 1) for value in values.values()
    ):
        raise ValueError("Provide a 0/1 value for every circuit signal.")


def render_scene_svg(scene: CircuitScene, values: Mapping[str, int], *,
                     title: str, description: str) -> bytes:
    """Use the same symbols, anchors and signal palette for every circuit scene."""
    _validate_values(scene.signals, values)
    positions = {node.id: node for node in scene.nodes}
    if len(positions) != len(scene.nodes) or set(positions) != set(values):
        raise ValueError("Provide exactly one position for every circuit signal.")
    # SVG text bounds are approximate; leave room for the left-aligned F label
    # and the labels over the first input rail in standalone image viewers.
    drawing = schemdraw.Drawing(canvas="svg", show=False, bgcolor="white", color=GATE_COLOR,
                                inches_per_unit=0.4, fontsize=11, lw=1.5, margin=scene.margin)

    def label(text: str, point: Point, *, align: str = "center") -> None:
        drawing.add(elm.Label().right().at(point).label(text, loc="center", ofst=0,
                                              halign=align, fontsize=11, color=GATE_COLOR))

    for group in scene.groups:
        left, bottom, right, top = group.box
        drawing.add(elm.Rect((left, bottom), (right, top), lw=0.8, ls="--")
                    .right().at((0, 0)).color("#cbd5e1"))
    for source, start, end in _wire_segments(scene):
        drawing.add(elm.Line().at(start).to(end).color(SIGNAL_COLORS[values[source]]))
    for source, point in scene.junctions:
        drawing.add(elm.Dot(radius=0.055).at(point).color(SIGNAL_COLORS[values[source]]))
    for node in scene.signals:
        position = positions[node.id]
        x, y = position.output
        if node.kind in ("INPUT", "CONST"):
            drawing.add(elm.Dot(open=True, radius=0.07).at(position.output).color(GATE_COLOR))
            continue
        if node.kind == "AND":
            gate = logic.And(inputs=2)
        elif node.kind == "OR":
            gate = logic.Or(inputs=2)
        elif node.kind == "XOR":
            gate = logic.Xor(inputs=2)
        else:
            gate = logic.Not(extend=False)
        gate = drawing.add(gate.right().anchor("out").at(position.output).color(GATE_COLOR).fill("white"))
        # The layout's endpoint contract is tied to the pinned symbol geometry.
        for anchor, expected in [("out", position.output)] + [
            (f"in{index + 1}", point) for index, point in enumerate(position.inputs)
        ]:
            if any(not math.isclose(actual, target, abs_tol=1e-9)
                   for actual, target in zip(gate.absanchors[anchor], expected)):
                raise ValueError("Logic gate geometry no longer matches the circuit layout.")
        label(str(values[node.id]), (x - 0.35, y + 0.75))
    for item in scene.labels:
        text = item.text if item.source is None else f"{item.text}={values[item.source]}"
        label(text, item.position, align=item.align)

    svg = drawing.get_imagedata("svg")
    root = ET.fromstring(svg)
    x, y, width, height = root.attrib["viewBox"].split()
    # A real background rectangle remains white in standalone SVG viewers too.
    additions = (f'<title>{escape(title)}</title>'
                 f'<desc>{escape(description)}</desc>'
                 f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="white"/>').encode()
    end = svg.index(b">", svg.index(b"<svg")) + 1
    return svg[:end] + additions + svg[end:]


def render_circuit_svg(circuit: Circuit, layout: CircuitLayout, values: Mapping[str, int], *,
                       input_labels: Mapping[str, str] | None = None,
                       output_label: str = "F") -> bytes:
    """Draw one SOP circuit; optional aliases change labels, never its logic."""
    if layout.circuit != circuit:
        raise ValueError("Circuit layout belongs to a different netlist.")
    _validate_values(circuit.nodes, values)
    aliases = input_labels or {}
    positions = {node.id: node for node in layout.nodes}
    labels = []
    input_index = 0
    for node in circuit.nodes:
        if node.kind in ("INPUT", "CONST"):
            x, y = positions[node.id].output
            text = aliases.get(node.variable, node.variable) if node.kind == "INPUT" else str(node.constant)
            offset = 1.1 if input_labels and input_index % 2 else 0.5
            labels.append(SceneLabel(text, (x, y + offset), node.id if node.kind == "INPUT" else None))
            if node.kind == "INPUT":
                input_index += 1
    labels.extend(SceneLabel(f"T{term.number}", (term.position[0], term.position[1] + 0.4), term.source)
                  for term in layout.terms)
    labels.append(SceneLabel(output_label, (layout.output[0] + 0.2, layout.output[1]), circuit.output, "left"))
    scene = CircuitScene(circuit.nodes, layout.nodes, layout.wires, layout.junctions, tuple(labels),
                         1.2 if input_labels or output_label != "F" else 0.8)
    summary = ", ".join(f"{aliases.get(node.variable, node.variable)}={values[node.id]}"
                        for node in circuit.nodes if node.kind == "INPUT")
    output = f"{output_label}={values[circuit.output]}"
    return render_scene_svg(scene, values, title=f"Logic circuit: {output}",
                            description=f"AND2/OR2 circuit with unary NOT. {summary}. {output}. "
                                        "Dots connect wires; other crossings do not.")


def svg_size_px(svg: bytes) -> tuple[float, float]:
    """Return intrinsic CSS-pixel dimensions, including Schemdraw's pt units."""
    root = ET.fromstring(svg)
    viewbox = list(map(float, root.attrib["viewBox"].split()))
    factors = {"": 1.0, "px": 1.0, "pt": 96 / 72, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4}

    def dimension(name: str, fallback: float) -> float:
        raw = root.attrib.get(name)
        if raw is None:
            result = fallback
        else:
            match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(px|pt|in|cm|mm)?", raw)
            if not match:
                raise ValueError("SVG dimensions must use explicit supported units.")
            result = float(match[1]) * factors[match[2] or ""]
        if not math.isfinite(result) or result <= 0:
            raise ValueError("SVG dimensions must be positive and finite.")
        return result

    return dimension("width", viewbox[2]), dimension("height", viewbox[3])
