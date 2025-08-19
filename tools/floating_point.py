# tools/floating_point.py

import streamlit as st
# Import the Decimal module for precise calculations
from decimal import Decimal, getcontext

# Set precision for Decimal calculations. 100 digits is more than enough.
getcontext().prec = 100

def get_ieee_754_details(precision):
    """Returns parameters for single or double precision."""
    if precision == 'Single (32-bit)':
        return {'exp_bits': 8, 'man_bits': 23, 'bias': 127, 'total_bits': 32}
    else:  # Double (64-bit)
        return {'exp_bits': 11, 'man_bits': 52, 'bias': 1023, 'total_bits': 64}

def convert_to_ieee754(number_str, precision):
    """
    Converts a decimal number string to its IEEE 754 binary representation
    and provides a detailed, step-by-step explanation.
    """
    try:
        # Check for zero case first
        if float(number_str) == 0.0:
            params = get_ieee_754_details(precision)
            sign_bit = '0'
            exponent_bits = '0' * params['exp_bits']
            mantissa_bits = '0' * params['man_bits']
            hex_representation = f"0x{0:0{params['total_bits']//4}X}"
            converted_back_value = Decimal('0')
            explanation = [
                "**Input Number:** 0.0", "This is a special case.", "**Sign Bit:** 0 (for positive zero)",
                f"**Exponent:** All zeros ({'0'*params['exp_bits']})", f"**Mantissa:** All zeros ({'0'*params['man_bits']})",
                "The IEEE 754 standard defines +0.0 as all zero bits."
            ]
            return (sign_bit, exponent_bits, mantissa_bits, hex_representation, converted_back_value), explanation
    except ValueError:
        return None, ["Error: Invalid input. Please enter a valid number."]

    explanation = []
    params = get_ieee_754_details(precision)

    # Step 1: Determine the Sign Bit
    is_negative = number_str.strip().startswith('-')
    sign_bit = '1' if is_negative else '0'
    
    if is_negative:
        number_str = number_str.strip()[1:] # Work with the absolute value string

    explanation.append(f"### 1. Sign Bit\n- The number is **{'negative' if is_negative else 'positive'}**.")
    explanation.append(f"- Therefore, the sign bit is **{sign_bit}**.")

    # Step 2: Convert to Binary using Decimal for accuracy
    if '.' in number_str:
        integer_str, fractional_str = number_str.split('.')
        integer_part = int(integer_str) if integer_str else 0
        fractional_part = Decimal('0.' + fractional_str)
    else:
        integer_part = int(number_str)
        fractional_part = Decimal('0')

    integer_binary = bin(integer_part)[2:]
    explanation.append(f"### 2. Convert to Binary\n- **Integer Part ({integer_part}):** The binary representation is **{integer_binary}**.")

    if integer_part > 0:
        bits_from_integer_part = len(integer_binary) - 1
    else:
        bits_from_integer_part = 0

    fractional_binary = ""
    temp_frac = fractional_part
    explanation.append(f"- **Fractional Part ({fractional_part}):** We convert this by repeatedly multiplying by 2.")
    
    separator_added = False # Flag to ensure we only add the separator once
    max_frac_bits = params['man_bits'] + 10 # Generate a few extra bits to show truncation
    
    for _ in range(max_frac_bits):
        if temp_frac == 0:
            break
        
        current_mantissa_bits = bits_from_integer_part + len(fractional_binary)
        
        if not separator_added and current_mantissa_bits >= params['man_bits']:
            explanation.append(
                f"> *Note: We now have the required {params['man_bits']} bits for the mantissa. "
                "Any further bits are for illustration and will be truncated.*"
            )
            separator_added = True

        temp_frac *= 2
        bit = int(temp_frac)
        explanation.append(f"  - `{temp_frac/2} * 2 = {temp_frac}` -> The integer part is **{bit}**")
        fractional_binary += str(bit)
        temp_frac -= bit

    combined_binary = f"{integer_binary}.{fractional_binary}"
    explanation.append(f"\n- **Combined Binary:** Putting them together, we get **{combined_binary}**.")

    # Step 3: Normalize the Binary
    if integer_part > 0:
        dot_pos = len(integer_binary) -1
        normalized_mantissa_str = integer_binary[1:] + fractional_binary
        exponent = dot_pos
    else:
        try:
            first_one = fractional_binary.index('1')
            exponent = -(first_one + 1)
            normalized_mantissa_str = fractional_binary[first_one+1:]
        except ValueError:
            exponent = 0
            normalized_mantissa_str = ""

    explanation.append(f"### 3. Normalize the Binary\n- We write the number in scientific notation: `1.mantissa * 2^exponent`.")
    explanation.append(f"- To do this, we move the decimal point. The original binary is `{combined_binary}`.")
    explanation.append(f"- The normalized form is `1.{normalized_mantissa_str} * 2^{exponent}`.")

    # Step 4: Calculate the Biased Exponent
    biased_exponent = exponent + params['bias']
    exponent_binary = bin(biased_exponent)[2:].zfill(params['exp_bits'])

    explanation.append(f"### 4. Calculate the Biased Exponent\n- The precision is **{precision}**, which has a bias of **{params['bias']}**.")
    explanation.append(f"- `Biased Exponent = Actual Exponent + Bias = {exponent} + {params['bias']} = {biased_exponent}`.")
    explanation.append(f"- In {params['exp_bits']}-bit binary, this is **{exponent_binary}**.")

    # Step 5: Determine the Mantissa
    mantissa_bits = (normalized_mantissa_str + '0' * params['man_bits'])[:params['man_bits']]
    explanation.append(f"### 5. Determine the Mantissa\n- The mantissa is the fractional part of the normalized form (`1.{normalized_mantissa_str}`), which is `{normalized_mantissa_str}`.")
    explanation.append(f"- We need **{params['man_bits']}** bits. We take our value and pad with zeros (if needed).")
    explanation.append(f"- After truncating to {params['man_bits']} bits, the final mantissa is **{mantissa_bits}**.")

    # Step 6: Final Hexadecimal Form
    full_binary_string = sign_bit + exponent_binary + mantissa_bits
    binary_as_int = int(full_binary_string, 2)
    hex_representation = f"0x{binary_as_int:0{params['total_bits']//4}X}"
    explanation.append(f"### 6. Final Hexadecimal Form\n- The full binary string is `{full_binary_string}`.")
    explanation.append(f"- Converting this binary to hexadecimal gives **{hex_representation}**.")

    # Convert the binary representation back to decimal for verification
    sign = int(sign_bit)
    
    # Calculate the actual exponent from the biased binary
    actual_exponent = int(exponent_binary, 2) - params['bias']
    
    # Calculate the mantissa value (including the implicit leading 1)
    mantissa_value = Decimal(1)
    for i, bit in enumerate(mantissa_bits):
        if bit == '1':
            mantissa_value += Decimal(2)**-(i + 1)
            
    # The final formula: (-1)^sign * mantissa * 2^exponent
    converted_back_value = (Decimal(-1)**sign) * mantissa_value * (Decimal(2)**actual_exponent)

    return (sign_bit, exponent_binary, mantissa_bits, hex_representation, converted_back_value), explanation

