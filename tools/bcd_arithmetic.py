# tools/bcd_arithmetic.py
from __future__ import annotations

import streamlit as st
from typing import List, Tuple, Optional

# ------------------------------------------------------------
# BCD helpers
# ------------------------------------------------------------

def _clean(s: str) -> str:
    return s.strip().replace(" ", "").replace("_", "")

def _digits_to_bcd_bits(digits: List[int]) -> str:
    return "".join(f"{d:04b}" for d in digits)

def _format_nibbles(bits: str) -> str:
    # "001100010100" -> "0011 0001 0100"
    return " ".join(bits[i:i+4] for i in range(0, len(bits), 4))

def _parse_bcd_operand(s: str) -> Tuple[Optional[List[int]], Optional[str], Optional[int], Optional[str]]:
    """
    Accepts a decimal string (e.g., '12345') or a raw BCD bitstring (e.g., '0001 0010 0011').
    Returns (digits[], bits, decimal_value, error).
    Only non-negative values are supported in this tool.
    """
    raw = _clean(s)
    if not raw:
        return None, None, None, "Input cannot be empty."

    # For this tool we keep BCD unsigned
    if raw.startswith("-"):
        return None, None, None, "Negative operands are not supported in BCD tool (use two’s-complement tool)."

    if all(c.isdigit() for c in raw):
        digits = [int(c) for c in raw]
        bits = _digits_to_bcd_bits(digits)
        return digits, bits, int(raw, 10), None

    if all(c in "01" for c in raw) and len(raw) % 4 == 0:
        digits: List[int] = []
        for i in range(0, len(raw), 4):
            nib = raw[i:i+4]
            val = int(nib, 2)
            if val > 9:
                return None, None, None, f"Nibble '{nib}' is not a valid BCD digit (>= 1010)."
            digits.append(val)
        bits = raw
        dec = int("".join(str(d) for d in digits)) if digits else 0
        return digits, bits, dec, None

    return None, None, None, "Enter decimal digits (e.g., 1234) or BCD bits of length multiple of 4 (e.g., 0001 0010)."

def _pad_digits(a: List[int], b: List[int]) -> Tuple[List[int], List[int]]:
    n = max(len(a), len(b))
    return [0]*(n-len(a)) + a, [0]*(n-len(b)) + b

# ------------------------------------------------------------
# BCD Addition (digit by digit with +0110 correction)
# ------------------------------------------------------------

