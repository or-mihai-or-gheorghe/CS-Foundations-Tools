# tools/gray_code_converter.py

import streamlit as st
from typing import Tuple, List, Optional

# ========================= Core Logic =========================

def binary_to_gray(binary_str: str) -> Tuple[str, List[str]]:
    """
    Convert binary to Gray code: Gray = Binary XOR (Binary >> 1)
    Returns (gray_code, explanation_steps)
    """
    explanation = []

    # Validate binary string
    if not binary_str or not all(c in '01' for c in binary_str):
        return "", ["Error: Input must be a binary string (0s and 1s only)"]

    # Keep the original length (don't strip leading zeros)
    n = len(binary_str)

    explanation.append("### Step 1: Input Binary Number")
    explanation.append(f"Binary: `{binary_str}` ({n} bits)")

    # Compute Binary >> 1 (right shift by 1)
    shifted = '0' + binary_str[:-1]
    explanation.append("### Step 2: Right Shift by 1 Position")
    explanation.append(f"Original:  `{binary_str}`")
    explanation.append(f"Shifted:   `{shifted}`")
    explanation.append("(Insert 0 at the left, drop the rightmost bit)")

    # Compute XOR bit by bit
    explanation.append("### Step 3: XOR Operation (bit by bit)")

    gray_bits = []
    xor_details = []
    for i in range(n):
        b1 = int(binary_str[i])
        b2 = int(shifted[i])
        g = b1 ^ b2
        gray_bits.append(str(g))
        xor_details.append(f"{b1} ⊕ {b2} = {g}")

    gray_str = ''.join(gray_bits)

    # Build the entire code block as one string
    xor_block = f"Binary:  {binary_str}\n"
    xor_block += f"Shifted: {shifted}\n"
    xor_block += f"         {'-' * n}\n"
    xor_block += f"Gray:    {gray_str}"
    explanation.append(f"```\n{xor_block}\n```")

    explanation.append("### Step 4: Bit-by-Bit XOR Details")
    for i, detail in enumerate(xor_details):
        explanation.append(f"- Position {i}: {detail}")

    return gray_str, explanation

def gray_to_binary(gray_str: str) -> Tuple[str, List[str]]:
    """
    Convert Gray code to binary.
    Binary[i] = Gray[i] XOR Binary[i-1], where Binary[0] = Gray[0]
    Returns (binary_code, explanation_steps)
    """
    explanation = []

    # Validate Gray string
    if not gray_str or not all(c in '01' for c in gray_str):
        return "", ["Error: Input must be a Gray code string (0s and 1s only)"]

    # Keep the original length (don't strip leading zeros)
    n = len(gray_str)

    explanation.append("### Step 1: Input Gray Code")
    explanation.append(f"Gray: `{gray_str}` ({n} bits)")

    explanation.append("### Step 2: Decode to Binary")
    explanation.append("Rule: `Binary[i] = Gray[i] ⊕ Binary[i-1]`")
    explanation.append(f"Start with `Binary[0] = Gray[0] = {gray_str[0]}`")

    binary_bits = [gray_str[0]]
    explanation.append("### Step 3: Compute Each Bit")
    explanation.append(f"- Bit 0: Binary[0] = Gray[0] = `{gray_str[0]}`")

    for i in range(1, n):
        prev_binary = int(binary_bits[i-1])
        gray_bit = int(gray_str[i])
        binary_bit = prev_binary ^ gray_bit
        binary_bits.append(str(binary_bit))
        explanation.append(f"- Bit {i}: Binary[{i}] = Gray[{i}] ⊕ Binary[{i-1}] = {gray_bit} ⊕ {prev_binary} = `{binary_bit}`")

    binary_str = ''.join(binary_bits)

    explanation.append("### Step 4: Result")
    explanation.append(f"Binary: `{binary_str}`")

    return binary_str, explanation

