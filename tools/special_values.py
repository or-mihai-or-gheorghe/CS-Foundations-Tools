# tools/special_values.py

import streamlit as st
from decimal import Decimal, getcontext

# Set precision for Decimal calculations
getcontext().prec = 100

def to_superscript(s):
    """Converts a string to its superscript equivalent."""
    sups = {'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '-': '⁻'}
    return "".join(sups.get(char, char) for char in s)

def get_ieee_754_details(precision):
    """Returns parameters for single or double precision."""
    if precision == 'Single (32-bit)':
        return {'exp_bits': 8, 'man_bits': 23, 'bias': 127, 'total_bits': 32}
    else:  # Double (64-bit)
        return {'exp_bits': 11, 'man_bits': 52, 'bias': 1023, 'total_bits': 64}

def generate_special_value_details(value_type, precision):
    """
    Generates the bit pattern and a rule-based explanation for a given special value.
    """
    params = get_ieee_754_details(precision)
    sign, exponent, mantissa = "", "", ""
    explanation = []
    value = ""

    if value_type == "Positive Infinity":
        sign = '0'
        exponent = '1' * params['exp_bits']
        mantissa = '0' * params['man_bits']
        value = "+Infinity"
        explanation.append("### Rule: Infinity")
        explanation.append("- **Condition:** The exponent field must be all 1s, and the mantissa field must be all 0s.")
        explanation.append("- **Sign Bit:** `0` for Positive Infinity, `1` for Negative Infinity.")
        explanation.append(f"- **Exponent:** `{exponent}` (All 1s)")
        explanation.append(f"- **Mantissa:** `{mantissa}` (All 0s)")

    elif value_type == "Negative Infinity":
        sign = '1'
        exponent = '1' * params['exp_bits']
        mantissa = '0' * params['man_bits']
        value = "-Infinity"
        explanation.append("### Rule: Infinity")
        explanation.append("- **Condition:** The exponent field must be all 1s, and the mantissa field must be all 0s.")
        explanation.append("- **Sign Bit:** `0` for Positive Infinity, `1` for Negative Infinity.")
        explanation.append(f"- **Exponent:** `{exponent}` (All 1s)")
        explanation.append(f"- **Mantissa:** `{mantissa}` (All 0s)")
        
    elif value_type == "Quiet NaN (qNaN)":
        sign = '0' # Can be 1 as well, 0 is a common example
        exponent = '1' * params['exp_bits']
        # Canonical qNaN: first bit of mantissa is 1
        mantissa = '1' + '0' * (params['man_bits'] - 1)
        value = "NaN (Quiet)"
        explanation.append("### Rule: Not a Number (NaN)")
        explanation.append("- **Condition:** The exponent field is all 1s, and the mantissa is **non-zero**.")
        explanation.append("- **Quiet vs. Signaling:** The first bit of the mantissa determines the type. A `1` indicates a Quiet NaN (qNaN).")
        explanation.append("- qNaNs propagate through operations without raising exceptions. They are often the result of invalid operations like `0/0`.")
        explanation.append(f"- **Exponent:** `{exponent}` (All 1s)")
        explanation.append(f"- **Mantissa:** `{mantissa}` (Non-zero, starts with 1)")

    elif value_type == "Signaling NaN (sNaN)":
        sign = '0' # Can be 1 as well
        exponent = '1' * params['exp_bits']
        # Canonical sNaN: first bit is 0, but mantissa is non-zero
        mantissa = '0' + '1' + '0' * (params['man_bits'] - 2)
        value = "NaN (Signaling)"
        explanation.append("### Rule: Not a Number (NaN)")
        explanation.append("- **Condition:** The exponent field is all 1s, and the mantissa is **non-zero**.")
        explanation.append("- **Quiet vs. Signaling:** The first bit of the mantissa determines the type. A `0` (with the rest being non-zero) indicates a Signaling NaN (sNaN).")
        explanation.append("- sNaNs are designed to raise an exception or signal an error when used in an operation.")
        explanation.append(f"- **Exponent:** `{exponent}` (All 1s)")
        explanation.append(f"- **Mantissa:** `{mantissa}` (Non-zero, starts with 0)")

    elif value_type == "Smallest Positive Denormalized Number":
        sign = '0'
        exponent = '0' * params['exp_bits']
        mantissa = '0' * (params['man_bits'] - 1) + '1'
        
        explanation.append("### Rule: Denormalized Number")
        explanation.append("- **Condition:** The exponent field is all 0s, and the mantissa is **non-zero**.")
        explanation.append("- Denormalized numbers allow for **gradual underflow**, representing values that are very close to zero but not exactly zero.")
        explanation.append("- The implicit leading bit for the mantissa is **0** (not 1 as with normalized numbers).")
        explanation.append(f"- **Exponent:** `{exponent}` (All 0s)")
        explanation.append(f"- **Mantissa:** `{mantissa}` (The smallest possible non-zero value)")
        
        # Calculate its value
        actual_exponent = 1 - params['bias']
        mantissa_value = Decimal(2)**(-params['man_bits'])
        final_value = (Decimal(2)**actual_exponent) * mantissa_value
        value = f"{final_value:.2e}" # Display in scientific notation
        
        explanation.append("#### Value Calculation")
        explanation.append("- Formula: `(-1)ˢ * 2¹⁻ᴮⁱᵃˢ * (0.M)`")
        explanation.append(f"- Exponent Value: `1 - {params['bias']} = {actual_exponent}`")
        explanation.append(f"- Mantissa Value: `2{to_superscript(str(-params['man_bits']))} = {mantissa_value}`")
        explanation.append(f"- Final Value: `2{to_superscript(str(actual_exponent))} * {mantissa_value} = {final_value}`")

    # Combine to get full binary string and hex value
    full_binary_string = sign + exponent + mantissa
    hex_representation = f"0x{int(full_binary_string, 2):0{params['total_bits']//4}X}"

    return (sign, exponent, mantissa, hex_representation, value), explanation

def render():
    st.title("Special Values Explorer")
    st.markdown("""
    This tool demonstrates how IEEE 754 represents exceptional values like Infinity, NaN, and denormalized numbers. 
    Select a value to see its binary pattern and the rules that define it.
    """)

    col1, col2 = st.columns(2)
    with col1:
        value_type = st.selectbox(
            "Select a Special Value to Examine:",
            [
                "Positive Infinity",
                "Negative Infinity",
                "Quiet NaN (qNaN)",
                "Signaling NaN (sNaN)",
                "Smallest Positive Denormalized Number"
            ]
        )
    with col2:
        precision = st.radio(
            "Select Precision:",
            ('Single (32-bit)', 'Double (64-bit)'),
            key='precision_special'
        )

    if st.button("Generate Example", key='generate_special'):
        st.markdown("---")
        
        params = get_ieee_754_details(precision)
        
        result, explanation = generate_special_value_details(value_type, precision)

        if result:
            sign, exponent, mantissa, hex_val, value_repr = result
            
            st.subheader("Representation")
            st.info(f"**Value:** {value_repr}")

            col_res1, col_res2 = st.columns(2)
            with col_res1:
                st.markdown("**Sign Bit:**")
                st.code(sign)
                # Now this line will work correctly
                st.markdown(f"**Exponent ({params['exp_bits']} bits):**")
                st.code(exponent)
            with col_res2:
                # And this line will also work correctly
                st.markdown(f"**Mantissa ({params['man_bits']} bits):**")
                st.code(mantissa)
                st.markdown("**Hexadecimal:**")
                st.code(hex_val)

            st.markdown("---")
            st.subheader("Explanation")
            for step in explanation:
                st.markdown(step, unsafe_allow_html=True)