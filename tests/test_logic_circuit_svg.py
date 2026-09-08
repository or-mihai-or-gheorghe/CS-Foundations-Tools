"""Circuit geometry and standalone, state-specific SVG regression checks."""

from concurrent.futures import ThreadPoolExecutor
from itertools import combinations, product
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from schemdraw import logic

from tools.logic_circuit import build_circuit, evaluate_circuit, gate_counts
from tools.logic_circuit_svg import (
    GATE_COLOR,
    SIGNAL_COLORS,
    _wire_segments,
    build_layout,
    render_circuit_svg,
    svg_size_px,
)
from tools.logic_minimization import Cube, minimize_sop


EPSILON = 1e-8


def parity_circuit():
    return build_circuit(
        tuple(Cube(5, 31, index) for index in range(32) if index.bit_count() % 2),
        tuple("ABCDE"),
    )


class CircuitLayoutTests(unittest.TestCase):
    def assert_geometry(self, circuit):
        layout = build_layout(circuit)
        self.assertEqual(layout, build_layout(circuit))
        nodes = {node.id: node for node in circuit.nodes}
        positions = {node.id: node for node in layout.nodes}
        self.assertEqual(set(nodes), set(positions))
        self.assertEqual(tuple(term.source for term in layout.terms), circuit.term_outputs)
        self.assertEqual(tuple(term.number for term in layout.terms), tuple(range(1, len(layout.terms) + 1)))
        for node in circuit.nodes:
            self.assertEqual(len(positions[node.id].inputs), len(node.inputs))
            self.assertEqual(positions[node.id].box is not None, node.kind in ("AND", "OR", "NOT"))
        edges = set()
        for wire in layout.wires:
            self.assertEqual(wire.points[0], positions[wire.source].output)
            if wire.target is None:
                self.assertEqual(wire.source, circuit.output)
                self.assertEqual(wire.points[-1], layout.output)
            else:
                self.assertEqual(nodes[wire.target].inputs[wire.input_index], wire.source)
                self.assertEqual(wire.points[-1], positions[wire.target].inputs[wire.input_index])
                edges.add((wire.source, wire.target, wire.input_index))
            for start, end in zip(wire.points, wire.points[1:]):
                self.assertTrue(start[0] == end[0] or start[1] == end[1], wire)
        expected = {(source, node.id, index) for node in circuit.nodes for index, source in enumerate(node.inputs)}
        self.assertEqual(edges, expected)
        self.assertEqual(len(layout.wires), len(expected) + 1)

        boxes = [(node.id, node.box) for node in layout.nodes if node.box is not None]
        for (first_id, first), (second_id, second) in combinations(boxes, 2):
            overlaps = (max(first[0], second[0]) < min(first[2], second[2]) - EPSILON
                        and max(first[1], second[1]) < min(first[3], second[3]) - EPSILON)
            self.assertFalse(overlaps, (first_id, second_id))

        segments = _wire_segments(layout)
        for source, start, end in segments:
            for node_id, (left, bottom, right, top) in boxes:
                if start[1] == end[1]:
                    hits = (bottom + EPSILON < start[1] < top - EPSILON
                            and max(start[0], left) < min(end[0], right) - EPSILON)
                else:
                    hits = (left + EPSILON < start[0] < right - EPSILON
                            and max(start[1], bottom) < min(end[1], top) - EPSILON)
                self.assertFalse(hits, (source, start, end, node_id))
        for (source, start, end), (other, first, last) in combinations(segments, 2):
            if source == other:
                continue
            horizontal_overlap = (start[1] == end[1] == first[1] == last[1]
                                  and max(start[0], first[0]) < min(end[0], last[0]) - EPSILON)
            vertical_overlap = (start[0] == end[0] == first[0] == last[0]
                                and max(start[1], first[1]) < min(end[1], last[1]) - EPSILON)
            self.assertFalse(horizontal_overlap or vertical_overlap, (source, other, start, end, first, last))

        for source, (x, y) in layout.junctions:
            directions = set()
            for other, start, end in segments:
                horizontal = start[1] == end[1] == y and start[0] - EPSILON <= x <= end[0] + EPSILON
                vertical = start[0] == end[0] == x and start[1] - EPSILON <= y <= end[1] + EPSILON
                if not (horizontal or vertical):
                    continue
                self.assertEqual(source, other, (source, other, x, y))
                if horizontal:
                    if start[0] < x - EPSILON:
                        directions.add("left")
                    if end[0] > x + EPSILON:
                        directions.add("right")
                else:
                    if start[1] < y - EPSILON:
                        directions.add("down")
                    if end[1] > y + EPSILON:
                        directions.add("up")
            self.assertGreaterEqual(len(directions), 3, (source, (x, y), directions))
        return layout

    def test_all_three_variable_functions_have_connected_unobstructed_geometry(self):
        for table in range(256):
            with self.subTest(table=table):
                result = minimize_sop(3, {index for index in range(8) if table & (1 << index)})
                self.assert_geometry(build_circuit(result.cover, result.var_order))

    def test_dense_84_gate_parity_geometry_and_term_labels(self):
        circuit = parity_circuit()
        layout = self.assert_geometry(circuit)
        self.assertEqual(gate_counts(circuit)["total"], 84)
        self.assertEqual(len(layout.terms), 16)
        self.assertEqual(sum(node.kind == "NOT" for node in circuit.nodes), 5)
        self.assertTrue(layout.junctions)

    def test_direct_outputs_constants_and_unused_inputs(self):
        for cubes in ((), (Cube(3, 0, 0),), (Cube(3, 4, 4),), (Cube(3, 4, 0),)):
            with self.subTest(cubes=cubes):
                circuit = build_circuit(cubes, ("C", "A", "E"))
                layout = self.assert_geometry(circuit)
                self.assertEqual(tuple(node.id for node in layout.nodes[:3]), ("input_C", "input_A", "input_E"))
                used = {wire.source for wire in layout.wires}
                self.assertNotIn("input_A", used)
                self.assertNotIn("input_E", used)


