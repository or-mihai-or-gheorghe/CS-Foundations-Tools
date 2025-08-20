# tools/twos_complement_arithmetic.py
from __future__ import annotations

import streamlit as st
from typing import Tuple, List, Optional, Dict

# ============================================================
# Helpers
# ============================================================

def _bit_range(width: int) -> Tuple[int, int]:
    """Signed range for a given two's-complement width."""
    return (-(1 << (width - 1)), (1 << (width - 1)) - 1)

def _int_to_twos_bits(value: int, width: int) -> str:
    """Convert a signed int to two's-complement bit string of length 'width'."""
    mask = (1 << width) - 1
    return format(value & mask, f"0{width}b")

def _twos_bits_to_int(bits: str) -> int:
    """Interpret 'bits' as a two's-complement number and return the signed int."""
    width = len(bits)
    val = int(bits, 2)
    if bits[0] == '1':
        val -= (1 << width)
    return val

def _clean(s: str) -> str:
    return s.strip().replace("_", "").replace(" ", "").lower()

def _parse_operand(value_str: str, width: int) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Parse an operand which may be decimal, hex (0x), binary (0b), or raw bits.
    Returns (signed_int_value, normalized_bits, error_message).
    """
    s = _clean(value_str)
    if not s:
        return None, None, "Input cannot be empty."

    signed = 1
    if s.startswith("-"):
        signed = -1
        s = s[1:]

    val: Optional[int] = None

    try:
        if s.startswith("0b"):
            val = int(s[2:], 2) * signed
        elif s.startswith("0x"):
            val = int(s[2:], 16) * signed
        elif all(c in "01" for c in s):
            # Raw bits -> interpret as non-negative magnitude, then apply sign if present.
            # If the user gives full width of bits without a leading '-', assume they meant the exact encoding.
            if signed == 1 and len(s) == width:
                # Interpret directly as two's-complement encoding of length 'width'.
                val = _twos_bits_to_int(s)
            else:
                # Otherwise treat as magnitude and apply sign.
                val = int(s, 2) * signed
        else:
            # Decimal
            val = int(s, 10) * signed
    except ValueError:
        return None, None, "Could not parse the number. Use decimal, 0x.., 0b.., or raw bits."

    lo, hi = _bit_range(width)
    if val < lo or val > hi:
        return None, None, f"Value {val} is out of the {width}-bit two's-complement range [{lo}, {hi}]."

    return val, _int_to_twos_bits(val, width), None

def _invert_bits(bits: str) -> str:
    return "".join('1' if b == '0' else '0' for b in bits)

def _conversion_block(label: str, value: int, width: int) -> str:
    """Build a compact code block that explains how a signed value becomes two's-complement bits."""
    abs_val = abs(value)
    mag = format(abs_val, f"0{width}b")
    if value >= 0:
        lines = [
            f"{label} two’s-complement ({width}-bit):",
            "",
            f"abs({label}) = {abs_val}",
            f"Pad to {width} bits: {mag}",
            "Original is ≥ 0 → keep as-is:",
            f"{label} bits: " + mag,
        ]
    else:
        # 'Set MSB to 1, negate other bits, add 1'
        neg_others = '1' + ''.join('1' if b == '0' else '0' for b in mag[1:])
        tc = _int_to_twos_bits(value, width)
        lines = [
            f"{label} two’s-complement ({width}-bit):",
            "",
            f"abs({label}) = {abs_val}",
            f"Pad to {width} bits: {mag}",
            "Make MSB 1, NEG the other bits, then add 1:",
            f"→ MSB=1 & NEG others: {neg_others}",
            f"→ + 1:                {tc}",
            f"{label} bits: " + tc,
        ]
    return "```\n" + "\n".join(lines) + "\n```"

# ============================================================
# Core column addition (on fixed-width bit strings)
# ============================================================