def render():
    """Renders the Floating Point Converter tool in Streamlit."""
    st.title("IEEE 754 Floating-Point Converter")
    st.markdown("""
    This tool demonstrates the conversion of a decimal number into its 
    [IEEE 754](https://en.wikipedia.org/wiki/IEEE_754) floating-point representation,
    explaining each step of the process.
    """)

    # Use a more descriptive default
    number_str = st.text_input("Enter a decimal number (e.g., -56.768):", "-56.768")
    precision = st.radio(
        "Select Precision:",
        ('Single (32-bit)', 'Double (64-bit)'),
        key='precision'
    )

    if st.button("Convert", key='convert_fp'):
        st.markdown("---")
        result, explanation = convert_to_ieee754(number_str, precision)

        if result:
            # --- CHANGE 1: Unpack the new converted_back_value ---
            sign, exponent, mantissa, hex_val, converted_back_value = result
            params = get_ieee_754_details(precision)

            st.subheader("Final Representation")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Sign Bit:**")
                st.code(sign, language=None)
                st.markdown(f"**Exponent ({params['exp_bits']} bits):**")
                st.code(exponent, language=None)
            with col2:
                st.markdown(f"**Mantissa ({params['man_bits']} bits):**")
                st.code(mantissa, language=None)
                st.markdown(f"**Hexadecimal:**")
                st.code(hex_val, language=None)
            
            st.subheader("Full Binary String")
            st.code(f"{sign} {exponent} {mantissa}", language=None)

            # --- CHANGE 2: Add the verification section ---
            st.subheader("Verification")
            
            original_decimal = Decimal(number_str.strip())
            
            st.markdown(f"**Original Value:** `{original_decimal}`")
            st.markdown(f"**Value from Binary:** `{converted_back_value}`")

            # Compare the original with the re-calculated value
            if original_decimal != converted_back_value:
                st.warning(
                    "**Precision Loss:** The value represented by the binary is slightly "
                    "different from the original input. This is because the original number "
                    "cannot be perfectly represented with a finite number of binary digits."
                )

            st.markdown("---")
            st.subheader("Step-by-Step Explanation")
            for step in explanation:
                st.markdown(step, unsafe_allow_html=True)
        else:
            st.error(explanation[0])