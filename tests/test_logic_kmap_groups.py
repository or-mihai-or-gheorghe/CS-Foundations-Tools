"""Regression coverage for identifying fragmented, overlapping K-map groups."""

from html.parser import HTMLParser
from itertools import combinations, product
import random
import re
import unittest

from streamlit.testing.v1 import AppTest

from tools.logic_kmap_sop import build_maps, render_kmap_html
from tools.logic_minimization import minimize_sop


class GroupMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.segments = []
        self.labels = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("class") == "group":
            self.segments.append(attrs)
        elif attrs.get("class") == "group-label":
            self.labels.append(attrs)


def style_pixels(element, name):
    return float(re.search(rf"(?:^|;)\s*{name}:([\d.]+)px", element["style"])[1])


class KmapGroupTests(unittest.TestCase):
    def render(self, ones, dont_cares=()):
        result = minimize_sop(5, ones, dont_cares)
        model = build_maps(5, list("ABCDE"))
        values = {m: "1" if m in ones else "X" if m in dont_cares else "0"
                  for m in range(32)}
        html = render_kmap_html(model, values, result.cover)
        return result, model, html, GroupMarkup(html)

    def assert_labels_identify_segments(self, result, model, html, markup):
        self.assertEqual(len(markup.labels), len(markup.segments))
        rectangles = []
        for label in markup.labels:
            group = int(label["data-group"])
            part = int(label["data-segment"])
            segments = [segment for segment in markup.segments
                        if int(segment["data-group"]) == group]
            segment = segments[part - 1]
            left, top = (style_pixels(segment, prop) for prop in ("left", "top"))
            right = left + style_pixels(segment, "width")
            bottom = top + style_pixels(segment, "height")
            # Labels occupy 20 x 10 px, including padding, inside their own part.
            x, y = (style_pixels(label, prop) for prop in ("left", "top"))
            self.assertGreaterEqual(x, left)
            self.assertGreaterEqual(y, top)
            self.assertLessEqual(x + 20, right)
            self.assertLessEqual(y + 10, bottom)
            rectangles.append((x, y, x + 20, y + 10))

            # Derive the visible part's support from cell centers, independently
            # of the production segmentation helper.
            support = sorted(m for r, row in enumerate(model["cell_to_min"])
                             for c, m in enumerate(row)
                             if left <= c * 48 + 22 <= right
                             and top <= r * 48 + 22 <= bottom)
            self.assertTrue(support)
            self.assertLessEqual(set(support), result.cover[group - 1].covered_minterms)
            self.assertEqual(label["title"],
                             f"Group {group}, part {part} of {len(segments)}: minterms {support}")
        for first, second in combinations(rectangles, 2):
            overlap = (max(first[0], second[0]) < min(first[2], second[2])
                       and max(first[1], second[1]) < min(first[3], second[3]))
            self.assertFalse(overlap, (first, second))
        if markup.labels:
            # Later colored overlays must not hide previously drawn labels.
            self.assertLess(html.rindex("class='group'"), html.index("class='group-label'"))

    def test_reported_five_variable_group_has_two_distinct_visible_badges(self):
        ones = {1, 3, 7, 11, 15, 8, 9, 13, 12}
        result, model, html, markup = self.render(ones)
        self.assertEqual(result.terms, ("A'·D·E", "A'·C'·E", "A'·B·D'"))
        self.assertEqual(result.cover[0].covered_minterms, {3, 7, 11, 15})
        # Arithmetic enumeration is independent of the minimizer's cube masks.
        expected = {16 * a + 8 * b + 4 * c + 2 * d + e
                    for a, b, c, d, e in product((0, 1), repeat=5)
                    if (not a and d and e) or (not a and not c and e)
                    or (not a and b and not d)}
        self.assertEqual(expected, ones)
        labels = [label for label in markup.labels if label["data-group"] == "1"]
        self.assertEqual([label["title"] for label in labels], [
            "Group 1, part 1 of 2: minterms [3, 11]",
            "Group 1, part 2 of 2: minterms [7, 15]",
        ])
        self.assert_labels_identify_segments(result, model, html, markup)

    def test_seeded_five_variable_labels_remain_distinct_and_attached(self):
        rng = random.Random(20260908)
        cases = [(set(), set()), (set(range(32)), set()),
                 ({m for m in range(32) if m.bit_count() % 2}, set())]
        for sample in range(160):
            table = [rng.randrange(2 if sample % 2 else 3) for _ in range(32)]
            cases.append(({m for m, value in enumerate(table) if value == 1},
                          {m for m, value in enumerate(table) if value == 2}))
        for sample, (ones, dont_cares) in enumerate(cases):
            with self.subTest(seed=20260908, sample=sample,
                              ones=sorted(ones), dont_cares=sorted(dont_cares)):
                self.assert_labels_identify_segments(*self.render(ones, dont_cares))

    def test_selected_implicants_explain_the_reported_visible_parts(self):
        app = AppTest.from_string(
            "from tools.logic_kmap_sop import render\nrender()\n", default_timeout=20
        ).run()
        app.radio(key="kmap_input_mode").set_value("Truth Table").run()
        app.selectbox(key="kmap_nvars").select(5)
        app.text_area(key="kmap_minterms").set_value("1,3,7,11,15,8,9,13,12")
        app.button(key="kmap_minimize_truth_table").click().run()
        self.assertEqual(len(app.exception), 0, [error.message for error in app.exception])
        captions = [caption.value for caption in app.caption]
        self.assertIn("G1 is one group drawn in 2 parts: [3, 11] and [7, 15].", captions)
        self.assertIn("G3 is one group drawn in 2 parts: [8, 9] and [12, 13].", captions)


if __name__ == "__main__":
    unittest.main()