def decimal_to_binary_str(decimal_val: int, min_bits: int = 4) -> str:
    """Convert decimal to binary string with minimum bit width."""
    if decimal_val < 0:
        raise ValueError("Only non-negative integers supported")
    binary = bin(decimal_val)[2:]  # Remove '0b' prefix
    # Pad to minimum width
    if len(binary) < min_bits:
        binary = binary.zfill(min_bits)
    return binary

def parse_input(input_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse input as decimal or binary.
    Returns (binary_string, error_message)

    Logic: If input contains digits 2-9, it's decimal. Otherwise it's binary.
    """
    input_str = input_str.strip().replace('_', '').replace(' ', '')

    if not input_str:
        return None, "Input cannot be empty"

    # Check if contains any digit 2-9 (must be decimal)
    if any(c in '23456789' for c in input_str):
        # Must be decimal
        try:
            decimal_val = int(input_str)
            if decimal_val < 0:
                return None, "Only non-negative integers supported"
            binary = decimal_to_binary_str(decimal_val)
            return binary, None
        except ValueError:
            return None, "Invalid decimal number"

    # Only contains 0s and 1s - treat as binary
    if all(c in '01' for c in input_str):
        return input_str, None

    # Contains other characters
    return None, "Input must be a decimal number or binary string (0s and 1s)"

# ========================= Streamlit UI =========================

def render() -> None:
    st.title("Gray Code Converter")

    st.markdown("""
    Convert between **Binary** and **Gray Code** (reflected binary code).

    ### What is Gray Code?
    Gray code is a binary numeral system where **two successive values differ by only one bit**.
    This property is useful in error correction, digital communications, and rotary encoders.

    ### Conversion Formula
    - **Binary → Gray**: `Gray[i] = Binary[i] ⊕ Binary[i+1]`
    - Equivalently: `Gray = Binary XOR (Binary >> 1)`
    """)

    # Conversion mode selector
    mode = st.radio(
        "Conversion Direction",
        ["Binary → Gray Code", "Gray Code → Binary"],
        horizontal=True
    )

    if mode == "Binary → Gray Code":
        st.subheader("Binary → Gray Code")

        col1, col2 = st.columns([2, 1])
        with col1:
            input_str = st.text_input(
                "Enter Binary or Decimal Number",
                value="1011",
                help="Binary: only 0s and 1s (e.g., 1011). Decimal: any digits including 2-9 (e.g., 15)"
            )
        with col2:
            st.markdown("**Examples:**")
            st.caption("Binary: `1011`")
            st.caption("Decimal: `15`")
            st.caption("*Note: `11` = binary, not decimal*")

        if st.button("Convert to Gray Code", key="to_gray"):
            binary_str, error = parse_input(input_str)

            if error:
                st.error(error)
            else:
                # Show parsed input if it was decimal
                if input_str.strip() != binary_str:
                    decimal_val = int(binary_str, 2)
                    st.info(f"Parsed as decimal `{input_str}` = binary `{binary_str}`")

                gray_str, explanation = binary_to_gray(binary_str)

                if gray_str:
                    st.subheader("Result")

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**Binary:**")
                        st.code(binary_str, language=None)
                        decimal_val = int(binary_str, 2)
                        st.caption(f"Decimal: {decimal_val}")

                    with col_b:
                        st.markdown(f"**Gray Code:**")
                        st.code(gray_str, language=None)
                        st.caption(f"Length: {len(gray_str)} bits")

                    st.subheader("Explanation")
                    for step in explanation:
                        st.markdown(step)

                    # Show verification
                    st.markdown("### ✓ Verification: Single-Bit Change Property")
                    st.caption("Gray code ensures adjacent values differ by exactly one bit:")

                    # Show a few adjacent values
                    decimal_val = int(binary_str, 2)
                    if decimal_val > 0:
                        prev_binary = decimal_to_binary_str(decimal_val - 1, len(binary_str))
                        prev_gray, _ = binary_to_gray(prev_binary)
                        diff_prev = sum(1 for i in range(len(gray_str)) if i < len(prev_gray) and gray_str[i] != prev_gray[i])
                        st.markdown(f"- Gray({decimal_val-1}) = `{prev_gray}` → Gray({decimal_val}) = `{gray_str}` (differs in {diff_prev} bit)")

                    if decimal_val < 2**len(binary_str) - 1:
                        next_binary = decimal_to_binary_str(decimal_val + 1, len(binary_str))
                        next_gray, _ = binary_to_gray(next_binary)
                        diff_next = sum(1 for i in range(len(gray_str)) if i < len(next_gray) and gray_str[i] != next_gray[i])
                        st.markdown(f"- Gray({decimal_val}) = `{gray_str}` → Gray({decimal_val+1}) = `{next_gray}` (differs in {diff_next} bit)")
                else:
                    for step in explanation:
                        st.error(step)

    else:  # Gray Code → Binary
        st.subheader("Gray Code → Binary")

        col1, col2 = st.columns([2, 1])
        with col1:
            gray_input = st.text_input(
                "Enter Gray Code",
                value="1110",
                help="Enter a Gray code string (e.g., 1110)"
            )
        with col2:
            st.markdown("**Example:**")
            st.caption("Gray: `1110`")

        if st.button("Convert to Binary", key="to_binary"):
            # Validate Gray code input
            gray_input = gray_input.strip().replace('_', '').replace(' ', '')

            if not gray_input:
                st.error("Input cannot be empty")
            elif not all(c in '01' for c in gray_input):
                st.error("Gray code must contain only 0s and 1s")
            else:
                binary_str, explanation = gray_to_binary(gray_input)

                if binary_str:
                    st.subheader("Result")

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**Gray Code:**")
                        st.code(gray_input, language=None)

                    with col_b:
                        st.markdown(f"**Binary:**")
                        st.code(binary_str, language=None)
                        decimal_val = int(binary_str, 2)
                        st.caption(f"Decimal: {decimal_val}")

                    st.subheader("Explanation")
                    for step in explanation:
                        st.markdown(step)

                    # Verification: convert back
                    st.markdown("### ✓ Verification: Round-trip Conversion")
                    verify_gray, _ = binary_to_gray(binary_str)
                    if verify_gray == gray_input.lstrip('0') or '0':
                        st.success(f"Binary `{binary_str}` converts back to Gray `{verify_gray}` ✓")
                    else:
                        st.warning(f"Round-trip result: `{verify_gray}` (leading zeros may differ)")
                else:
                    for step in explanation:
                        st.error(step)

    # Additional information
    with st.expander("ℹ️ About Gray Code", expanded=False):
        st.markdown("""
        ### Properties
        - **Single-bit change**: Adjacent values differ by exactly one bit
        - **Cyclic**: Last value differs from first by one bit (when wrapping around)
        - **Reflected**: Second half is first half reversed with MSB flipped

        ### Applications
        1. **Rotary Encoders**: Prevents errors during position reading
        2. **Error Correction**: Minimizes errors in transmission
        3. **Analog-to-Digital Converters**: Reduces glitches
        4. **Karnaugh Maps**: Adjacent cells differ by one variable
        5. **Genetic Algorithms**: Smooth mutation operators

        ### Example: 3-bit Gray Code Sequence
        ```
        Decimal | Binary | Gray
        --------|--------|------
           0    |  000   | 000
           1    |  001   | 001
           2    |  010   | 011
           3    |  011   | 010
           4    |  100   | 110
           5    |  101   | 111
           6    |  110   | 101
           7    |  111   | 100
        ```
        Notice: Each row differs from the previous by exactly **one bit** in Gray column.

        ### Mathematical Formula
        **Binary → Gray:**
        ```
        G[i] = B[i] ⊕ B[i+1]  (for i < n-1)
        G[n-1] = B[n-1]
        ```
        Or equivalently: `Gray = Binary XOR (Binary >> 1)`

        **Gray → Binary:**
        ```
        B[0] = G[0]
        B[i] = G[i] ⊕ B[i-1]  (for i > 0)
        ```
        """)