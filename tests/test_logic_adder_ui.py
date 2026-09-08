"""Lesson synchronization and input lifecycle on Streamlit's real script runner."""

import base64
import re
import unittest

from streamlit.testing.v1 import AppTest

from tools.logic_adder import build_full_adder
from tools.logic_circuit_svg import svg_size_px
from tools.logic_kmap_sop import build_maps, render_kmap_html


class AdderLessonUI(unittest.TestCase):
    diagram_names = ("sum", "carry", "full_adder", "four_bit_blocks", "four_bit", "four_bit_xor")
    switch_groups = ("sum_bit", "sum_circuit", "carry_bit", "carry_circuit", "full_adder")
    input_names = ("A", "B", "Cin")

    def switch_key(self, group, bit):
        return f"adder_input_{bit}" if group == "sum_bit" else f"adder_input_{group}_{bit}"

    def app(self):
        app = AppTest.from_string(
            "from tools.logic_adder_lesson import render\nrender()\n", default_timeout=30
        ).run()
        self.clean(app)
        return app

    def clean(self, app):
        self.assertEqual([e.message for e in app.exception], [])

    def metrics(self, app):
        return {metric.label: metric.value for metric in app.metric}

    def html(self, app):
        return [element.proto.body for element in app.get("html")]

    def table(self, app, name):
        return next(body for body in self.html(app) if f"aria-label='{name}'" in body)

    def set_operands(self, app, a, b):
        app.text_input(key="adder_operand_a").set_value(a)
        app.text_input(key="adder_operand_b").set_value(b)
        app.run()
        self.clean(app)

    def assert_one_bit_state(self, app, expected):
        """Check every input copy and every consumer after a single widget event."""
        self.clean(app)
        self.assertEqual(app.session_state["adder_one_bit_inputs"], expected)
        self.assertEqual([toggle.key for toggle in app.toggle], [
            self.switch_key(group, bit)
            for group in self.switch_groups for bit in self.input_names
        ])
        for group in self.switch_groups:
            for bit in self.input_names:
                toggle = app.toggle(key=self.switch_key(group, bit))
                self.assertEqual(toggle.value, expected[bit])
                self.assertEqual(toggle.label, f"{bit}={int(expected[bit])}")
        signature = tuple(int(expected[bit]) for bit in self.input_names)
        minterm = signature[0] * 4 + signature[1] * 2 + signature[2]
        total = sum(signature)
        outputs = {"S": total % 2, "Cout": total // 2}
        for output, value in outputs.items():
            self.assertEqual(self.metrics(app)[output], str(value))
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", self.table(app, f"{output} truth table"),
                              flags=re.S)[1:]
            self.assertEqual([i for i, row in enumerate(rows) if "Active" in row], [minterm])
            self.assertEqual(re.findall(r"<td>(.*?)</td>", rows[minterm]),
                             [*(str(bit) for bit in signature), str(value), "Active"])
        maps = [body for body in self.html(app) if "logic-kmap-display" in body]
        self.assertEqual(len(maps), 2)
        for body, output in zip(maps, ("S", "Cout")):
            self.assertIn(f"data-active-minterm='{minterm}'", body)
            self.assertIn(f"Selected input: minterm {minterm}, output {outputs[output]}", body)
        descriptions = [body for body in self.html(app) if "<img " in body][:3]
        for name, body in zip(("sum", "carry", "full_adder"), descriptions):
            current = app.session_state[f"adder_svg_{name}"]
            self.assertEqual(current["signature"], signature)
            svg = current["data"].decode()
            for bit, value in zip(self.input_names, signature):
                self.assertIn(f"{bit}={value}", body)
                self.assertIn(f"{bit}={value}", svg)
            for output in (("S",) if name == "sum" else
                           ("Cout",) if name == "carry" else ("S", "Cout")):
                self.assertIn(f"{output}={outputs[output]}", body)
                self.assertIn(f"{output}={outputs[output]}", svg)
            encoded = re.search(r"base64,([^\"]+)", body).group(1)
            self.assertEqual(base64.b64decode(encoded), current["data"])

    def test_defaults_tables_maps_and_six_current_exports(self):
        app = self.app()
        self.assertEqual(self.metrics(app), {
            "S": "0", "Cout": "1", "Sum (4 bits)": "1000", "Carry C4": "0",
            "Full result (5 bits)": "01000",
        })
        self.assert_one_bit_state(app, {"A": True, "B": True, "Cin": False})
        prose = "\n".join(element.value for kind in ("markdown", "caption", "success", "info")
                          for element in app.get(kind))
        self.assertNotIn("S + 2·Cout", prose)
        for name in ("S", "Cout"):
            body = self.table(app, f"{name} truth table")
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", body, flags=re.S)[1:]
            self.assertEqual(len(rows), 8)
            self.assertEqual(sum("Active" in row for row in rows), 1)
            self.assertIn("Active", rows[6])
        maps = [body for body in self.html(app) if "logic-kmap-display" in body]
        self.assertEqual(len(maps), 2)
        for body in maps:
            self.assertIn("data-active-minterm='6'", body)
            self.assertEqual(body.count("(B,Cin)"), 1)
        self.assertEqual(len(app.get("download_button")), 6)
        image_sources = [base64.b64decode(re.search(r"base64,([^\"]+)", body).group(1))
                         for body in self.html(app) if "<img " in body]
        for name, svg in zip(self.diagram_names, image_sources):
            self.assertEqual(svg, app.session_state[f"adder_svg_{name}"]["data"])
        self.assertEqual(len(image_sources), 6)
        # The block overview precedes the complete netlist; the XOR circuit is last.
        for name, body in zip(self.diagram_names, (body for body in self.html(app) if "<img " in body)):
            svg = app.session_state[f"adder_svg_{name}"]["data"]
            width, _ = svg_size_px(svg)
            self.assertIn(f"width:{width * 0.5:.2f}px;max-width:100%;height:auto;", body)
        headings = [header.value for header in app.header]
        self.assertEqual(headings[-1], "5. Simplify with XOR")

    def test_every_switch_copy_updates_all_one_bit_consumers_immediately(self):
        app = self.app()
        expected = {"A": True, "B": True, "Cin": False}
        four_bit_images = {name: dict(app.session_state[f"adder_svg_{name}"])
                           for name in self.diagram_names[3:]}
        four_bit_metrics = {label: self.metrics(app)[label]
                            for label in ("Sum (4 bits)", "Carry C4", "Full result (5 bits)")}
        for group in self.switch_groups:
            for bit in self.input_names:
                with self.subTest(group=group, bit=bit):
                    expected[bit] = not expected[bit]
                    app.toggle(key=self.switch_key(group, bit)).set_value(expected[bit]).run()
                    self.assert_one_bit_state(app, expected)
                    self.assertEqual(app.text_input(key="adder_operand_a").value, "0101")
                    self.assertEqual(app.text_input(key="adder_operand_b").value, "0011")
                    for label, value in four_bit_metrics.items():
                        self.assertEqual(self.metrics(app)[label], value)
                    for name, image in four_bit_images.items():
                        self.assertEqual(app.session_state[f"adder_svg_{name}"], image)

    def test_synced_inputs_survive_reruns_and_widget_cleanup(self):
        app = AppTest.from_string(
            "import streamlit as st\n"
            "from tools.logic_adder_lesson import render\n"
            "if st.checkbox('Show lesson', value=True, key='show_lesson'):\n"
            "    render()\n", default_timeout=30,
        ).run()
        app.toggle(key=self.switch_key("carry_circuit", "B")).set_value(False).run()
        app.toggle(key=self.switch_key("full_adder", "Cin")).set_value(True).run()
        expected = {"A": True, "B": False, "Cin": True}
        self.assert_one_bit_state(app, expected)
        app.run()
        self.assert_one_bit_state(app, expected)
        app.checkbox(key="show_lesson").set_value(False).run()
        self.clean(app)
        self.assertEqual(len(app.toggle), 0)
        self.assertEqual(app.session_state["adder_one_bit_inputs"], expected)
        app.checkbox(key="show_lesson").set_value(True).run()
        self.assert_one_bit_state(app, expected)

    def test_zero_output_still_selects_rows_and_maps_and_keeps_operands_independent(self):
        app = self.app()
        old_images = {name: app.session_state[f"adder_svg_{name}"]["data"]
                      for name in self.diagram_names}
        app.toggle(key="adder_input_A").set_value(False)
        app.toggle(key="adder_input_B").set_value(False)
        app.run()
        self.clean(app)
        self.assertEqual(self.metrics(app)["S"], "0")
        self.assertEqual(self.metrics(app)["Cout"], "0")
        self.assertEqual(self.metrics(app)["Sum (4 bits)"], "1000")
        for name in ("S", "Cout"):
            body = self.table(app, f"{name} truth table")
            first_row = re.findall(r"<tr[^>]*>(.*?)</tr>", body, flags=re.S)[1]
            self.assertEqual(re.findall(r"<td>(.*?)</td>", first_row), ["0", "0", "0", "0", "Active"])
        maps = [body for body in self.html(app) if "logic-kmap-display" in body]
        for body in maps:
            self.assertIn("data-active-minterm='0'", body)
            self.assertIn("Selected input: minterm 0, output 0", body)
        for name in ("sum", "carry", "full_adder"):
            self.assertNotEqual(app.session_state[f"adder_svg_{name}"]["data"], old_images[name])
        for name in ("four_bit_blocks", "four_bit", "four_bit_xor"):
            self.assertEqual(app.session_state[f"adder_svg_{name}"]["data"], old_images[name])

    def test_bit_order_overflow_and_each_carry(self):
        app = self.app()
        full_image = app.session_state["adder_svg_full_adder"]["data"]
        for a, b, summed, carry, complete in (
            ("0001", "0000", "0001", "0", "00001"),
            ("1000", "0000", "1000", "0", "01000"),
            ("1111", "0001", "0000", "1", "10000"),
            ("1111", "1111", "1110", "1", "11110"),
        ):
            with self.subTest(a=a, b=b):
                self.set_operands(app, a, b)
                metrics = self.metrics(app)
                self.assertEqual(metrics["Sum (4 bits)"], summed)
                self.assertEqual(metrics["Carry C4"], carry)
                self.assertEqual(metrics["Full result (5 bits)"], complete)
                for name in ("four_bit_blocks", "four_bit", "four_bit_xor"):
                    svg = app.session_state[f"adder_svg_{name}"]["data"].decode()
                    self.assertEqual(app.session_state[f"adder_svg_{name}"]["signature"], (a, b))
                    for i in range(4):
                        self.assertIn(f"S{i}={summed[-1-i]}", svg)
                        self.assertIn(f"A{i}={a[-1-i]}", svg)
                        self.assertIn(f"B{i}={b[-1-i]}", svg)
                    self.assertIn(f"C4={carry}", svg)
                table = self.table(app, "Four-bit carry propagation")
                rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, flags=re.S)[1:]
                prior_carry = 0
                for i, row in enumerate(rows):
                    bits = [int(value) for value in re.findall(r"<td>(.*?)</td>", row)]
                    expected_a, expected_b = int(a[-1-i]), int(b[-1-i])
                    total = expected_a + expected_b + prior_carry
                    self.assertEqual(bits, [i, expected_a, expected_b, prior_carry, total % 2, total // 2])
                    prior_carry = total // 2
                self.assertEqual(len(rows), 4)
        self.assertEqual(app.session_state["adder_svg_full_adder"]["data"], full_image)
        self.assert_one_bit_state(app, {"A": True, "B": True, "Cin": False})

    def test_invalid_operands_hide_all_four_bit_results_then_recover(self):
        app = self.app()
        for invalid in ("", "111", "11111", "10x0", "1 01"):
            with self.subTest(invalid=invalid):
                self.set_operands(app, invalid, "0001")
                self.assertEqual(len(app.error), 1)
                self.assertEqual(set(self.metrics(app)), {"S", "Cout"})
                self.assertEqual(len(app.get("download_button")), 3)
                self.assertFalse(any("Four-bit carry propagation" in body for body in self.html(app)))
                self.assertFalse(any("Four-bit ripple-carry circuit;" in body for body in self.html(app)))
                self.assertFalse(any("Four-bit full-adder block overview;" in body for body in self.html(app)))
                self.assertFalse(any("Simplified four-bit XOR/AND/OR circuit;" in body for body in self.html(app)))
                self.assertEqual(len(app.toggle), 15)
        self.set_operands(app, " 0001 ", "\t0010\t")
        self.assertEqual(len(app.error), 0)
        self.assertEqual(self.metrics(app)["Sum (4 bits)"], "0011")
        self.assertEqual(self.metrics(app)["Full result (5 bits)"], "00011")
        self.assertEqual(len(app.get("download_button")), 6)

    def test_kmap_options_keep_the_existing_default_and_validate_selection(self):
        result = build_full_adder().sum_result
        model = build_maps(3, list(result.var_order))
        values = {m: str(int(m in result.ones)) for m in range(8)}
        legacy = render_kmap_html(model, values, result.cover)
        self.assertIn("BC<br>00", legacy)
        self.assertIn("A - 0", legacy)
        self.assertNotIn("data-active-minterm=", legacy)
        lesson = render_kmap_html(model, values, result.cover, input_labels={"C": "Cin"},
                                  compact_headers=True, active_minterm=0)
        self.assertEqual(lesson.count("(B,Cin)"), 1)
        self.assertNotIn("BC<br>", lesson)
        self.assertIn("Selected input: minterm 0, output 0", lesson)
        self.assertIn(".logic-kmap-display .cell", lesson)
        with self.assertRaises(ValueError):
            render_kmap_html(model, values, result.cover, active_minterm=8)


if __name__ == "__main__":
    unittest.main()