def _bcd_add_core(a_in: str, b_in: str) -> Tuple[dict, List[str]]:
    """
    BCD addition for non-negative operands.
    Returns results + a list of explanation blocks (some inside expanders).
    """
    a_digits, a_bits, a_val, err_a = _parse_bcd_operand(a_in)
    b_digits, b_bits, b_val, err_b = _parse_bcd_operand(b_in)
    if err_a or err_b:
        return {"error": err_a or err_b}, [err_a or err_b]

    A, B = _pad_digits(a_digits, b_digits)
    n = len(A)

    # Setup
    explanation: List[str] = []
    explanation.append("### 1. Setup")
    setup = [
        "BCD operates on decimal digits encoded as 4-bit nibbles (0000–1001).",
        "For each digit (right→left) we compute a raw 4-bit sum and if the result is invalid (>1001) or",
        "produces a carry, we add 0110 (decimal 6) to correct it and carry 1 to the next digit.",
        "",
        "Operands (right-aligned):",
        f"A (dec): {a_val}",
        f"A (BCD): {_format_nibbles(_digits_to_bcd_bits(A))}",
        f"B (dec): {b_val}",
        f"B (BCD): {_format_nibbles(_digits_to_bcd_bits(B))}",
    ]
    explanation.append("```\n" + "\n".join(setup) + "\n```")

    # Per-digit processing
    carry = 0
    result_digits = [0]*n
    digit_blocks: List[str] = []

    for pos in range(n-1, -1, -1):
        da, db = A[pos], B[pos]
        carry_in = carry

        # Raw 4-bit sum (binary digits + carry)
        raw_sum_dec = da + db + carry_in
        raw_carry = 1 if raw_sum_dec >= 16 else 0  # carry out of 4-bit boundary
        raw_low = raw_sum_dec % 16
        raw_bits = f"{raw_low:04b}"

        needs_correction = (raw_low > 9) or (raw_carry == 1)
        corrected_low = raw_low
        correction_carry = 0

        block = []
        step_idx = n - pos
        block.append(f"BCD addition – digit {step_idx} (from right)")
        block.append("")
        block.append(f"Digits: {da} + {db} + carry({carry_in}) = {raw_sum_dec}")
        block.append(f"Nibble A: {da:04b}")
        block.append(f"Nibble B: {db:04b}")
        block.append(f"Carry-in: {'0001' if carry_in else '0000'}")
        block.append("")
        block.append("Raw 4-bit sum:")
        block.append(f"  {da:04b}")
        block.append(f"+ {db:04b}")
        block.append(f"+ {'0001' if carry_in else '0000'}")
        block.append("  ----")
        block.append(f"  {raw_bits}  (carry_out={raw_carry})")

        if needs_correction:
            # Add 6 (0110) correction
            corrected = raw_low + 6
            correction_carry = 1 if corrected >= 16 else 0
            corrected_low = corrected % 16
            block.append("")
            block.append("Correction needed (raw > 1001 or carry_out=1) → add 0110:")
            block.append(f"  {raw_bits}")
            block.append(f"+ 0110")
            block.append("  ----")
            block.append(f"  {corrected_low:04b}  (extra carry={correction_carry})")

        carry = 1 if (da + db + carry_in) >= 10 else 0  # decimal carry to next digit
        result_digit = (da + db + carry_in) % 10
        result_digits[pos] = result_digit

        block.append("")
        block.append(f"Digit result: {result_digit}  |  carry to next digit: {carry}")
        digit_blocks.append("```\n" + "\n".join(block) + "\n```")

    # Handle final carry-out
    final_carry = carry
    result_str_digits = "".join(str(d) for d in result_digits)
    if final_carry:
        result_str_digits = "1" + result_str_digits

    result_bits = _digits_to_bcd_bits(([1] if final_carry else []) + result_digits)

    explanation.append("### 2. Final Result")
    merged = []
    line_a = _format_nibbles(_digits_to_bcd_bits(A))
    line_b = _format_nibbles(_digits_to_bcd_bits(B))
    width = max(len(line_a), len(line_b)) + 2
    merged.append("Final BCD addition:")
    merged.append("")
    merged.append(line_a.rjust(width))
    merged.append(("+" + line_b).rjust(width))
    merged.append("-" * width)
    merged.append(_format_nibbles(result_bits).rjust(width))
    if final_carry:
        merged.append("")
        merged.append("Note: Final carry-out produces a new leftmost BCD digit '0001'.")

    explanation.append("```\n" + "\n".join(merged) + "\n```")

    results = {
        "result_decimal": int(result_str_digits),
        "result_digits": result_str_digits,
        "result_bits": _format_nibbles(result_bits),
        "digit_blocks": digit_blocks,  # for expanders
    }
    return results, explanation

# ------------------------------------------------------------
# BCD Subtraction (digit by digit with borrow and +1010 correction)
# ------------------------------------------------------------