def _add_bits_with_explanation(a_bits: str, b_bits: str) -> Tuple[Dict[str, str], List[str]]:
    """
    Add two fixed-width two's-complement bit-strings (same length) and return
    { result_bits, result_value, carry_in_msb, carry_out_msb, overflow_bool, overflow_kind }
    plus a detailed step-by-step explanation with code blocks.
    """
    width = len(a_bits)
    max_len = width

    explanation: List[str] = []
    carry_vec = [' '] * (max_len + 1)
    res = [' '] * max_len
    carry = 0
    step_no = 0
    carry_into_msb = 0
    carry_out_of_msb = 0

    # Setup block
    setup_lines = [
        "Setup:",
        "",
        f"Width: {width} bits",
        f"A: {a_bits} (sign bit {a_bits[0]})",
        f"B: {b_bits} (sign bit {b_bits[0]})",
        "-" * (max_len + 2),
        " " + " " * max_len,  # placeholder for carry line
        " " + a_bits,
        "+" + b_bits,
        "-" * (max_len + 2),
        " " * (max_len + 1),
    ]
    explanation.append("```\n" + "\n".join(setup_lines) + "\n```")

    for i in range(max_len - 1, -1, -1):
        step_no += 1
        a = int(a_bits[i])
        b = int(b_bits[i])

        s = a + b + carry
        sum_bit = s & 1
        new_carry = (s >> 1) & 1
        res[i] = str(sum_bit)

        # Track carry into/out of MSB (i == 0 is MSB)
        if i == 0:
            carry_into_msb = carry
            carry_out_of_msb = new_carry

        # place carry marker (above the next column to the left)
        if new_carry == 1 and step_no < max_len:
            pos = len(carry_vec) - 1 - step_no
            carry_vec[pos] = '1'

        # Per-step block
        body = []
        body.append(f"Column {step_no}: {a} + {b} + carry({carry}) = {s} → sum {sum_bit}, carry {new_carry}")
        body.append("")
        body.append("".join(carry_vec))
        body.append(" " + a_bits)
        body.append("+" + b_bits)
        body.append("-" * (max_len + 2))

        partial = " "
        for j in range(max_len):
            partial += res[j] if j >= i else ' '
        body.append(partial)
        body.append(" " * (i + 1) + "^")

        explanation.append("```\n" + "\n".join(body) + "\n```")
        carry = new_carry

    result_bits = "".join(res)
    sign_a, sign_b, sign_r = a_bits[0], b_bits[0], result_bits[0]
    overflow = (sign_a == sign_b) and (sign_r != sign_a)
    overflow_kind = None
    if overflow:
        overflow_kind = "positive overflow" if sign_a == '0' else "negative overflow (underflow)"

    # Show final carry-out on the carry line (leftmost position)
    if carry_out_of_msb == 1:
        carry_vec[0] = '1'

    # Final view
    final_lines = [
        "Final addition (with carries):",
        "",
        "".join(carry_vec),
        " " + a_bits,
        "+" + b_bits,
        "-" * (max_len + 2),
        " " + result_bits,
    ]
    explanation.append("```\n" + "\n".join(final_lines) + "\n```")

    # Carry-out note (two's complement ignores it)
    if carry_out_of_msb == 1:
        explanation.append(
            "**Note:** A carry out of the MSB occurred (the leftmost `1` on the carry line). "
            "In fixed-width **two’s-complement** arithmetic this carry is **discarded**, "
            "so the result bits shown are the correct wrapped result."
        )

    # Overflow explanation
    rule_lines = [
        "Overflow rule (two's complement):",
        "",
        "- Overflow occurs when adding two numbers with the **same sign** and the **result sign differs**.",
        f"- Signs: A={sign_a}, B={sign_b}, Result={sign_r}.",
        f"- Carry into MSB={carry_into_msb}, carry out of MSB={carry_out_of_msb} → "
        f"{'overflow' if (carry_into_msb != carry_out_of_msb) else 'no overflow'} by carry rule.",
    ]
    if overflow:
        rule_lines.append(f"→ **{overflow_kind}** detected. The bit-pattern below is the wrapped result.")
    else:
        rule_lines.append("→ No overflow detected.")

    explanation.append("```\n" + "\n".join(rule_lines) + "\n```")

    results = {
        "result_bits": result_bits,
        "result_value": str(_twos_bits_to_int(result_bits)),
        "carry_in_msb": str(carry_into_msb),
        "carry_out_msb": str(carry_out_of_msb),
        "overflow": str(overflow),
        "overflow_kind": overflow_kind or "",
    }
    return results, explanation

