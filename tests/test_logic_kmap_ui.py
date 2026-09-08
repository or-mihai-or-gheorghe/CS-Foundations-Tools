"""Behavioral coverage for the K-map result and circuit simulator lifecycle."""

import base64
import re
import unittest

from streamlit.testing.v1 import AppTest


class KmapCircuitUI(unittest.TestCase):
    def app(self):
        app = AppTest.from_string(
            "from tools.logic_kmap_sop import render\nrender()\n", default_timeout=20
        ).run()
        self.clean(app)
        return app

    def clean(self, app):
        self.assertEqual(len(app.exception), 0, [error.message for error in app.exception])

    def snapshot(self, app):
        return app.session_state["kmap_result"]

    def minimize_expression(self, app, expression):
        app.text_input(key="kmap_expression").set_value(expression)
        app.button(key="kmap_minimize_expression").click().run()
        self.clean(app)
        return self.snapshot(app)

    def set_input(self, app, variable, value, run=True):
        generation = self.snapshot(app)["generation"]
        app.toggle(key=f"kmap_sim_{generation}_{variable}").set_value(bool(value))
        if run:
            app.run()
            self.clean(app)

    def no_result(self, app):
        self.clean(app)
        self.assertEqual(len(app.success), 0)
        self.assertEqual(len(app.toggle), 0)
        self.assertEqual(len(app.metric), 0)
        self.assertEqual(len(app.get("download_button")), 0)
        self.assertNotIn("kmap_result", app.session_state)

    def table(self, app, nvars, minterms, dont_cares="", order="ABCDE"):
        app.radio(key="kmap_input_mode").set_value("Truth Table").run()
        app.selectbox(key="kmap_nvars").select(nvars)
        app.text_input(key="kmap_variable_order").set_value(order)
        app.text_area(key="kmap_minterms").set_value(minterms)
        app.text_area(key="kmap_dont_cares").set_value(dont_cares)
        app.button(key="kmap_minimize_truth_table").click().run()
        self.clean(app)

    def test_simulation_updates_the_display_and_export_source(self):
        app = self.app()
        snapshot = self.minimize_expression(app, "A'B + C")
        generation = snapshot["generation"]
        svg_zero = snapshot["svg_bytes"]
        self.assertEqual(app.metric[0].value, "0")
        for variable, value, expected in (("C", 1, "1"), ("C", 0, "0"),
                                           ("B", 1, "1"), ("A", 1, "0")):
            self.set_input(app, variable, value)
            self.assertEqual(app.metric[0].value, expected)
            current = self.snapshot(app)
            self.assertEqual(current["generation"], generation)
            body = app.get("html")[0].proto.body
            encoded = re.search(r"base64,([^\"]+)", body).group(1)
            self.assertEqual(base64.b64decode(encoded), current["svg_bytes"])
            self.assertEqual(len(app.get("download_button")), 1)
        self.assertNotEqual(self.snapshot(app)["svg_bytes"], svg_zero)
        svg_current = self.snapshot(app)["svg_bytes"]
        app.slider(key=f"kmap_zoom_{generation}").set_value(200).run()
        self.clean(app)
        self.assertEqual(app.metric[0].value, "0")
        self.assertEqual(self.snapshot(app)["svg_bytes"], svg_current)
        self.assertEqual(self.snapshot(app)["generation"], generation)

    def test_edit_revert_and_invalid_minimization_remove_old_results(self):
        app = self.app()
        self.minimize_expression(app, "A AND B")
        app.text_input(key="kmap_expression").set_value("A OR B").run()
        self.no_result(app)
        app.text_input(key="kmap_expression").set_value("A AND B").run()
        self.no_result(app)
        self.minimize_expression(app, "A AND B")
        app.text_input(key="kmap_expression").set_value("A + F")
        app.button(key="kmap_minimize_expression").click().run()
        self.no_result(app)
        self.assertEqual(len(app.error), 1)

    def test_new_minimization_resets_inputs_and_zoom(self):
        app = self.app()
        generation = self.minimize_expression(app, "A + B")["generation"]
        self.set_input(app, "A", 1)
        app.slider(key=f"kmap_zoom_{generation}").set_value(200).run()
        self.assertEqual(app.metric[0].value, "1")
        snapshot = self.minimize_expression(app, "A + B")
        self.assertGreater(snapshot["generation"], generation)
        self.assertTrue(all(not toggle.value for toggle in app.toggle))
        self.assertEqual(app.slider[0].value, 100)
        self.assertEqual(app.metric[0].value, "0")

    def test_custom_order_unused_inputs_and_dont_care(self):
        app = self.app()
        self.table(app, 2, "2,3", order="ba")
        self.assertEqual(self.snapshot(app)["minimization"].sop, "B")
        self.assertEqual(self.snapshot(app)["circuit"].var_order, ("B", "A"))
        self.set_input(app, "A", 1)
        self.assertEqual(app.metric[0].value, "0")
        self.set_input(app, "B", 1)
        self.assertEqual(app.metric[0].value, "1")
        app.text_area(key="kmap_dont_cares").set_value("1").run()
        self.no_result(app)
        app.button(key="kmap_minimize_truth_table").click().run()
        self.clean(app)
        self.set_input(app, "A", 1)
        self.assertEqual(app.metric[0].value, "0")
        captions = "\n".join(item.value for item in app.caption)
        self.assertIn("Minterm: 1", captions)
        self.assertIn("X (don't-care)", captions)

    def test_mode_dimension_and_invalid_order_invalidate_result(self):
        app = self.app()
        self.minimize_expression(app, "A + B")
        app.radio(key="kmap_input_mode").set_value("Truth Table").run()
        self.no_result(app)
        self.table(app, 2, "2,3", order="AB")
        app.selectbox(key="kmap_nvars").select(3).run()
        self.no_result(app)
        app.text_input(key="kmap_variable_order").set_value("AaB")
        app.button(key="kmap_minimize_truth_table").click().run()
        self.no_result(app)
        self.assertEqual(len(app.error), 1)

    def test_constant_circuits_and_all_dont_cares(self):
        app = self.app()
        for minterms, dont_cares, expected in (("", "0,1", "0"), ("0", "1", "1")):
            with self.subTest(expected=expected):
                self.table(app, 1, minterms, dont_cares)
                self.assertEqual(app.metric[0].value, expected)
                self.assertEqual(self.snapshot(app)["minimization"].sop, expected)
                self.set_input(app, "A", 1)
                self.assertEqual(app.metric[0].value, expected)
                self.assertEqual(len(app.get("download_button")), 1)

    def test_five_variable_regression_in_ui(self):
        app = self.app()
        self.table(app, 5, "1,2,3,6")
        for minterm in (0, 1, 4, 5, 6, 7):
            with self.subTest(minterm=minterm):
                for index, variable in enumerate("ABCDE"):
                    self.set_input(app, variable, (minterm >> (4 - index)) & 1, run=False)
                app.run()
                self.clean(app)
                self.assertEqual(app.metric[0].value, str(int(minterm in {1, 2, 3, 6})))


if __name__ == "__main__":
    unittest.main()