class CircuitSVGTests(unittest.TestCase):
    def setUp(self):
        self.circuit = build_circuit((Cube(3, 5, 1), Cube(3, 6, 2)), tuple("ABC"))
        self.layout = build_layout(self.circuit)

    def render(self, bits):
        values = evaluate_circuit(self.circuit, dict(zip(self.circuit.var_order, bits)))
        return render_circuit_svg(self.circuit, self.layout, values)

    def test_real_symbols_have_binary_arity_and_explicit_direction(self):
        with patch("tools.logic_circuit_svg.logic.And", wraps=logic.And) as and_gate, \
             patch("tools.logic_circuit_svg.logic.Or", wraps=logic.Or) as or_gate, \
             patch("tools.logic_circuit_svg.logic.Not", wraps=logic.Not) as not_gate:
            svg = self.render((0, 1, 0))  # Includes vertical wires before symbol placement.
        self.assertEqual(and_gate.call_count, 2)
        self.assertEqual(or_gate.call_count, 1)
        self.assertEqual(not_gate.call_count, 1)
        self.assertTrue(all(call.kwargs == {"inputs": 2} for call in and_gate.call_args_list + or_gate.call_args_list))
        not_gate.assert_called_once_with(extend=False)
        self.assertIn(b"<svg", svg)

    def test_standalone_svg_has_background_accessible_state_and_no_external_content(self):
        svg = self.render((0, 1, 0))
        root = ET.fromstring(svg)
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        self.assertEqual(root.find("svg:title", namespace).text, "Logic circuit: F=1")
        description = root.find("svg:desc", namespace).text
        self.assertIn("A=0, B=1, C=0", description)
        self.assertIn("F=1", description)
        rect = root.find("svg:rect", namespace)
        self.assertEqual(rect.attrib["fill"], "white")
        self.assertEqual(tuple(rect.attrib[key] for key in ("x", "y", "width", "height")), tuple(root.attrib["viewBox"].split()))
        text = " ".join(root.itertext())
        for label in ("A=0", "B=1", "C=0", "T1=0", "T2=1", "F=1"):
            self.assertIn(label, text)
        for element in root.iter():
            self.assertNotIn(element.tag.rsplit("}", 1)[-1], ("script", "foreignObject", "image"))
            self.assertFalse(any(key.rsplit("}", 1)[-1] == "href" for key in element.attrib))
        self.assertIn(GATE_COLOR.encode(), svg)
        self.assertIn(SIGNAL_COLORS[0].encode(), svg)
        self.assertIn(SIGNAL_COLORS[1].encode(), svg)

    def test_redraw_is_deterministic_and_changes_with_state(self):
        first = self.render((0, 1, 0))
        second = self.render((1, 1, 0))
        self.assertNotEqual(first, second)
        self.assertIn(b"Logic circuit: F=0", second)
        self.assertEqual(first, self.render((0, 1, 0)))
        self.assertEqual(svg_size_px(first), svg_size_px(second))

    def test_svg_reserves_space_for_boundary_labels(self):
        root = ET.fromstring(self.render((0, 1, 0)))
        left, _, width, _ = map(float, root.attrib["viewBox"].split())
        for label in root.iter("{http://www.w3.org/2000/svg}text"):
            text = "".join(label.itertext())
            x = float(label.attrib["x"])
            # One font em per character is a conservative allowance for these
            # ASCII labels. This caught the clipped F=0 standalone SVG export.
            allowance = len(text) * float(label.attrib["font-size"])
            if label.attrib["text-anchor"] == "middle":
                self.assertGreaterEqual(x - left, allowance / 2, text)
                self.assertGreaterEqual(left + width - x, allowance / 2, text)
            else:
                self.assertGreaterEqual(x, left, text)
                self.assertGreaterEqual(left + width - x, allowance, text)

    def test_concurrent_renders_are_independent_and_equal_serial_results(self):
        assignments = list(product((0, 1), repeat=3))
        expected = [self.render(bits) for bits in assignments]
        with ThreadPoolExecutor(max_workers=4) as executor:
            actual = list(executor.map(self.render, assignments * 2))
        self.assertEqual(actual, expected * 2)
        self.assertEqual(len(set(expected)), 8)

    def test_dense_export_is_complete_and_contains_every_term(self):
        circuit = parity_circuit()
        svg = render_circuit_svg(circuit, build_layout(circuit), evaluate_circuit(circuit, dict.fromkeys(circuit.var_order, 0)))
        text = " ".join(ET.fromstring(svg).itertext())
        for number in range(1, 17):
            self.assertIn(f"T{number}=0", text)
        width, height = svg_size_px(svg)
        self.assertGreater(width, 1000)
        self.assertGreater(height, 2000)
        self.assertNotIn(b"clipPath", svg)  # Export contains the circuit, not a viewport crop.

    def test_constants_and_single_literals_export_without_fake_gates(self):
        for cubes in ((), (Cube(1, 0, 0),), (Cube(1, 1, 1),), (Cube(1, 1, 0),)):
            circuit = build_circuit(cubes, ("E",))
            with self.subTest(cubes=cubes):
                values = evaluate_circuit(circuit, {"E": 0})
                svg = render_circuit_svg(circuit, build_layout(circuit), values)
                self.assertIn(f"Logic circuit: F={values[circuit.output]}".encode(), svg)
                self.assertTrue(all(size > 0 for size in svg_size_px(svg)))

    def test_render_rejects_mismatched_layout_and_incomplete_or_nonbinary_state(self):
        values = evaluate_circuit(self.circuit, {"A": 0, "B": 0, "C": 0})
        other = build_circuit((), tuple("ABC"))
        with self.assertRaises(ValueError):
            render_circuit_svg(other, self.layout, values)
        for invalid in ({}, {**values, "extra": 0}, {**values, "input_A": 2}, {**values, "input_A": "0"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                render_circuit_svg(self.circuit, self.layout, invalid)

    def test_intrinsic_svg_dimensions_convert_points_to_css_pixels(self):
        self.assertEqual(svg_size_px(b'<svg width="72pt" height="144pt" viewBox="0 0 72 144"/>'), (96, 192))
        self.assertEqual(svg_size_px(b'<svg width="100px" height="200" viewBox="0 0 1 1"/>'), (100, 200))
        self.assertEqual(svg_size_px(b'<svg viewBox="-10 -20 120 240"/>'), (120, 240))
        for dimension in ("0", "-1", "50%", "NaN"):
            with self.subTest(dimension=dimension), self.assertRaises(ValueError):
                svg_size_px(f'<svg width="{dimension}" height="72pt" viewBox="0 0 1 1"/>'.encode())


if __name__ == "__main__":
    unittest.main()
