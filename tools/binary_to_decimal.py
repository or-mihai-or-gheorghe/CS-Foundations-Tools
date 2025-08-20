# tools/binary_to_decimal.py

import streamlit as st
from decimal import Decimal, getcontext

getcontext().prec = 200

def _group_bits(s: str, group: int = 4) -> str:
    if group <= 0: return s
    if '.' in s:
        left, right = s.split('.', 1)
        gl = " ".join(left[i:i+group] for i in range(0, len(left), group)) if left else "0"
        gr = " ".join(right[i:i+group] for i in range(0, len(right), group)) if right else ""
        return gl + ('. ' + gr if gr else '')
    return " ".join(s[i:i+group] for i in range(0, len(s), group))

def _clean_binary_text(x: str) -> str:
    x = x.strip().replace('_','').replace(' ','')
    if x.count('.') > 1:
        raise ValueError("Too many binary points.")
    if x in {"+", "-", ".", ""}:
        raise ValueError("Missing bits.")
    # Allow leading sign
    core = x[1:] if x[:1] in "+-" else x
    if not all(ch in "01." for ch in core):
        raise ValueError("Only 0/1 digits and at most one '.' are allowed (and optional leading sign).")
    return x

def _binary_to_decimal_core(bin_str: str):
    explanation = []

    # 1) Normalize input & sign
    try:
        s = _clean_binary_text(bin_str)
    except ValueError as e:
        return None, [f"Error: {e}"]

    sign = 1
    if s.startswith('-'):
        sign = -1
        s = s[1:]
    elif s.startswith('+'):
        s = s[1:]

    if '.' in s:
        int_bits, frac_bits = s.split('.', 1)
    else:
        int_bits, frac_bits = s, ""

    int_bits = int_bits or "0"     # allow ".101"
    frac_bits = frac_bits or ""    # allow "101."

    # Disallow empty or non-binary (after previous check)
    if not (set(int_bits).issubset({'0','1'}) and set(frac_bits).issubset({'0','1'})):
        return None, ["Error: Bits must be 0 or 1."]

    explanation.append("### 1) Decomposition")
    explanation.append(f"- **Sign:** `{'-' if sign < 0 else '+'}`")
    explanation.append(f"- **Integer bits:** `{_group_bits(int_bits)}`")
    explanation.append(f"- **Fractional bits:** `{_group_bits(frac_bits) if frac_bits else '(none)'}`")

    # 2) Integer value
    explanation.append("\n### 2) Integer Part as Powers of 2")
    intval = Decimal(0)
    int_terms = []
    if int_bits == "0":
        explanation.append("- Integer bits are `0` ⇒ value 0.")
    else:
        for idx, b in enumerate(int_bits):
            power = len(int_bits) - 1 - idx
            if b == '1':
                term = Decimal(2) ** Decimal(power)
                intval += term
                int_terms.append(f"2^{{{power}}}")
        explanation.append("- Sum the powers where bit=1:")
        explanation.append(f"$${' + '.join(int_terms) if int_terms else '0'} = {intval}$$")

    # 3) Fractional value
    explanation.append("\n### 3) Fractional Part as Negative Powers of 2")
    fracval = Decimal(0)
    frac_terms = []
    if frac_bits:
        for j, b in enumerate(frac_bits, start=1):
            if b == '1':
                term = Decimal(2) ** Decimal(-j)
                fracval += term
                frac_terms.append(f"2^{{-{j}}}")
        explanation.append("- Sum the powers where bit=1:")
        explanation.append(f"$${' + '.join(frac_terms) if frac_terms else '0'} = {fracval}$$")
    else:
        explanation.append("- No fractional bits ⇒ value 0.")

    # 4) Combine & show formula
    total = (intval + fracval) * (Decimal(-1) if sign < 0 else Decimal(1))

    explanation.append("\n### 4) Final Value")
    formula = r"x \;=\; (-1)^s \left(\sum_{i=0}^{n-1} b_i\,2^{\,n-1-i} \;+\; \sum_{j=1}^{m} f_j\,2^{-j}\right)"
    explanation.append("**Formula:**")
    explanation.append(f"$${formula}$$")
    explanation.append(f"- **Result:** `{total}`")

    return {
        "grouped_input": ('-' if sign < 0 else '') + _group_bits(s, 4),
        "decimal_value": f"{total}",
    }, explanation

def render() -> None:
    st.title("Binary → Decimal")

    st.markdown(
        r"""
Convert a binary string (optionally with fractional part and sign) to **base-10**.

### Rules
1. Split into **integer** and **fractional** parts at the binary point.
2. Integer part $\;\Rightarrow\;$ sum the **powers of 2** where bit $=1$.
3. Fractional part $\;\Rightarrow\;$ sum the **negative powers** $2^{-j}$ where bit $=1$.
4. Apply the **sign** at the end.
"""
    )


    bin_in = st.text_input("Binary input", "-1101.101")

    if st.button("Convert", key="bin2dec"):
        st.markdown("---")
        results, steps = _binary_to_decimal_core(bin_in)

        if not results:
            st.error(steps[0])
            return

        st.subheader("Result")
        st.markdown(f"- **Decimal value:** `{results['decimal_value']}`")

        st.markdown("---")
        st.subheader("Step-by-step")
        for s in steps:
            st.markdown(s, unsafe_allow_html=True)
