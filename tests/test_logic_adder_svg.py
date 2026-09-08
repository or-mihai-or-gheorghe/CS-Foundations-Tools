"""Verify physical connectivity and complete SVGs for the fixed adder lesson."""

from itertools import combinations, product
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from schemdraw import logic

from tools.logic_adder import build_full_adder, build_four_bit_adder, evaluate_four_bit
from tools.logic_adder_svg import build_adder_scene, render_adder_svg
from tools.logic_circuit import evaluate_network
from tools.logic_circuit_svg import (
    CIRCUIT_FONT_SIZE, SIGNAL_COLORS, _wire_segments, build_layout, render_circuit_svg, svg_size_px,
)


EPS = 1e-8


def incident_directions(start, end, point):
    x, y = point
    result = set()
    if start[1] == end[1] and abs(start[1] - y) < EPS and start[0] - EPS <= x <= end[0] + EPS:
        if start[0] < x - EPS:
            result.add("left")
        if x < end[0] - EPS:
            result.add("right")
    if start[0] == end[0] and abs(start[0] - x) < EPS and start[1] - EPS <= y <= end[1] + EPS:
        if start[1] < y - EPS:
            result.add("down")
        if y < end[1] - EPS:
            result.add("up")
    return result


class AdderGeometryTests(unittest.TestCase):
    def assert_geometry(self, adder):
        scene = build_adder_scene(adder)
        nodes = {node.id: node for node in adder.network.nodes}
        positions = {node.id: node for node in scene.nodes}
        self.assertEqual(set(nodes), set(positions))
        self.assertEqual(len(nodes), len(scene.nodes))
        self.assertEqual(scene, build_adder_scene(adder))
        expected_edges = {(source, node.id, index) for node in nodes.values()
                          for index, source in enumerate(node.inputs)}
        actual_edges = []
        output_sources = {output.source for output in adder.network.outputs}
        terminal_sources = []
        for wire in scene.wires:
            self.assertEqual(wire.points[0], positions[wire.source].output)
            if wire.target is None:
                self.assertIn(wire.source, output_sources)
                terminal_sources.append(wire.source)
            else:
                self.assertEqual(nodes[wire.target].inputs[wire.input_index], wire.source)
                self.assertEqual(wire.points[-1], positions[wire.target].inputs[wire.input_index])
                actual_edges.append((wire.source, wire.target, wire.input_index))
        self.assertEqual(set(actual_edges), expected_edges)
        self.assertEqual(len(actual_edges), len(expected_edges))
        self.assertCountEqual(terminal_sources, output_sources)
        for node in nodes.values():
            self.assertEqual(len(positions[node.id].inputs), len(node.inputs))
        boxes = [(node.id, node.box) for node in positions.values() if node.box]
        self.assertEqual(len(boxes), 19 * len(adder.stages))
        self.assertEqual(len(scene.groups), len(adder.stages))
        for group in scene.groups:
            left, bottom, right, top = group.box
            enclosed = [box for _, box in boxes if left < box[0] < box[2] < right
                        and bottom < box[1] < box[3] < top]
            self.assertEqual(len(enclosed), 19)
        for (name, box), (other, bounds) in combinations(boxes, 2):
            self.assertFalse(max(box[0], bounds[0]) < min(box[2], bounds[2]) - EPS
                             and max(box[1], bounds[1]) < min(box[3], bounds[3]) - EPS,
                             (name, other))
        segments = _wire_segments(scene)  # Also rejects nonorthogonal paths.
        for source, start, end in segments:
            for node_id, (left, bottom, right, top) in boxes:
                hits = (bottom + EPS < start[1] < top - EPS and
                        max(start[0], left) < min(end[0], right) - EPS) if start[1] == end[1] else (
                        left + EPS < start[0] < right - EPS and
                        max(start[1], bottom) < min(end[1], top) - EPS)
                self.assertFalse(hits, (source, start, end, node_id))
        for (source, start, end), (other, first, last) in combinations(segments, 2):
            if source == other:
                continue
            self.assertFalse(start[1] == end[1] == first[1] == last[1]
                             and max(start[0], first[0]) < min(end[0], last[0]) - EPS,
                             (source, other, start, end, first, last))
            self.assertFalse(start[0] == end[0] == first[0] == last[0]
                             and max(start[1], first[1]) < min(end[1], last[1]) - EPS,
                             (source, other, start, end, first, last))
        for source, point in scene.junctions:
            directions = set()
            for other, start, end in segments:
                incident = incident_directions(start, end, point)
                if incident:
                    self.assertEqual(source, other, (source, other, point))
                    directions.update(incident)
            self.assertGreaterEqual(len(directions), 3, (source, point))
        return scene

    def test_shared_one_bit_inputs_and_four_complete_carry_connected_stages(self):
        for adder in (build_full_adder(), build_four_bit_adder()):
            with self.subTest(stages=len(adder.stages)):
                scene = self.assert_geometry(adder)
                self.assertEqual(sum(node.kind == "INPUT" for node in scene.signals),
                                 3 if len(adder.stages) == 1 else 8)
                self.assertEqual(sum(node.kind == "CONST" for node in scene.signals),
                                 0 if len(adder.stages) == 1 else 1)

    def test_extended_sum_rails_gain_their_previously_missing_final_tap_junctions(self):
        for adder in (build_full_adder(), build_four_bit_adder()):
            scene = build_adder_scene(adder)
            positions = {node.id: node for node in scene.nodes}
            dots = set(scene.junctions)
            for stage in adder.stages:
                top = positions[stage.inputs[0]].output[1]
                for source, x, last_y in zip(stage.inputs, (0.0, 1.0, 2.0), (-19.5, -20.65, -21.8)):
                    self.assertIn((source, (x, top + last_y)), dots)

    def test_internal_carry_has_one_real_source_and_no_terminal_port(self):
        adder = build_four_bit_adder()
        scene = build_adder_scene(adder)
        positions = {node.id: node for node in scene.nodes}
        for previous, following in zip(adder.stages, adder.stages[1:]):
            self.assertEqual(previous.carry_output, following.inputs[2])
            outgoing = [wire for wire in scene.wires if wire.source == previous.carry_output]
            self.assertTrue(outgoing)
            self.assertTrue(all(wire.target is not None for wire in outgoing))
            self.assertTrue(all(wire.points[0] == positions[previous.carry_output].output for wire in outgoing))
            self.assertTrue(all(wire.points[-1][1] < positions[previous.carry_output].output[1]
                                for wire in outgoing))

    def test_internal_carry_input_labels_do_not_cover_their_incoming_wire(self):
        adder = build_four_bit_adder()
        scene = build_adder_scene(adder)
        positions = {node.id: node for node in scene.nodes}
        em = CIRCUIT_FONT_SIZE / (72 * 0.4)  # Match the renderer's font and drawing scale.
        for stage in adder.stages[1:]:
            top = positions[stage.inputs[0]].output[1]
            label = next(item for item in scene.labels if item.source == stage.inputs[2]
                         and abs(item.position[1] - (top + 0.5)) < EPS)
            x, y = label.position
            width = len(f"{label.text}=0") * em
            left = x - width / 2 if label.align == "center" else x
            right, bottom, upper = left + width, y - em, y + em
            for source, start, end in _wire_segments(scene):
                if source != stage.inputs[2]:
                    continue
                intersects = (bottom < start[1] < upper and
                              max(start[0], left) < min(end[0], right)) if start[1] == end[1] else (
                              left < start[0] < right and
                              max(start[1], bottom) < min(end[1], upper))
                self.assertFalse(intersects, (label.text, start, end))