# ============================================================
# Public operations (Addition/Subtraction) on two's complement
# ============================================================

def _add_tc_core(a_str: str, b_str: str, width: int) -> Tuple[Dict[str, str], List[str]]:
    """Two's-complement addition with explanations and overflow detection."""
    explanation: List[str] = []

    # Parse / normalize
    a_val, a_bits, err_a = _parse_operand(a_str, width)
    b_val, b_bits, err_b = _parse_operand(b_str, width)
    if err_a or err_b:
        msg = err_a or err_b
        return {"error": msg}, [msg]

    lo, hi = _bit_range(width)
    explanation.append("### 1. Setup")
    explanation.append(
        "We represent signed integers in **two’s-complement**:\n"
        "- Take **ABS(value)** and write its binary.\n"
        f"- **Pad left** with 0s to **{width} bits**.\n"
        "- If the original is **positive** (sign 0), keep it.\n"
        "- If it’s **negative** (sign 1), **make the first bit 1**, **NEG** the other bits, then **add 1**."
    )
    setup = [
        "Setup:",
        "",
        f"Width: {width} bits (range {lo} .. {hi})",
        f"Operand A: {a_str} → {a_bits} (value {a_val})",
        f"Operand B: {b_str} → {b_bits} (value {b_val})",
    ]
    explanation.append("```\n" + "\n".join(setup) + "\n```")
    # Per-operand conversion mini-traces
    explanation.append(_conversion_block("A", a_val, width))
    explanation.append(_conversion_block("B", b_val, width))

    # Column addition
    explanation.append("### 2. Column-by-Column Addition")
    add_res, add_steps = _add_bits_with_explanation(a_bits, b_bits)
    explanation.extend(add_steps)

    # Final message
    result_bits = add_res["result_bits"]
    result_val = _twos_bits_to_int(result_bits)
    overflow = add_res["overflow"] == "True"
    overflow_kind = add_res["overflow_kind"]

    explanation.append("### 3. Final Result")
    final_msg = [f"**Answer:** `{a_val} + {b_val} = {result_val}`  (bits: `{result_bits}`)"]
    if overflow:
        final_msg.append(f"**Overflow:** {overflow_kind}.")
    explanation.append("\n".join(final_msg))

    return {
        "result_bits": result_bits,
        "result_value": str(result_val),
        "overflow": overflow,
        "overflow_kind": overflow_kind,
    }, explanation

def _sub_tc_core(a_str: str, b_str: str, width: int) -> Tuple[Dict[str, str], List[str]]:
    """Two's-complement subtraction with explanations and overflow detection."""
    explanation: List[str] = []

    # Parse / normalize
    a_val, a_bits, err_a = _parse_operand(a_str, width)
    b_val, b_bits, err_b = _parse_operand(b_str, width)
    if err_a or err_b:
        msg = err_a or err_b
        return {"error": msg}, [msg]

    lo, hi = _bit_range(width)
    explanation.append("### 1. Setup")
    explanation.append(
        "We represent signed integers in **two’s-complement**:\n"
        "- Take **ABS(value)** and write its binary.\n"
        f"- **Pad left** with 0s to **{width} bits**.\n"
        "- If the original is **positive** (sign 0), keep it.\n"
        "- If it’s **negative** (sign 1), **make the first bit 1**, **NEG** the other bits, then **add 1**."
    )
    setup = [
        "Setup:",
        "",
        f"Width: {width} bits (range {lo} .. {hi})",
        f"Operand A: {a_str} → {a_bits} (value {a_val})",
        f"Operand B: {b_str} → {b_bits} (value {b_val})",
        "",
        "We compute subtraction as **A - B = A + (two's complement of B)**.",
    ]
    explanation.append("```\n" + "\n".join(setup) + "\n```")
    # Per-operand conversion mini-traces
    explanation.append(_conversion_block("A", a_val, width))
    explanation.append(_conversion_block("B", b_val, width))

    # Two's complement of B (show ~B + 1 summary)
    inv = _invert_bits(b_bits)
    one = "0" * (width - 1) + "1"
    add_neg, _ = _add_bits_with_explanation(inv, one)
    neg_b_bits = add_neg["result_bits"]
    neg_b_val = _twos_bits_to_int(neg_b_bits)

    explanation.append("### 2. Build -B using two's complement")
    block = [
        "Two's complement of B (within width):",
        "",
        f"B:   {b_bits}",
        f"~B:  {inv}",
        f"+1:  {one}",
        "-" * (width + 2),
        f"-B:  {neg_b_bits}  (value {neg_b_val})",
    ]
    explanation.append("```\n" + "\n".join(block) + "\n```")

    # Now perform A + (-B)
    explanation.append("### 3. Add A + (-B)")
    add_res, add_steps = _add_bits_with_explanation(a_bits, neg_b_bits)
    explanation.extend(add_steps)

    result_bits = add_res["result_bits"]
    result_val = _twos_bits_to_int(result_bits)
    overflow = add_res["overflow"] == "True"
    overflow_kind = add_res["overflow_kind"]

    explanation.append("### 4. Final Result")
    final_msg = [f"**Answer:** `{a_val} - {b_val} = {result_val}`  (bits: `{result_bits}`)"]
    if overflow:
        final_msg.append(f"**Overflow:** {overflow_kind}.")
    explanation.append("\n".join(final_msg))

    return {
        "result_bits": result_bits,
        "result_value": str(result_val),
        "overflow": overflow,
        "overflow_kind": overflow_kind,
    }, explanation

