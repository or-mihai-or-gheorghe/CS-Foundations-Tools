# tools/decimal_to_binary.py

import streamlit as st
from decimal import Decimal, getcontext

# High precision so fractional steps and rounding are stable
getcontext().prec = 200

# ---------- Small helpers ----------

def _group_bits(s: str, group: int = 4) -> str:
    """
    Group bits in chunks of `group`, keeping the sign separate and not counting it
    toward grouping. Pads the integer part on the left to full groups of `group`.
    Example:
      "-1101.101" with group=4 -> "-1101. 101"
      "101" -> "0101"
    """
    if group <= 0:
        return s

    sign = ""
    if s[:1] in "+-":
        sign = s[0]
        s = s[1:]

    if "." in s:
        left, right = s.split(".", 1)
    else:
        left, right = s, ""

    # Pad integer part left
    if left:
        pad_len = (-len(left)) % group
        if pad_len:
            left = "0" * pad_len + left

    gl = " ".join(left[i:i+group] for i in range(0, len(left), group)) if left else "0"
    gr = " ".join(right[i:i+group] for i in range(0, len(right), group)) if right else ""

    out = gl + (("." + gr) if gr else "")
    return sign + out


def _clean_decimal_text(x: str) -> str:
    """
    Normalize a decimal string:
    - trims spaces/underscores,
    - allows one optional leading +/−,
    - allows at most one dot,
    - requires at least one digit.
    """
    x = x.strip().replace('_', '').replace(' ', '')
    if x.count('.') > 1:
        raise ValueError("Too many decimal points.")
    if x in {"+", "-"}:
        raise ValueError("Missing digits.")
    return x

def _infer_default_frac_bits(number_str: str, fallback: int = 16) -> int:
    """
    Return 0 by default if:
      - the input has no fractional part, or
      - the fractional part exists but is all zeros.
    Otherwise, return `fallback` (default 16).
    """
    try:
        s = _clean_decimal_text(number_str)
    except Exception:
        return fallback  # if input isn't clean yet, keep the older behavior

    # Strip optional sign
    if s.startswith(('+', '-')):
        s = s[1:]

    if '.' not in s:
        return 0

    frac = s.split('.', 1)[1]
    if frac == "" or set(frac) <= {'0'}:
        return 0
    return fallback


def _fmt_dec_short(d: Decimal) -> str:
    """
    Friendly decimal formatting: no scientific notation for simple values,
    trim trailing zeros, and remove trailing dot.
    """
    s = format(d, 'f')  # fixed-point
    s = s.rstrip('0').rstrip('.')
    return s if s else "0"


# ---------- Core conversion ----------

