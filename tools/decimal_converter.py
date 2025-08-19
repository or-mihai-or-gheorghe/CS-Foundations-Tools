# tools/decimal_converter.py

import streamlit as st
from decimal import Decimal, getcontext

# Set precision for Decimal calculations
getcontext().prec = 100

def get_ieee_754_details(precision):
    """Returns parameters for single or double precision."""
    if precision == 'Single (32-bit)':
        return {'exp_bits': 8, 'man_bits': 23, 'bias': 127, 'total_bits': 32}
    else:  # Double (64-bit)
        return {'exp_bits': 11, 'man_bits': 52, 'bias': 1023, 'total_bits': 64}

def to_superscript(s):
    """Converts a string to its superscript equivalent."""
    sups = {
        '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
        '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '-': '⁻'
    }
    return "".join(sups.get(char, char) for char in s)

def convert_from_ieee754(input_str, input_type, precision):
    """
    Converts an IEEE 754 binary or hex string to a decimal value,
    providing a detailed, step-by-step explanation.
    """
    params = get_ieee_754_details(precision)
    explanation = []

    # Step 1: Validate and convert input to a standard binary string
    input_str = input_str.strip().replace(" ", "")
    binary_str = ""

    if input_type == 'Hexadecimal':
        try:
            if input_str.lower().startswith('0x'):
                input_str = input_str[2:]
            
            expected_hex_len = params['total_bits'] // 4
            if len(input_str) != expected_hex_len:
                return None, [f"Error: Hexadecimal input for {precision} must be exactly {expected_hex_len} characters long."]
            
            binary_str = f"{int(input_str, 16):0{params['total_bits']}b}"
            explanation.append(f"### 1. Convert Input to Binary\n- **Input Hex:** `{input_str}`\n- **Full Binary:** `{binary_str}`")
        except ValueError:
            return None, ["Error: Invalid hexadecimal characters in input."]
    else: # Binary
        if len(input_str) != params['total_bits']:
            return None, [f"Error: Binary input for {precision} must be exactly {params['total_bits']} bits long."]
        if not all(c in '01' for c in input_str):
            return None, ["Error: Binary input must contain only '0' and '1'."]
        binary_str = input_str
        explanation.append(f"### 1. Parse Input Binary\n- **Input Binary:** `{binary_str}`")

    # Step 2: Parse the binary string into its components
    sign_bit = binary_str[0]
    exp_start = 1
    exp_end = 1 + params['exp_bits']
    exponent_bits = binary_str[exp_start:exp_end]
    mantissa_bits = binary_str[exp_end:]

    explanation.append(f"### 2. Deconstruct the Binary String")
    explanation.append(f"- **Sign (S):** `{sign_bit}` → {'Negative (-)' if sign_bit == '1' else 'Positive (+)'}")
    explanation.append(f"- **Exponent (E):** `{exponent_bits}`")
    explanation.append(f"- **Mantissa (M):** `{mantissa_bits}`")

    # Step 3: Analyze the components and calculate the value
    explanation.append("### 3. Analyze and Calculate")
    
    all_exp_ones = '1' * params['exp_bits']
    all_exp_zeros = '0' * params['exp_bits']
    
    # Case 1: Special Values (Infinity and NaN)
    if exponent_bits == all_exp_ones:
        if mantissa_bits == '0' * params['man_bits']:
            explanation.append("- The exponent is all ones and the mantissa is all zeros. This represents **Infinity**.")
            result = "-Infinity" if sign_bit == '1' else "+Infinity"
            return result, explanation
        else:
            explanation.append("- The exponent is all ones and the mantissa is non-zero. This represents **NaN** (Not a Number).")
            return "NaN", explanation

    # Case 2: Denormalized Numbers and Zero
    elif exponent_bits == all_exp_zeros:
        if mantissa_bits == '0' * params['man_bits']:
            explanation.append("- The exponent and mantissa are all zeros. This represents **Zero**.")
            result = "-0.0" if sign_bit == '1' else "+0.0"
            return result, explanation
        else:
            explanation.append("- The exponent is all zeros, but the mantissa is non-zero. This is a **Denormalized Number**.")
            actual_exponent = 1 - params['bias']
            explanation.append(f"- The exponent value for denormalized numbers is `1 - Bias` = `1 - {params['bias']}` = **{actual_exponent}**.")
            mantissa_value = Decimal(0)
            mantissa_calc_str = []
            for i, bit in enumerate(mantissa_bits):
                if bit == '1':
                    power = -(i + 1)
                    value = Decimal(2)**power
                    mantissa_value += value
                    mantissa_calc_str.append(f"2{to_superscript(str(power))}")
            
            explanation.append(f"- The implicit leading bit is **0**. The mantissa value is `0.{mantissa_bits}`.")
            explanation.append(f"- Value = `{' + '.join(mantissa_calc_str)}` = **{mantissa_value}**")
            
            sign = Decimal(-1) if sign_bit == '1' else Decimal(1)
            final_value = sign * (Decimal(2)**actual_exponent) * mantissa_value
            explanation.append("### 4. Final Calculation\n- Formula: `(-1)ˢ * 2¹⁻ᴮⁱᵃˢ * (0.M)`")
            explanation.append(f"- Result: `({-1 if sign_bit == '1' else 1}) * 2{to_superscript(str(actual_exponent))} * {mantissa_value}` = **{final_value}**")
            return final_value, explanation

    # Case 3: Normalized Numbers
    else:
        explanation.append("- The exponent is not all zeros or all ones. This is a **Normalized Number**.")
        biased_exp = int(exponent_bits, 2)
        actual_exponent = biased_exp - params['bias']
        explanation.append(f"- The exponent value is `E - Bias` = `{biased_exp} - {params['bias']}` = **{actual_exponent}**.")
        mantissa_value = Decimal(1)
        mantissa_calc_str = []
        for i, bit in enumerate(mantissa_bits):
            if bit == '1':
                power = -(i + 1)
                value = Decimal(2)**power
                mantissa_value += value
                mantissa_calc_str.append(f"2{to_superscript(str(power))}")
        
        explanation.append(f"- The implicit leading bit is **1**. The mantissa value is `1.{mantissa_bits}`.")
        explanation.append(f"- Value = `1 + {' + '.join(mantissa_calc_str)}` = **{mantissa_value}**")
        
        sign = Decimal(-1) if sign_bit == '1' else Decimal(1)
        final_value = sign * (Decimal(2)**actual_exponent) * mantissa_value
        explanation.append("### 4. Final Calculation\n- Formula: `(-1)ˢ * 2ᴱ⁻ᴮⁱᵃˢ * (1.M)`")
        explanation.append(f"- Result: `({-1 if sign_bit == '1' else 1}) * 2{to_superscript(str(actual_exponent))} * {mantissa_value}` = **{final_value}**")
        
        # Alternative calculation for positive exponents
        if actual_exponent >= 0:
            explanation.append("\n---\n") # Separator
            explanation.append("#### Alternative Method (Point Shifting)")
            explanation.append(f"- Since the exponent is positive ({actual_exponent}), we can find the value by shifting the binary point to the right.")
            
            full_mantissa = '1' + mantissa_bits
            
            # This logic is generic and works because len(mantissa_bits) is either 23 or 52
            if actual_exponent < len(mantissa_bits):
                int_part_bin = full_mantissa[:actual_exponent + 1]
                frac_part_bin = full_mantissa[actual_exponent + 1:]
            else: # Exponent is large, need to pad with zeros
                padding_needed = actual_exponent - len(mantissa_bits)
                int_part_bin = full_mantissa + '0' * padding_needed
                frac_part_bin = ""

            shifted_binary_str = f"{int_part_bin}" + (f".{frac_part_bin}" if frac_part_bin else "")
            explanation.append(f"- `1.{mantissa_bits} * 2{to_superscript(str(actual_exponent))}` becomes `{shifted_binary_str}`.")

            # Calculate integer and fractional decimal values
            int_part_dec = int(int_part_bin, 2)
            explanation.append(f"- **Integer Part:** `{int_part_bin}`₂ = `{int_part_dec}`₁₀")

            frac_part_dec = Decimal(0)
            if frac_part_bin:
                for i, bit in enumerate(frac_part_bin):
                    if bit == '1':
                        frac_part_dec += Decimal(2)**-(i+1)
                explanation.append(f"- **Fractional Part:** `0.{frac_part_bin}`₂ = `{frac_part_dec}`₁₀")
                
                total_abs_val = Decimal(int_part_dec) + frac_part_dec
                explanation.append(f"- **Total Absolute Value:** `{int_part_dec} + {frac_part_dec} = {total_abs_val}`")
            else:
                total_abs_val = Decimal(int_part_dec)
            
            final_signed_val = total_abs_val * (Decimal(-1) if sign_bit == '1' else Decimal(1))
            explanation.append(f"- Applying the sign bit (`{sign_bit}`), the final value is **{final_signed_val}**.")

        return final_value, explanation