# ============================================================
# Streamlit UI
# ============================================================

def render() -> None:
    """Renders the Two’s-Complement Arithmetic tool in Streamlit."""
    st.title("Two’s-Complement Arithmetic (Signed)")
    st.markdown(
        "Add or subtract **signed** integers using two’s-complement representation. "
        "Choose a width (8/16/32 bits). You can enter values as decimal (e.g., `-13`), "
        "binary (`0b1011`, `-0b1011`, or raw bits like `1011`), or hex (`0xAF`)."
    )

    # Inputs
    col1, col2 = st.columns(2)
    with col1:
        op_a = st.text_input("Operand A", "-5")
    with col2:
        op_b = st.text_input("Operand B", "12")

    width = st.selectbox("Integer width", [8, 16, 32], index=1)
    operation = st.radio("Operation", ("Addition", "Subtraction"), horizontal=True)

    if st.button("Calculate", key="calc_twos_signed"):
        if operation == "Addition":
            results, steps = _add_tc_core(op_a, op_b, width)
        else:
            results, steps = _sub_tc_core(op_a, op_b, width)

        if "error" in results:
            st.error(results["error"])
            return

        # Result summary
        st.subheader("Result")
        st.success(f"**Value:** `{results['result_value']}`")
        st.info(f"**Bits:** `{results['result_bits']}`")

        if results["overflow"]:
            kind = results.get("overflow_kind") or "overflow"
            st.warning(f"**Overflow detected:** {kind}. The bit-pattern shown is the wrapped result.")

        # Explanation
        st.subheader("Step-by-Step Explanation")

        def is_column_block(s: str) -> bool:
            # Our per-column blocks start with ```\nColumn ...
            return s.startswith("```\nColumn ")

        # Stream the steps and wrap contiguous column-block runs in an expander
        in_group = False
        group: List[str] = []
        group_idx = 0

        for s in steps:
            if is_column_block(s):
                if not in_group:
                    in_group = True
                    group = [s]
                else:
                    group.append(s)
            else:
                if in_group:
                    group_idx += 1
                    with st.expander(f"Show column-by-column addition steps #{group_idx}", expanded=False):
                        for g in group:
                            st.markdown(g, unsafe_allow_html=True)
                    in_group = False
                    group = []
                st.markdown(s, unsafe_allow_html=True)

        # Flush a trailing group if the list ended with column steps
        if in_group and group:
            group_idx += 1
            with st.expander(f"Show column-by-column addition steps #{group_idx}", expanded=False):
                for g in group:
                    st.markdown(g, unsafe_allow_html=True)
