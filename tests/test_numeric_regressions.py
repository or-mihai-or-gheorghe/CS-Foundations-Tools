"""Focused regressions for KI-001 (initial carry), KI-004 through KI-008.

Run from the repository root with:
    python -B -m unittest discover -s tests -p 'test_numeric_regressions.py' -v
"""

from decimal import getcontext, localcontext, setcontext
from fractions import Fraction
from itertools import product
import re
import unittest

from streamlit.testing.v1 import AppTest
from tools import bcd_arithmetic as bcd
from tools import decimal_to_binary as decbin
from tools import fp_arithmetic as fp
from tools import logic_kmap_sop as kmap
from tools import raw_binary_arithmetic as raw
from tools import twos_complement_arithmetic as tc


def binary_value(text):
    """Read the displayed binary value independently of production helpers."""
    text = ''.join(text.split())
    sign = -1 if text.startswith('-') else 1
    text = text.lstrip('+-')
    integer, _, fraction = text.partition('.')
    return sign * (Fraction(int(integer, 2)) +
                   Fraction(int(fraction or '0', 2), 2 ** len(fraction)))


def rounded_value(text, places, rounding):
    original = Fraction(text)
    scaled = abs(original) * 2 ** places
    integer, remainder = divmod(scaled.numerator, scaled.denominator)
    if rounding == 'nearest-even':
        twice_remainder = 2 * remainder
        if (twice_remainder > scaled.denominator or
                (twice_remainder == scaled.denominator and integer % 2)):
            integer += 1
    return (-1 if original < 0 else 1) * Fraction(integer, 2 ** places)


def context_state():
    context = getcontext()
    return (context.prec, context.rounding, context.Emin, context.Emax,
            context.capitals, context.clamp, dict(context.flags), dict(context.traps))