def render():
    """Renders the Decimal Converter tool in Streamlit."""
    st.title("Decimal Value Converter")
    st.markdown("""
    This tool converts an IEEE 754 floating-point number (in binary or hex format) 
    back to its decimal representation, explaining each step of the process.
    """)

    col1, col2 = st.columns(2)
    with col1:
        precision = st.radio(
            "Select Precision:",
            ('Single (32-bit)', 'Double (64-bit)'),
            key='precision_dec'
        )
    with col2:
        input_type = st.radio(
            "Select Input Format:",
            ('Binary', 'Hexadecimal'),
            key='input_type',
            horizontal=True
        )

    # Provide a helpful default value based on selection
    if precision == 'Single (32-bit)':
        default_val = "C2630A3D" if input_type == 'Hexadecimal' else "11000010011000110000101000111101"
    else:
        default_val = "404C6147AE147AE1" if input_type == 'Hexadecimal' else "0100000001001100011000010100011110101110000101000111101011100001"
    
    input_str = st.text_input("Enter the value to convert:", default_val)

    if st.button("Convert", key='convert_dec'):
        st.markdown("---")
        result, explanation = convert_from_ieee754(input_str, input_type, precision)

        if result is not None:
            st.subheader("Result")
            st.success(f"**Decimal Value:** {result}")
            
            st.markdown("---")
            st.subheader("Step-by-Step Explanation")
            for step in explanation:
                st.markdown(step, unsafe_allow_html=True)
        else:
            st.error(explanation[0])