def _decimal_to_binary_core(number_str: str, frac_bits: int, rounding: str):
    """
    Convert a base-10 string (may include fractional part and sign) to binary string
    with up to frac_bits after the point, using either 'truncate' or 'nearest-even' rounding.
    Returns (result_dict, explanation_lines).
    """
    explanation = []

    # 1) Normalize input & sign
    try:
        s = _clean_decimal_text(number_str)
    except ValueError as e:
        return None, [f"Error: {e}"]

    sign = ''
    if s.startswith('-'):
        sign = '-'
        s = s[1:]
    elif s.startswith('+'):
        s = s[1:]

    if s == "" or s == ".":
        return None, ["Error: Please enter digits (e.g., -13.625, 0.1, 42)."]

    if '.' in s:
        int_part_str, frac_part_str = s.split('.', 1)
    else:
        int_part_str, frac_part_str = s, ""

    int_part_str = int_part_str or "0"
    frac_part_str = frac_part_str or ""

    # Validate numeric
    if not (int_part_str.isdigit() and (frac_part_str.isdigit() or frac_part_str == "")):
        return None, ["Error: Only digits and one '.' are allowed (and an optional leading sign)."]

    # 2) Integer part: repeated division by 2
    explanation.append("### 1) Integer Part via Repeated Division by 2")
    try:
        n = int(int_part_str)
    except Exception:
        return None, ["Error: Integer part is too large to parse."]
    if n == 0:
        int_bits = "0"
        explanation.append("- Integer is 0 ⇒ binary integer part is `0`.")
        division_table = ["0 / 2 = 0 remainder 0"]
    else:
        bits = []
        division_table = []
        temp = n
        while temp > 0:
            q, r = divmod(temp, 2)
            division_table.append(f"{temp} / 2 = {q} remainder {r}")
            bits.append(str(r))
            temp = q
        int_bits = ''.join(reversed(bits))
    st_table_int = "Division steps (top→bottom are performed order):\n" + "\n".join(division_table)
    explanation.append("Division by 2 steps:")
    explanation.append(f"```\n{st_table_int}\n```")
    explanation.append(f"- **Integer bits:** `{_group_bits(int_bits)}`")

    # 3) Fractional part: repeated multiplication by 2 (friendlier output)
    explanation.append("\n### 2) Fractional Part via Repeated Multiplication by 2")
    if frac_part_str == "" or int(frac_part_str) == 0:
        frac_bits_full = ""
        explanation.append("- Fractional part is 0 ⇒ binary fractional part is empty (or all zeros).")
    else:
        f = Decimal("0." + frac_part_str)
        steps = []
        out_bits = []
        # We generate extra bits for rounding if needed
        extra = 4 if rounding == "nearest-even" else 0
        limit = frac_bits + extra if frac_bits > 0 else (extra if extra > 0 else 64)  # keep a cap in case user chose 0 bits
        # Friendlier, compact per-step lines
        for k in range(1, limit + 1):
            before = _fmt_dec_short(f)
            f *= 2
            bit = int(f)  # 0 or 1
            after = _fmt_dec_short(f)
            remainder = _fmt_dec_short(f - bit)
            out_bits.append(str(bit))
            steps.append(f"Step {k}: {before} × 2 = {after} ⇒ take {bit}; remainder {remainder}")
            f -= bit
            if f == 0:
                break
        frac_bits_full = ''.join(out_bits)
        explanation.append("Multiplication by 2 steps:")
        explanation.append("```\n" + "\n".join(steps[:64]) + ("\n..." if len(steps) > 64 else "") + "\n```")
        explanation.append(f"- **Raw fractional bits:** `{frac_bits_full or '0'}`")

    # 4) Rounding / Truncation
    explanation.append("\n### 3) Rounding Rule for Fractional Bits")
    explanation.append(f"- Requested fractional precision: **{frac_bits}** bits after the point.")
    integer_value = int(int_bits, 2) if int_bits else 0

    if frac_bits == 0:
        # No fractional output: round integer if nearest-even & fractional >= .5
        carry = 0
        if rounding == "nearest-even":
            # Look at the first fractional bit (guard) and sticky
            guard = int(frac_bits_full[0]) if len(frac_bits_full) >= 1 else 0
            sticky = 1 if ('1' in frac_bits_full[1:]) else 0
            lsb_even = (integer_value % 2 == 0)
            round_up = (guard == 1) and ((sticky == 1) or (not lsb_even))
            carry = 1 if round_up else 0
            explanation.append(f"- Nearest-even: guard={guard}, sticky={sticky}, integer LSB even? {lsb_even} ⇒ round_up={round_up}")
        else:
            explanation.append("- Truncate mode: discard fractional part.")
        if carry:
            integer_value += 1
            int_bits = format(integer_value, 'b')
        frac_bits_final = ""
    else:
        # Keep frac_bits (padded with zeros); apply rounding if needed
        if len(frac_bits_full) < frac_bits:
            frac_bits_final = frac_bits_full + '0' * (frac_bits - len(frac_bits_full))
            explanation.append("- Not enough raw bits → padded with zeros.")
        else:
            kept = frac_bits_full[:frac_bits]
            tail = frac_bits_full[frac_bits:]
            if rounding == "truncate" or len(tail) == 0:
                frac_bits_final = kept
                if rounding == "truncate":
                    explanation.append("- Truncate mode: we keep the first k bits and drop the rest.")
            else:
                guard = 1 if tail[:1] == '1' else 0
                sticky = 1 if '1' in tail[1:] else 0
                lsb = int(kept[-1]) if kept else 0
                round_up = (guard == 1 and (sticky == 1 or lsb == 1))
                explanation.append(f"- Nearest-even: guard={guard}, sticky={sticky}, LSB={lsb} ⇒ round_up={round_up}")
                if round_up:
                    # Add 1 ulp (2^-frac_bits)
                    m = int(kept, 2) + 1
                    if m >= (1 << frac_bits):
                        # carry into integer part
                        integer_value += 1
                        int_bits = format(integer_value, 'b')
                        frac_bits_final = '0' * frac_bits
                        explanation.append("- Rounding carried into integer part.")
                    else:
                        frac_bits_final = format(m, f"0{frac_bits}b")
                else:
                    frac_bits_final = kept

    # 5) Assemble full result & math checks
    bin_str = int_bits
    if frac_bits > 0:
        bin_str += ('.' + (frac_bits_final or '0'*frac_bits))

    full_bin = ('-' if sign == '-' else '') + bin_str

    # Compute back to decimal (for display/verification)
    dec_from_bits = Decimal(integer_value)
    if frac_bits > 0:
        for i, b in enumerate(frac_bits_final, start=1):
            if b == '1':
                dec_from_bits += Decimal(2) ** Decimal(-i)
    if sign == '-':
        dec_from_bits = -dec_from_bits

    # 6) LaTeX explanation for value
    explanation.append("\n### 4) Mathematical Form (Value Reconstruction)")
    st_formula = r"x \;=\; (-1)^s \left(\sum_{i=0}^{n-1} b_i\,2^{\,n-1-i} \;+\; \sum_{j=1}^{m} f_j\,2^{-j} \right)"
    explanation.append("We treat the integer part as powers of 2 (left to right), and the fractional part as negative powers of 2.")
    explanation.append(" ")
    explanation.append("**Formula:**")
    explanation.append(f"$${st_formula}$$")

    # Show concrete sum (limited length to keep readable)
    int_terms = []
    for idx, ch in enumerate(int_bits):
        if ch == '1':
            power = len(int_bits) - 1 - idx
            int_terms.append(f"2^{{{power}}}")
    frac_terms = []
    for j, ch in enumerate((frac_bits_final or ""), start=1):
        if ch == '1':
            frac_terms.append(f"2^{{-{j}}}")

    pretty_int = " + ".join(int_terms) if int_terms else "0"
    pretty_frac = " + ".join(frac_terms) if frac_terms else "0"
    explanation.append("**This input becomes**")
    explanation.append(f"$${'-' if sign=='-' else ''}\\big( {pretty_int} \\, + \\, {pretty_frac} \\big)$$")

    results = {
        "sign": '-' if sign == '-' else '+',
        "int_bits": int_bits,
        "frac_bits": frac_bits_final,
        "bin_string": full_bin,
        "grouped": _group_bits(full_bin, 4),
        "decimal_back": f"{dec_from_bits}",
        "rounding": rounding,
        "requested_frac_bits": frac_bits
    }
    return results, explanation