class NumericRegressions(unittest.TestCase):
    def setUp(self):
        # Module imports change Decimal precision; no test may depend on their order.
        self.addCleanup(setcontext, getcontext().copy())

    def test_fp_initial_carry_vectors(self):
        # Fixed expected encodings, independently checked with exact rational sums.
        # Subnormal and final-rounding-carry defects remain outside this fix.
        vectors = [
            ('Single (32-bit)', '3F800000', '3F800000', '40000000'),
            ('Single (32-bit)', 'BFC00000', 'BFC00000', 'C0400000'),
            ('Single (32-bit)', '3FFC0000', '3D000021', '40000001'),
            ('Single (32-bit)', '7F7FFFFF', '7F7FFFFF', '7F800000'),
            ('Single (32-bit)', 'FF7FFFFF', 'FF7FFFFF', 'FF800000'),
            ('Single (32-bit)', '3F800000', '3F000000', '3FC00000'),
            ('Single (32-bit)', '3F800000', 'BF800000', '00000000'),
            ('Double (64-bit)', '3FF0000000000000', '3FF0000000000000', '4000000000000000'),
            ('Double (64-bit)', 'BFF8000000000000', 'BFF8000000000000', 'C008000000000000'),
            ('Double (64-bit)', '3FFF800000000000', '3FA0000000000021', '4000000000000001'),
            ('Double (64-bit)', '7FEFFFFFFFFFFFFF', '7FEFFFFFFFFFFFFF', '7FF0000000000000'),
            ('Double (64-bit)', 'FFEFFFFFFFFFFFFF', 'FFEFFFFFFFFFFFFF', 'FFF0000000000000'),
            ('Double (64-bit)', '3FF0000000000000', '3FE0000000000000', '3FF8000000000000'),
            ('Double (64-bit)', '3FF0000000000000', 'BFF0000000000000', '0000000000000000'),
        ]
        for precision, left, right, expected in vectors:
            width = len(expected) * 4
            for input_format in ('Hexadecimal', 'Binary'):
                with self.subTest(precision=precision, left=left, right=right, format=input_format):
                    a, b = left, right
                    if input_format == 'Binary':
                        a, b = (format(int(value, 16), f'0{width}b') for value in (a, b))
                    result, _ = fp.perform_fp_addition(a, b, precision, input_format)
                    self.assertIsNotNone(result)
                    bits = ''.join(result)
                    self.assertEqual(len(bits), width)
                    self.assertEqual(f'{int(bits, 2):0{len(expected)}X}', expected)

    def test_subtraction_exhaustive_small_widths(self):
        for width in range(2, 6):
            lo, hi = -(2 ** (width - 1)), 2 ** (width - 1) - 1
            mask = 2 ** width - 1
            for a, b in product(range(lo, hi + 1), repeat=2):
                with self.subTest(width=width, a=a, b=b):
                    a_bits, b_bits = (format(value & mask, f'0{width}b') for value in (a, b))
                    result, _ = tc._sub_tc_core(a_bits, b_bits, width)
                    exact = a - b
                    wrapped = (exact - lo) % (2 ** width) + lo
                    self.assertEqual(result['result_bits'], format(exact & mask, f'0{width}b'))
                    self.assertEqual(int(result['result_value']), wrapped)
                    self.assertEqual(result['overflow'], not lo <= exact <= hi)
                    kind = ('positive overflow' if exact > hi else
                            'negative overflow (underflow)' if exact < lo else '')
                    self.assertEqual(result['overflow_kind'], kind)

    def test_subtraction_boundary_explanations(self):
        for width in (8, 16, 32):
            lo, hi = -(2 ** (width - 1)), 2 ** (width - 1) - 1
            for a, b, overflow in ((0, lo, True), (lo, lo, False), (hi, -1, True), (lo, 1, True)):
                with self.subTest(width=width, a=a, b=b):
                    result, steps = tc._sub_tc_core(str(a), str(b), width)
                    self.assertEqual(result['overflow'], overflow)
                    explanation = '\n'.join(steps)
                    self.assertIn('Subtraction overflow rule', explanation)
                    self.assertNotIn('when adding two numbers', explanation)
                    if overflow:
                        self.assertIn(f'{a} - ({b}) = {a - b}', explanation)
                        self.assertIn('Wrapped', explanation)
                    if b == lo:
                        self.assertRegex(explanation, r'not representable|cannot be represented')
            conversion = tc._conversion_block('B', lo, width)
            self.assertIn('0' + '1' * (width - 1), conversion)
            self.assertNotIn('MSB=1 & NEG others', conversion)

    def test_direct_addition_overflow_is_preserved(self):
        for a, b, value, overflow in (('127', '1', -128, True), ('-128', '-1', 127, True), ('-5', '12', 7, False)):
            with self.subTest(a=a, b=b):
                result, steps = tc._add_tc_core(a, b, 8)
                self.assertEqual(int(result['result_value']), value)
                self.assertEqual(result['overflow'], overflow)
                self.assertIn('when adding two numbers', '\n'.join(steps))

    def test_division_matches_integer_arithmetic(self):
        for a, b in product(range(64), range(1, 64)):
            with self.subTest(a=a, b=b):
                result, _ = raw._divide_binary_core(format(a, 'b'), format(b, 'b'))
                self.assertEqual((int(result['quotient'], 2), int(result['remainder'], 2)), divmod(a, b))

    def test_division_zero_quotient_layout_and_zero_divisor(self):
        for a, b in (('0', '1'), ('1', '10')):
            with self.subTest(a=a, b=b):
                result, steps = raw._divide_binary_core(a, b)
                self.assertEqual(result, {'quotient': '0', 'remainder': a})
                layout = next(step for step in steps if 'Long division (dividend' in step)
                self.assertIn(f'{a} | {b}', layout)
                self.assertIn('| 0', layout)
        result, steps = raw._divide_binary_core('1', '0')
        self.assertIsNone(result)
        self.assertIn('Division by zero', steps[0])

    def test_kmap_aliases_and_precedence(self):
        both = lambda e: e['A'] and e['B']
        either = lambda e: e['A'] or e['B']
        cases = [(expr, 'AB', both) for expr in ('A AND B', 'a aNd b', 'A.B', 'AxB', 'AXB', 'A*B', 'A·B', 'AB', 'A_B')]
        cases += [(expr, 'AB', either) for expr in ('A OR B', 'a or b', 'A+B', 'A U B', 'A V B', 'A|B')]
        cases += [(expr, 'A', lambda e: not e['A']) for expr in ('NOT A', 'NOT(A)', '!A', '~A', '¬A', "A'", 'N_O_T(A)')]
        cases += [
            ('A OR B AND C', 'ABC', lambda e: e['A'] or (e['B'] and e['C'])),
            ('NOT A AND B OR C', 'ABC', lambda e: ((not e['A']) and e['B']) or e['C']),
            ('A AND NOT B', 'AB', lambda e: e['A'] and not e['B']),
            ('NOT NOT A', 'A', lambda e: e['A']),
            ("A''", 'A', lambda e: e['A']),
            ("(AB)'", 'AB', lambda e: not (e['A'] and e['B'])),
            ("(A+B)'C", 'ABC', lambda e: not (e['A'] or e['B']) and e['C']),
            ('A + N O T(B)', 'AB', lambda e: e['A'] or not e['B']),
            ('A+0', 'A', lambda e: e['A']),
            ('A*1', 'A', lambda e: e['A']),
            ('A+1', 'A', lambda e: True),
            ('A*0', 'A', lambda e: False),
            ('A + B·C', 'ABC', lambda e: e['A'] or (e['B'] and e['C'])),
            ("A'B + C(D + E')", 'ABCDE', lambda e: (not e['A'] and e['B']) or (e['C'] and (e['D'] or not e['E']))),
            ("a b' + !c", 'ABC', lambda e: (e['A'] and not e['B']) or not e['C']),
            ("(A + B)(C' + D)", 'ABCD', lambda e: (e['A'] or e['B']) and (not e['C'] or e['D'])),
        ]
        for expression, variables, reference in cases:
            with self.subTest(expression=expression):
                expected = set()
                for index, bits in enumerate(product((False, True), repeat=len(variables))):
                    if reference(dict(zip(variables, bits))):
                        expected.add(index)
                _, used = kmap._norm_expr(expression)
                self.assertEqual(used, list(variables))
                self.assertEqual(kmap._eval_expr_to_minterms(expression, list(variables)), expected)

    def test_kmap_rejects_invalid_expressions(self):
        for expression in ('', 'A AND', 'AND A', 'A OR OR B', 'NOT', 'A + F', '(A+B', 'A)', 'A AND (B OR)',
                           'A XOR B', 'A_AND_B', 'NOTA', 'A == B', 'A < B', 'A#B', 'A+2', 'A+11', "'' OR A"):
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    kmap._norm_expr(expression)
        for expression in kmap.EXAMPLES:
            _, variables = kmap._norm_expr(expression)
            kmap._eval_expr_to_minterms(expression, variables)

    def assert_decimal_conversion(self, text, places, mode):
        before = context_state()
        result, steps = decbin._decimal_to_binary_core(text, places, mode)
        self.assertEqual(context_state(), before)
        self.assertIsNotNone(result)
        expected = rounded_value(text, places, mode)
        self.assertEqual(binary_value(result['bin_string']), expected)
        self.assertEqual(binary_value(result['grouped']), expected)
        self.assertEqual(Fraction(result['decimal_back']), expected)
        self.assertEqual(result['sign'], '-' if text.startswith('-') else '+')
        self.assertEqual(len(result['frac_bits']), places)
        self.assertEqual(result['requested_frac_bits'], places)
        self.assertEqual(result['rounding'], mode)
        for before_value, after, bit, remainder in re.findall(
                r'Step \d+: (\S+) × 2 = (\S+) ⇒ take ([01]); remainder (\S+)', '\n'.join(steps)):
            self.assertEqual(Fraction(after), 2 * Fraction(before_value))
            self.assertEqual(Fraction(remainder), Fraction(after) - int(bit))
            self.assertTrue(0 <= Fraction(remainder) < 1)

    def test_decimal_rounding_and_all_representations(self):
        cases = [('0.5001', 0), ('0.25001', 1), ('0.5', 0), ('1.5', 0), ('0.25', 1), ('0.75', 1),
                 ('0.4999', 0), ('0.125', 3), ('0.99999', 4), ('0.1', 16), ('0.1', 64), ('0', 0), ('0', 64)]
        for precision, mode, (text, places), sign in product((3, 28, 100, 200), ('nearest-even', 'truncate'), cases, ('', '-')):
            with self.subTest(precision=precision, mode=mode, text=sign + text, places=places):
                with localcontext() as context:
                    context.prec = precision
                    self.assert_decimal_conversion(sign + text, places, mode)

    def test_decimal_reconstruction_and_distant_remainder(self):
        cases = [('-1234', 0), ('1' + '0' * 120 + '.5001', 1), ('0.5' + '0' * 220 + '1', 0)]
        for precision, (text, places), mode in product((3, 28, 100, 200), cases, ('nearest-even', 'truncate')):
            with self.subTest(precision=precision, text=text, mode=mode):
                with localcontext() as context:
                    context.prec = precision
                    self.assert_decimal_conversion(text, places, mode)

    def test_bcd_formats_and_arithmetic(self):
        self.assertEqual(bcd._parse_bcd_operand('1001')[2], 1001)
        self.assertEqual(bcd._parse_bcd_operand('1001', 'BCD')[2], 9)
        for text in ('0001 0010', '0001_0010', '00010010'):
            self.assertEqual(bcd._parse_bcd_operand(text, 'BCD')[2], 12)
        vectors = [
            (bcd._bcd_add_core, '0010', '3', 'Decimal', 'Decimal', 13),
            (bcd._bcd_add_core, '0010', '3', 'BCD', 'Decimal', 5),
            (bcd._bcd_add_core, '0001 0010', '3', 'BCD', 'Decimal', 15),
            (bcd._bcd_sub_core, '0001 0010', '3', 'BCD', 'Decimal', 9),
            (bcd._bcd_sub_core, '3', '0001 0010', 'Decimal', 'BCD', -9),
            (bcd._bcd_add_core, '1001', '0001', 'BCD', 'BCD', 10),
            (bcd._bcd_sub_core, '0001 0000 0000', '0001', 'BCD', 'BCD', 99),
        ]
        for operation, a, b, a_format, b_format, expected in vectors:
            with self.subTest(operation=operation.__name__, a=a, b=b, a_format=a_format, b_format=b_format):
                result, _ = operation(a, b, a_format=a_format, b_format=b_format)
                self.assertEqual(result['result_decimal'], expected)
                bits = result['result_bits'].replace(' ', '').lstrip('-')
                self.assertEqual(len(bits) % 4, 0)
                digits = [int(bits[i:i + 4], 2) for i in range(0, len(bits), 4)]
                self.assertTrue(all(digit < 10 for digit in digits))
                self.assertEqual(int(''.join(map(str, digits))), abs(expected))
        # Existing two-argument calls retain decimal semantics.
        result, _ = bcd._bcd_add_core('1234', '567')
        self.assertEqual(result['result_decimal'], 1801)

    def test_bcd_invalid_inputs(self):
        for text, input_format in (('', 'Decimal'), ('-1', 'Decimal'), ('1.5', 'Decimal'), ('abc', 'Decimal'),
                                   ('1010', 'BCD'), ('1111', 'BCD'), ('010', 'BCD'), ('0012', 'BCD'),
                                   ('-0001', 'BCD'), ('0001', 'Hexadecimal')):
            with self.subTest(text=text, format=input_format):
                *values, error = bcd._parse_bcd_operand(text, input_format)
                self.assertIsNotNone(error)
                self.assertEqual(values, [None, None, None])
        for operation in (bcd._bcd_add_core, bcd._bcd_sub_core):
            result, _ = operation('3', '1010', b_format='BCD')
            self.assertIn('error', result)


