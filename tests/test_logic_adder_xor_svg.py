"""Check the simplified adder's real gate geometry and complete SVG output."""

from itertools import combinations, product
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from schemdraw import logic

from tools.logic_adder import build_xor_full_adder, build_xor_four_bit_adder, evaluate_four_bit
from tools.logic_adder_xor_svg import build_xor_adder_scene, render_xor_adder_svg
from tools.logic_circuit import evaluate_network
from tools.logic_circuit_svg import SIGNAL_COLORS, _wire_segments, svg_size_px


EPS = 1e-8


class XorAdderSVGTests(unittest.TestCase):
    def test_every_gate_edge_and_output_is_drawn_without_gate_or_wire_overlap(self):
        for adder in (build_xor_full_adder(), build_xor_four_bit_adder()):
            scene = build_xor_adder_scene(adder)
            nodes = {node.id: node for node in scene.signals}
            placed = {node.id: node for node in scene.nodes}
            self.assertEqual(set(nodes), set(placed))
            edges = []
            terminals = []
            for wire in scene.wires:
                self.assertEqual(wire.points[0], placed[wire.source].output)
                if wire.target is None:
                    terminals.append(wire.source)
                else:
                    self.assertEqual(wire.source, nodes[wire.target].inputs[wire.input_index])
                    self.assertEqual(wire.points[-1], placed[wire.target].inputs[wire.input_index])
                    edges.append((wire.source, wire.target, wire.input_index))
            self.assertCountEqual(edges, [(source, node.id, index) for node in scene.signals
                                          for index, source in enumerate(node.inputs)])
            self.assertCountEqual(terminals, [output.source for output in adder.network.outputs])
            boxes = [(node.id, node.box) for node in scene.nodes if node.box]
            self.assertEqual(len(boxes), 5 * len(adder.stages))
            for group in scene.groups:
                left, bottom, right, top = group.box
                self.assertEqual(sum(left < box[0] < box[2] < right and
                                     bottom < box[1] < box[3] < top for _, box in boxes), 5)
            segments = _wire_segments(scene)
            for source, start, end in segments:
                for node_id, (left, bottom, right, top) in boxes:
                    intersects = (bottom + EPS < start[1] < top - EPS and
                                  max(start[0], left) < min(end[0], right) - EPS) if start[1] == end[1] else (
                                  left + EPS < start[0] < right - EPS and
                                  max(start[1], bottom) < min(end[1], top) - EPS)
                    self.assertFalse(intersects, (source, start, end, node_id))
            for (source, start, end), (other, first, last) in combinations(segments, 2):
                if source == other:
                    continue
                self.assertFalse(start[1] == end[1] == first[1] == last[1] and
                                 max(start[0], first[0]) < min(end[0], last[0]) - EPS,
                                 (source, other, start, end, first, last))
                self.assertFalse(start[0] == end[0] == first[0] == last[0] and
                                 max(start[1], first[1]) < min(end[1], last[1]) - EPS,
                                 (source, other, start, end, first, last))
            for source, point in scene.junctions:
                directions = set()
                x, y = point
                for other, start, end in segments:
                    if start[1] == end[1] == y and start[0] <= x <= end[0]:
                        self.assertEqual(source, other, (point, source, other))
                        if start[0] < x:
                            directions.add("left")
                        if x < end[0]:
                            directions.add("right")
                    if start[0] == end[0] == x and start[1] <= y <= end[1]:
                        self.assertEqual(source, other, (point, source, other))
                        if start[1] < y:
                            directions.add("down")
                        if y < end[1]:
                            directions.add("up")
                self.assertGreaterEqual(len(directions), 3)

    def test_all_one_bit_states_preserve_outputs_and_render_real_xor_anchors(self):
        adder = build_xor_full_adder()
        scene = build_xor_adder_scene(adder)
        sizes = set()
        for bits in product((0, 1), repeat=3):
            values = evaluate_network(adder.network, dict(zip(adder.network.var_order, bits)))
            svg = render_xor_adder_svg(adder, scene, values)
            text = " ".join(ET.fromstring(svg).itertext())
            self.assertIn(f"S={sum(bits) % 2}", text)
            self.assertIn(f"Cout={sum(bits) // 2}", text)
            self.assertIn(f"P={bits[0] ^ bits[1]}", text)
            sizes.add(svg_size_px(svg))
        self.assertEqual(len(sizes), 1)

    def test_four_bit_export_shows_all_twenty_gates_and_internal_carry_state(self):
        adder = build_xor_four_bit_adder()
        scene = build_xor_adder_scene(adder)
        values = evaluate_four_bit(adder, "1111", "0001").values
        with patch("tools.logic_circuit_svg.logic.Xor", wraps=logic.Xor) as xor_gate, \
             patch("tools.logic_circuit_svg.logic.And", wraps=logic.And) as and_gate, \
             patch("tools.logic_circuit_svg.logic.Or", wraps=logic.Or) as or_gate, \
             patch("tools.logic_circuit_svg.logic.Not", wraps=logic.Not) as not_gate:
            svg = render_xor_adder_svg(adder, scene, values)
        self.assertEqual((xor_gate.call_count, and_gate.call_count, or_gate.call_count, not_gate.call_count),
                         (8, 8, 4, 0))
        self.assertTrue(all(call.kwargs == {"inputs": 2}
                            for call in xor_gate.call_args_list + and_gate.call_args_list + or_gate.call_args_list))
        text = " ".join(ET.fromstring(svg).itertext())
        for i in range(4):
            self.assertIn(f"S{i}=0", text)
            self.assertIn(f"C{i + 1}=1", text)
            if i < 3:
                self.assertNotIn(adder.stages[i].carry_output,
                                 [wire.source for wire in scene.wires if wire.target is None])
        self.assertIn("C0=0", text)
        self.assertIn(SIGNAL_COLORS[0].encode(), svg)
        self.assertIn(SIGNAL_COLORS[1].encode(), svg)
        self.assertNotIn(b"clipPath", svg)
        self.assertNotIn(b"<script", svg)
        width, height = svg_size_px(svg)
        self.assertLess(width, 1000)
        self.assertLess(height, 2000)

    def test_rejects_mismatched_scene_and_incomplete_signal_values(self):
        adder = build_xor_four_bit_adder()
        scene = build_xor_adder_scene(adder)
        with self.assertRaises(ValueError):
            render_xor_adder_svg(build_xor_full_adder(), scene, {})
        with self.assertRaises(ValueError):
            render_xor_adder_svg(adder, scene, {})


if __name__ == "__main__":
    unittest.main()