# ---------- Streamlit UI ----------

def render() -> None:
    st.title("Decimal → Binary")

    st.markdown(
        r"""
Convert a base-10 number (with optional fractional part and sign) to **binary**.

### Rules
1. **Sign**: keep the sign as is (this tool shows *unsigned* magnitude in base 2, not two’s complement).
2. **Integer part**: repeated **division by 2**; the remainders read bottom→top give the bits.
3. **Fractional part**: repeated **multiplication by 2**; each integer part extracted is a bit (top→bottom).
4. **Rounding**: choose **truncate** or **round to nearest, ties to even** for the fractional bits.
"""
    )

    col1, col2 = st.columns(2)
    with col1:
        decimal_in = st.text_input("Decimal input", "-13.625")
    with col2:
        # Default 0 fractional bits if input has no decimals or all fractional digits are zero
        default_frac_bits = _infer_default_frac_bits(decimal_in, fallback=16)
        frac_bits = st.slider("Fractional bits to output", 0, 64, value=default_frac_bits, key="dec2bin_frac_bits")

    rounding = st.radio("Rounding mode (for fractional part)", ("nearest-even", "truncate"), index=0, horizontal=True)

    if st.button("Convert", key="dec2bin"):
        st.markdown("---")
        results, steps = _decimal_to_binary_core(decimal_in, frac_bits, rounding)

        if not results:
            st.error(steps[0])
            return

        st.subheader("Result")

        # Remove trailing zeros in fractional part for display
        raw_bin = results['bin_string']
        if '.' in raw_bin:
            raw_bin = raw_bin.rstrip('0').rstrip('.')

        st.markdown(f"- **Binary (raw):** `{raw_bin}`")
        st.markdown(f"- **Binary (grouped):** `{results['grouped']}`")
        st.markdown(f"- **Recomputed decimal:** `{results['decimal_back']}`")
        st.caption(f"Rounding: {results['rounding']}, fractional bits shown: {results['requested_frac_bits']}")

        st.markdown("---")
        st.subheader("Step-by-step")
        for s in steps:
            st.markdown(s, unsafe_allow_html=True)
