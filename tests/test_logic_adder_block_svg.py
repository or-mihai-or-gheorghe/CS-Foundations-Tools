"""Check the block overview's bit order, real carry wiring, and SVG exports."""

import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from schemdraw import elements as elm

from tools.logic_adder import build_four_bit_adder, build_full_adder, evaluate_four_bit
from tools.logic_adder_block_svg import render_adder_blocks_svg
from tools.logic_circuit_svg import SIGNAL_COLORS, svg_size_px


CASES = (("0000", "0000"), ("0101", "0011"), ("1111", "0001"), ("1111", "1111"))
SVG_NS = "{http://www.w3.org/2000/svg}"
EPS = 1e-8


class AdderBlockSVGTests(unittest.TestCase):
    def test_all_operand_sum_and_carry_arrows_use_the_corresponding_real_signal(self):
        adder = build_four_bit_adder()
        for a, b in CASES:
            with self.subTest(a=a, b=b):
                arrows, rectangles = [], []
                real_arrow, real_rect = elm.Arrow, elm.Rect

                def arrow(*args, **kwargs):
                    item = real_arrow(*args, **kwargs)
                    arrows.append(item)
                    return item

                def rectangle(*args, **kwargs):
                    item = real_rect(*args, **kwargs)
                    rectangles.append(item)
                    return item

                values = evaluate_four_bit(adder, a, b).values
                with patch("tools.logic_adder_block_svg.elm.Arrow", side_effect=arrow), \
                     patch("tools.logic_adder_block_svg.elm.Rect", side_effect=rectangle):
                    render_adder_blocks_svg(adder, values)
                boxes = sorted((item.get_bbox(transform=True) for item in rectangles),
                               key=lambda box: box.xmin, reverse=True)
                self.assertEqual(len(boxes), 4)
                self.assertEqual(len(arrows), 17)  # Eight inputs, four sums, five carries.
                used = set()
                for stage, box in zip(adder.stages, boxes):
                    incoming = sorted((item for item in arrows
                                       if box.xmin < item.absanchors["end"].x < box.xmax
                                       and abs(item.absanchors["end"].y - box.ymax) < EPS),
                                      key=lambda item: item.absanchors["end"].x)
                    self.assertEqual(len(incoming), 2)
                    for item, source in zip(incoming, stage.inputs[:2]):
                        start, end = item.absanchors["start"], item.absanchors["end"]
                        self.assertAlmostEqual(start.x, end.x)
                        self.assertGreater(start.y, end.y)
                        self.assertEqual(item.params["color"], SIGNAL_COLORS[values[source]])
                        used.add(id(item))
                    sums = [item for item in arrows
                            if abs(item.absanchors["start"].x - (box.xmin + box.xmax) / 2) < EPS
                            and abs(item.absanchors["start"].y - box.ymin) < EPS]
                    self.assertEqual(len(sums), 1)
                    item = sums[0]
                    self.assertAlmostEqual(item.absanchors["start"].x, item.absanchors["end"].x)
                    self.assertLess(item.absanchors["end"].y, box.ymin)
                    self.assertEqual(item.params["color"], SIGNAL_COLORS[values[stage.sum_output]])
                    used.add(id(item))
                    carries = [item for item in arrows
                               if abs(item.absanchors["start"].x - box.xmin) < EPS
                               and box.ymin < item.absanchors["start"].y < box.ymax]
                    self.assertEqual(len(carries), 1)
                    item = carries[0]
                    start, end = item.absanchors["start"], item.absanchors["end"]
                    self.assertLess(end.x, start.x)
                    self.assertAlmostEqual(start.y, end.y)
                    self.assertEqual(item.params["color"], SIGNAL_COLORS[values[stage.carry_output]])
                    if stage.index < 3:
                        self.assertAlmostEqual(end.x, boxes[stage.index + 1].xmax)
                        self.assertEqual(stage.carry_output, adder.stages[stage.index + 1].inputs[2])
                    used.add(id(item))
                initial = [item for item in arrows if id(item) not in used]
                self.assertEqual(len(initial), 1)
                start, end = initial[0].absanchors["start"], initial[0].absanchors["end"]
                self.assertGreater(start.x, end.x)
                self.assertAlmostEqual(start.y, end.y)
                self.assertAlmostEqual(end.x, boxes[0].xmax)
                self.assertTrue(boxes[0].ymin < end.y < boxes[0].ymax)
                self.assertEqual(initial[0].params["color"], SIGNAL_COLORS[values[adder.stages[0].inputs[2]]])

    def test_svg_has_msb_on_left_complete_state_labels_and_self_contained_bounds(self):
        adder = build_four_bit_adder()
        sizes = set()
        for a, b in CASES:
            with self.subTest(a=a, b=b):
                result = evaluate_four_bit(adder, a, b)
                svg = render_adder_blocks_svg(adder, result.values)
                sizes.add(svg_size_px(svg))
                root = ET.fromstring(svg)
                text_elements = list(root.iter(SVG_NS + "text"))
                labels = {"".join(element.itertext()): element for element in text_elements}
                self.assertEqual(sorted((name for name in labels if name.startswith("FA")),
                                        key=lambda name: float(labels[name].attrib["x"])),
                                 ["FA3", "FA2", "FA1", "FA0"])
                for i, ai, bi, cin, total, cout in result.stages:
                    for name in (f"A{i}={ai}", f"B{i}={bi}", f"S{i}={total}",
                                 f"C{i}={cin}", f"C{i + 1}={cout}"):
                        self.assertIn(name, labels)
                self.assertIn("Fixed 0", labels)
                self.assertIsNotNone(root.find(SVG_NS + "title"))
                self.assertIn("right to left", root.find(SVG_NS + "desc").text)
                left, top, width, height = map(float, root.attrib["viewBox"].split())
                self.assertGreater(width, 2 * height)
                for element in text_elements:
                    text = "".join(element.itertext())
                    x, y, size = (float(element.attrib[name]) for name in ("x", "y", "font-size"))
                    allowance = len(text) * size
                    anchor = element.attrib["text-anchor"]
                    text_left = x - allowance / 2 if anchor == "middle" else x - allowance if anchor == "end" else x
                    text_right = x + allowance / 2 if anchor == "middle" else x if anchor == "end" else x + allowance
                    self.assertGreaterEqual(text_left, left, text)
                    self.assertLessEqual(text_right, left + width, text)
                    self.assertGreaterEqual(y - size, top, text)
                    self.assertLessEqual(y + size, top + height, text)
                self.assertFalse(any(element.tag.rsplit("}", 1)[-1] in ("script", "foreignObject", "image")
                                     for element in root.iter()))
                self.assertFalse(any(key.rsplit("}", 1)[-1] == "href"
                                     for element in root.iter() for key in element.attrib))
        self.assertEqual(len(sizes), 1)

    def test_one_bit_and_invalid_signal_values_are_rejected(self):
        with self.assertRaises(ValueError):
            render_adder_blocks_svg(build_full_adder(), {})
        adder = build_four_bit_adder()
        values = evaluate_four_bit(adder, "0000", "0000").values
        for invalid in ({}, {**values, "extra": 0}, {**values, "input_A0": 2},
                        {**values, "input_A0": "0"}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                render_adder_blocks_svg(adder, invalid)


if __name__ == "__main__":
    unittest.main()