class NumericUIRegressions(unittest.TestCase):
    def app(self, module, precision=None):
        script = f'from tools.{module} import render\n'
        if precision is not None:
            # AppTest runs in a separate thread; configure its context after imports.
            script += ('from decimal import localcontext\n'
                       f'with localcontext() as context:\n    context.prec = {precision}\n    render()\n')
        else:
            script += 'render()\n'
        app = AppTest.from_string(script, default_timeout=10).run()
        self.assert_clean(app)
        return app

    def assert_clean(self, app):
        self.assertEqual(len(app.exception), 0, [item.message for item in app.exception])

    def displayed(self, app):
        return '\n'.join(str(item.value) for kind in ('markdown', 'code', 'success', 'info', 'warning', 'error')
                         for item in app.get(kind))

    def test_fp_addition_ui(self):
        app = self.app('fp_arithmetic')
        app.text_input[0].set_value('1.0')
        app.text_input[1].set_value('1.0')
        app.button(key='calculate_arith').click().run()
        self.assert_clean(app)
        self.assertIn('0x40000000', self.displayed(app))
        self.assertIn('**Decimal Value:** `2.0`', self.displayed(app))

    def test_subtraction_ui(self):
        app = self.app('twos_complement_arithmetic')
        app.selectbox[0].select(8)
        app.radio[0].set_value('Subtraction')
        app.text_input[0].set_value('0')
        app.text_input[1].set_value('-128')
        app.button(key='calc_twos_signed').click().run()
        self.assert_clean(app)
        self.assertEqual(len(app.warning), 1)
        self.assertIn('Exact result', self.displayed(app))
        app.text_input[0].set_value('-128')
        app.button(key='calc_twos_signed').click().run()
        self.assert_clean(app)
        self.assertEqual(len(app.warning), 0)
        self.assertIn('**Value:** `0`', self.displayed(app))

    def test_division_ui(self):
        app = self.app('raw_binary_arithmetic')
        app.radio(key='binary_op').set_value('Division')
        for a, b, remainder in (('0', '1', '0'), ('1', '10', '1')):
            app.text_input[0].set_value(a)
            app.text_input[1].set_value(b)
            app.button(key='calc_binary_raw').click().run()
            self.assert_clean(app)
            self.assertIn('**Quotient:** `0`', self.displayed(app))
            self.assertIn(f'**Remainder:** `{remainder}`', self.displayed(app))
        app.text_input[1].set_value('0')
        app.button(key='calc_binary_raw').click().run()
        self.assert_clean(app)
        self.assertIn('Division by zero', app.error[0].value)
        self.assertEqual(len(app.success), 0)

    def test_kmap_ui_valid_and_invalid(self):
        app = self.app('logic_kmap_sop')
        app.text_input[0].set_value('A AND B')
        app.button(key='kmap_minimize_expression').click().run()
        self.assert_clean(app)
        self.assertEqual(len(app.error), 0)
        self.assertIn('A·B', self.displayed(app))
        for expression in ('A AND', 'A + F', 'A#B', '0', '1'):
            app.text_input[0].set_value(expression)
            app.button(key='kmap_minimize_expression').click().run()
            self.assert_clean(app)
            self.assertEqual(len(app.error), 1)
            self.assertEqual(len(app.success), 0)
            self.assertEqual(len(app.toggle), 0)
            self.assertEqual(len(app.get('download_button')), 0)

    def test_decimal_ui_default_and_small_context(self):
        for precision in (None, 3):
            with self.subTest(precision=precision):
                app = self.app('decimal_to_binary', precision=precision)
                app.text_input[0].set_value('0.1')
                app.slider(key='dec2bin_frac_bits').set_value(16)
                app.button(key='dec2bin').click().run()
                self.assert_clean(app)
                self.assertIn('`0.100006103515625`', self.displayed(app))
                app.text_input[0].set_value('0.5001').run()
                app.slider(key='dec2bin_frac_bits').set_value(0)
                app.button(key='dec2bin').click().run()
                self.assert_clean(app)
                self.assertIn('**Binary (raw):** `1`', self.displayed(app))

    def test_bcd_ui_format_changes_preserve_text(self):
        app = self.app('bcd_arithmetic')
        self.assertEqual(app.selectbox(key='bcd_format_a').value, 'Decimal')
        self.assertEqual(app.selectbox(key='bcd_format_b').value, 'Decimal')
        app.text_input(key='bcd_operand_a').set_value('0010')
        app.text_input(key='bcd_operand_b').set_value('3')
        app.button(key='calc_bcd').click().run()
        self.assert_clean(app)
        self.assertIn('**Decimal:** `13`', self.displayed(app))
        app.selectbox(key='bcd_format_a').select('BCD').run()
        self.assert_clean(app)
        self.assertEqual(app.text_input(key='bcd_operand_a').value, '0010')
        self.assertEqual(app.text_input(key='bcd_operand_b').value, '3')
        app.button(key='calc_bcd').click().run()
        self.assert_clean(app)
        self.assertIn('**Decimal:** `5`', self.displayed(app))
        app.text_input(key='bcd_operand_a').set_value('0001 0010')
        app.button(key='calc_bcd').click().run()
        self.assert_clean(app)
        self.assertIn('**Decimal:** `15`', self.displayed(app))
        app.radio[0].set_value('Subtraction')
        app.button(key='calc_bcd').click().run()
        self.assert_clean(app)
        self.assertIn('**Decimal:** `9`', self.displayed(app))
        app.selectbox(key='bcd_format_b').select('BCD')
        app.text_input(key='bcd_operand_b').set_value('1010')
        app.button(key='calc_bcd').click().run()
        self.assert_clean(app)
        self.assertEqual(len(app.error), 1)
        self.assertEqual(len(app.success), 0)
        app.selectbox(key='bcd_format_b').select('Decimal').run()
        self.assert_clean(app)
        self.assertEqual(app.text_input(key='bcd_operand_b').value, '1010')
        app.button(key='calc_bcd').click().run()
        self.assert_clean(app)
        self.assertEqual(len(app.error), 0)
        self.assertIn('**Decimal:** `-998`', self.displayed(app))


if __name__ == '__main__':
    unittest.main()