def _bcd_sub_core(a_in: str, b_in: str) -> Tuple[dict, List[str]]:
    """
    BCD subtraction for non-negative operands.
    If A < B, we compute (B - A) and prefix a '-' in the decimal result, while still showing
    the borrow/correction steps for the magnitude.
    """
    a_digits, a_bits, a_val, err_a = _parse_bcd_operand(a_in)
    b_digits, b_bits, b_val, err_b = _parse_bcd_operand(b_in)
    if err_a or err_b:
        return {"error": err_a or err_b}, [err_a or err_b]

    # If negative result, swap to show positive magnitude steps and remember the sign.
    neg = False
    if a_val < b_val:
        A_raw, B_raw = b_digits, a_digits
        neg = True
    else:
        A_raw, B_raw = a_digits, b_digits

    A, B = _pad_digits(A_raw, B_raw)
    n = len(A)

    # Setup
    explanation: List[str] = []
    explanation.append("### 1. Setup")
    setup = [
        "BCD subtraction is done digit-by-digit (right→left).",
        "If a digit cannot subtract (result would be negative), we borrow 1 decimal from the next digit,",
        "which is equivalent to adding 1010 (decimal 10) to this nibble and setting a borrow for the next.",
        "",
        f"Compute {'B - A' if neg else 'A - B'} to get the magnitude; apply sign at the end.",
        f"A (dec): {int(''.join(map(str, A)),10)}",
        f"A (BCD): {_format_nibbles(_digits_to_bcd_bits(A))}",
        f"B (dec): {int(''.join(map(str, B)),10)}",
        f"B (BCD): {_format_nibbles(_digits_to_bcd_bits(B))}",
    ]
    explanation.append("```\n" + "\n".join(setup) + "\n```")

    # Per-digit processing
    borrow = 0
    result_digits = [0]*n
    digit_blocks: List[str] = []

    for pos in range(n-1, -1, -1):
        da, db = A[pos], B[pos]
        borrow_in = borrow
        raw = da - borrow_in - db

        block = []
        step_idx = n - pos
        block.append(f"BCD subtraction – digit {step_idx} (from right)")
        block.append("")
        block.append(f"Digits: {da} - {db} - borrow({borrow_in}) = {raw}")
        block.append(f"Nibble A: {da:04b}")
        block.append(f"Nibble B: {db:04b}")
        block.append(f"Borrow-in: {'0001' if borrow_in else '0000'}")
        block.append("")

        if raw < 0:
            # Need borrow: add 10 (1010) to make a valid BCD digit
            corrected = raw + 10
            borrow = 1
            result_digit = corrected
            block.append("Borrow needed → add 1010 (decimal 10) to this nibble and set borrow=1 for the next digit:")
            block.append(f"  raw result (negative): {raw}")
            block.append(f"  corrected: {corrected}  → {corrected:04b} (valid BCD digit)")
        else:
            borrow = 0
            result_digit = raw
            block.append("No borrow needed; result digit is valid (0–9).")
            block.append(f"  digit: {result_digit}  → {result_digit:04b}")

        result_digits[pos] = result_digit
        block.append("")
        block.append(f"Digit result: {result_digit}  |  borrow to next digit: {borrow}")
        digit_blocks.append("```\n" + "\n".join(block) + "\n```")

    # Remove leading zeros in digits (but keep at least one)
    # (Do not drop a leading zero if the true result is zero)
    mag_digits_str = "".join(map(str, result_digits)).lstrip('0') or "0"
    result_decimal = int(mag_digits_str, 10)
    result_bits = _digits_to_bcd_bits([int(c) for c in mag_digits_str])

    if neg and result_decimal != 0:
        dec_str = "-" + mag_digits_str
    else:
        dec_str = mag_digits_str

    explanation.append("### 2. Final Result")
    merged = []
    line_a = _format_nibbles(_digits_to_bcd_bits(A))
    line_b = _format_nibbles(_digits_to_bcd_bits(B))
    width = max(len(line_a), len(line_b)) + 2
    merged.append(f"Final BCD subtraction (magnitude {'B - A' if neg else 'A - B'}):")
    merged.append("")
    merged.append(line_a.rjust(width))
    merged.append(("-" + line_b).rjust(width))
    merged.append("-" * width)
    merged.append(_format_nibbles(result_bits).rjust(width))
    if neg and result_decimal != 0:
        merged.append("")
        merged.append("Sign: A < B → final result is negative.")

    explanation.append("```\n" + "\n".join(merged) + "\n```")

    results = {
        "result_decimal": int(dec_str) if dec_str != "-" else 0,
        "result_digits": dec_str,
        "result_bits": _format_nibbles(result_bits if dec_str[0] != '-' else result_bits),
        "digit_blocks": digit_blocks,
        "negative": neg and result_decimal != 0,
    }
    return results, explanation

# ------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------

def render() -> None:
    st.title("BCD Arithmetic (Addition & Subtraction)")
    st.markdown(
        "Perform **BCD** (Binary-Coded Decimal) addition and subtraction on **non-negative** operands.\n"
        "- Enter plain decimal (e.g., `1234`) or raw BCD bits (e.g., `0001 0010 0011`).\n"
        "- Addition fixes invalid digits by **adding 0110** to a nibble that overflowed.\n"
        "- Subtraction borrows as needed and corrects the nibble by **adding 1010** (decimal 10)."
    )

    col1, col2 = st.columns(2)
    with col1:
        a_in = st.text_input("Operand A", "1234")
    with col2:
        b_in = st.text_input("Operand B", "567")

    op = st.radio("Operation", ("Addition", "Subtraction"), horizontal=True)

    if st.button("Calculate", key="calc_bcd"):
        if op == "Addition":
            results, expl = _bcd_add_core(a_in, b_in)
        else:
            results, expl = _bcd_sub_core(a_in, b_in)

        if "error" in results:
            st.error(results["error"])
            return

        # Results
        st.subheader("Result")
        st.success(f"**Decimal:** `{results['result_decimal']}`")
        st.code(results["result_bits"], language="")

        # Explanations
        st.subheader("Step-by-Step Explanation")

        # 1) Show all narrative/setup/final blocks as-is
        for block in expl:
            st.markdown(block, unsafe_allow_html=True)

        # 2) Put per-digit traces inside collapsible expanders
        digit_blocks: List[str] = results.get("digit_blocks", [])
        for i, db in enumerate(digit_blocks, start=1):
            with st.expander(f"Show digit-by-digit steps #{i}", expanded=False):
                st.markdown(db, unsafe_allow_html=True)