class AdderSVGTests(unittest.TestCase):
    def test_all_one_bit_states_export_both_correct_outputs_and_shared_input_labels(self):
        adder = build_full_adder()
        scene = build_adder_scene(adder)
        sizes = set()
        for bits in product((0, 1), repeat=3):
            values = evaluate_network(adder.network, dict(zip(adder.network.var_order, bits)))
            svg = render_adder_svg(adder, scene, values)
            sizes.add(svg_size_px(svg))
            text = " ".join(ET.fromstring(svg).itertext())
            self.assertIn(f"S={sum(bits) % 2}", text)
            self.assertIn(f"Cout={sum(bits) // 2}", text)
            self.assertIn(f"Cin={bits[2]}", text)
            self.assertIn(f"Carry input: Cin={bits[2]}", text)
            self.assertNotIn("Internal carry:", text)
            self.assertEqual(svg, render_adder_svg(adder, scene, values))
        self.assertEqual(len(sizes), 1)

    def test_four_bit_svg_uses_all_real_symbols_and_no_fake_carry_inputs(self):
        adder = build_four_bit_adder()
        scene = build_adder_scene(adder)
        values = evaluate_four_bit(adder, "0111", "1001").values
        with patch("tools.logic_circuit_svg.logic.And", wraps=logic.And) as and_gate, \
             patch("tools.logic_circuit_svg.logic.Or", wraps=logic.Or) as or_gate, \
             patch("tools.logic_circuit_svg.logic.Not", wraps=logic.Not) as not_gate:
            svg = render_adder_svg(adder, scene, values)
        self.assertEqual((and_gate.call_count, or_gate.call_count, not_gate.call_count), (44, 20, 12))
        self.assertTrue(all(call.kwargs == {"inputs": 2} for call in and_gate.call_args_list + or_gate.call_args_list))
        self.assertTrue(all(call.kwargs == {"extend": False} for call in not_gate.call_args_list))
        root = ET.fromstring(svg)
        text = " ".join(root.itertext())
        for index in range(4):
            for name in (f"Bit {index}", f"A{index}=", f"B{index}=", f"S{index}=0", f"C{index}="):
                self.assertIn(name, text)
        self.assertIn("C4=1", text)
        self.assertIn("0 is red; 1 is green", text)
        self.assertIn(SIGNAL_COLORS[0].encode(), svg)
        self.assertIn(SIGNAL_COLORS[1].encode(), svg)
        self.assertIn(b"stroke-dasharray", svg)
        self.assertNotIn(b"clipPath", svg)
        self.assertFalse(any(element.tag.rsplit("}", 1)[-1] in ("script", "foreignObject", "image")
                             for element in root.iter()))
        self.assertFalse(any(key.rsplit("}", 1)[-1] == "href" for element in root.iter() for key in element.attrib))
        width, height = svg_size_px(svg)
        self.assertGreater(width, 1000)
        self.assertGreater(height, 5000)

    def test_boundary_labels_have_room_in_standalone_exports(self):
        for adder in (build_full_adder(), build_four_bit_adder()):
            values = evaluate_network(adder.network, dict.fromkeys(adder.network.var_order, 0))
            svg = render_adder_svg(adder, build_adder_scene(adder), values)
            root = ET.fromstring(svg)
            left, top, width, height = map(float, root.attrib["viewBox"].split())
            for element in root.iter("{http://www.w3.org/2000/svg}text"):
                text = "".join(element.itertext())
                x, y, size = (float(element.attrib[name]) for name in ("x", "y", "font-size"))
                allowance = len(text) * size
                self.assertGreaterEqual(y - top, size, text)
                self.assertGreaterEqual(top + height - y, size, text)
                if element.attrib["text-anchor"] == "middle":
                    self.assertGreaterEqual(x - left, allowance / 2, text)
                    self.assertGreaterEqual(left + width - x, allowance / 2, text)
                else:
                    self.assertGreaterEqual(x, left, text)
                    self.assertGreaterEqual(left + width - x, allowance, text)

    def test_standalone_branch_aliases_do_not_change_the_sop_or_its_geometry(self):
        adder = build_full_adder()
        for circuit, output in ((adder.sum_circuit, "S"), (adder.carry_circuit, "Cout")):
            mapping = dict(adder.stages[0].sum_nodes if output == "S" else adder.stages[0].carry_nodes)
            global_values = evaluate_network(adder.network, {"A": 1, "B": 0, "Cin": 1})
            values = {local: global_values[source] for local, source in mapping.items()}
            svg = render_circuit_svg(circuit, build_layout(circuit), values,
                                     input_labels={"C": "Cin"}, output_label=output)
            text = " ".join(ET.fromstring(svg).itertext())
            self.assertIn("Cin=1", text)
            self.assertIn(f"{output}={0 if output == 'S' else 1}", text)
            self.assertNotIn("F=", text)

    def test_wrong_network_and_invalid_values_are_rejected(self):
        adder = build_full_adder()
        scene = build_adder_scene(adder)
        with self.assertRaises(ValueError):
            render_adder_svg(build_four_bit_adder(), scene, {})
        values = evaluate_network(adder.network, {"A": 0, "B": 0, "Cin": 0})
        for invalid in ({}, {**values, "extra": 0}, {**values, "input_A": 2}):
            with self.assertRaises(ValueError):
                render_adder_svg(adder, scene, invalid)


if __name__ == "__main__":
    unittest.main()
