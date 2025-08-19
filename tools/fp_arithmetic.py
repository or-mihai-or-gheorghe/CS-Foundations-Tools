# tools/fp_arithmetic.py

import streamlit as st
from decimal import Decimal, getcontext
# Import the converter from our other tool to reuse its logic
from .floating_point import convert_to_ieee754, get_ieee_754_details

getcontext().prec = 150  # Use high precision for intermediate calculations

def to_superscript(s):
    sups = {'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹', '-': '⁻'}
    return "".join(sups.get(char, char) for char in s)

def _parse_input_to_fp_parts(input_str, precision, input_type):
    """Helper to get (sign, exponent, mantissa) from any input type."""
    params = get_ieee_754_details(precision)
    
    if input_type == 'Decimal':
        # Reuse our existing converter but ignore its explanation
        result, _ = convert_to_ieee754(input_str, precision)
        if not result: return None
        # Unpack result, ignoring hex and back-converted value
        sign, exp, man, _, _ = result
        return sign, exp, man

    input_str = input_str.strip().replace(" ", "")
    binary_str = ""
    if input_type == 'Hexadecimal':
        try:
            if input_str.lower().startswith('0x'): input_str = input_str[2:]
            expected_len = params['total_bits'] // 4
            if len(input_str) != expected_len: return None
            binary_str = f"{int(input_str, 16):0{params['total_bits']}b}"
        except ValueError: return None
    else:  # Binary
        if len(input_str) != params['total_bits']: return None
        if not all(c in '01' for c in input_str): return None
        binary_str = input_str

    sign = binary_str[0]
    exponent = binary_str[1:1 + params['exp_bits']]
    mantissa = binary_str[1 + params['exp_bits']:]
    return sign, exponent, mantissa

def add_binary_strings(a, b, width):
    """Add two binary strings with proper carry handling."""
    # Pad to same width
    a = a.zfill(width)
    b = b.zfill(width)
    
    result = []
    carry = 0
    
    # Add from right to left
    for i in range(width - 1, -1, -1):
        bit_sum = int(a[i]) + int(b[i]) + carry
        result.append(str(bit_sum % 2))
        carry = bit_sum // 2
    
    # Add final carry if present
    if carry:
        result.append('1')
    
    return ''.join(reversed(result))

def subtract_binary_strings(a, b, width):
    """Subtract b from a using two's complement."""
    # Pad to same width
    a = a.zfill(width)
    b = b.zfill(width)
    
    # Two's complement of b: invert bits and add 1
    b_inverted = ''.join('1' if bit == '0' else '0' for bit in b)
    b_twos = add_binary_strings(b_inverted, '1', width)
    
    # Add a and two's complement of b
    result = add_binary_strings(a, b_twos, width)
    
    # If result is longer than width, we have overflow - take only the lower bits
    if len(result) > width:
        return result[-width:], False  # No borrow
    return result, True  # Borrow occurred

def perform_fp_addition(num_a_str, num_b_str, precision, input_type):
    """
    Performs floating-point addition with correct IEEE 754 semantics.
    """
    explanation = []
    params = get_ieee_754_details(precision)
    bias = params['bias']

    # --- Step 1: Deconstruct Inputs ---
    explanation.append("### 1. Deconstruct Input Numbers")
    parts_a = _parse_input_to_fp_parts(num_a_str, precision, input_type)
    parts_b = _parse_input_to_fp_parts(num_b_str, precision, input_type)

    if not parts_a or not parts_b:
        return None, ["Error: One or both inputs are invalid. Please check their format and length."]

    sign_a, exp_a, man_a = parts_a
    sign_b, exp_b, man_b = parts_b
    
    exp_a_val = int(exp_a, 2)
    exp_b_val = int(exp_b, 2)
    
    # Check for special values
    exp_max = (1 << params['exp_bits']) - 1
    
    # Handle special cases
    is_a_zero = exp_a_val == 0 and int(man_a, 2) == 0
    is_b_zero = exp_b_val == 0 and int(man_b, 2) == 0
    is_a_inf = exp_a_val == exp_max and int(man_a, 2) == 0
    is_b_inf = exp_b_val == exp_max and int(man_b, 2) == 0
    is_a_nan = exp_a_val == exp_max and int(man_a, 2) != 0
    is_b_nan = exp_b_val == exp_max and int(man_b, 2) != 0
    
    explanation.append(f"**Number A:**")
    explanation.append(f"- Sign: `{sign_a}` ({'+' if sign_a == '0' else '-'})")
    explanation.append(f"- Exponent: `{exp_a}` (biased value: {exp_a_val}, actual: {exp_a_val - bias if exp_a_val != 0 else 1 - bias})")
    explanation.append(f"- Mantissa: `{man_a}`")
    if is_a_zero: explanation.append("- **Special: Zero**")
    elif is_a_inf: explanation.append("- **Special: Infinity**")
    elif is_a_nan: explanation.append("- **Special: NaN**")
    elif exp_a_val == 0: explanation.append("- **Special: Denormalized**")
    
    explanation.append(f"\n**Number B:**")
    explanation.append(f"- Sign: `{sign_b}` ({'+' if sign_b == '0' else '-'})")
    explanation.append(f"- Exponent: `{exp_b}` (biased value: {exp_b_val}, actual: {exp_b_val - bias if exp_b_val != 0 else 1 - bias})")
    explanation.append(f"- Mantissa: `{man_b}`")
    if is_b_zero: explanation.append("- **Special: Zero**")
    elif is_b_inf: explanation.append("- **Special: Infinity**")
    elif is_b_nan: explanation.append("- **Special: NaN**")
    elif exp_b_val == 0: explanation.append("- **Special: Denormalized**")

    # Handle special value arithmetic
    if is_a_nan or is_b_nan:
        explanation.append("\n### Result: NaN")
        explanation.append("Any operation with NaN produces NaN.")
        return ('0', '1' * params['exp_bits'], '1' + '0' * (params['man_bits'] - 1)), explanation
    
    if is_a_inf or is_b_inf:
        if is_a_inf and is_b_inf and sign_a != sign_b:
            explanation.append("\n### Result: NaN")
            explanation.append("∞ - ∞ is undefined, producing NaN.")
            return ('0', '1' * params['exp_bits'], '1' + '0' * (params['man_bits'] - 1)), explanation
        explanation.append("\n### Result: Infinity")
        final_sign = sign_a if is_a_inf else sign_b
        return (final_sign, '1' * params['exp_bits'], '0' * params['man_bits']), explanation
    
    if is_a_zero:
        explanation.append("\n### Result: B")
        explanation.append("Adding zero returns the other operand.")
        return (sign_b, exp_b, man_b), explanation
    
    if is_b_zero:
        explanation.append("\n### Result: A")
        explanation.append("Adding zero returns the other operand.")
        return (sign_a, exp_a, man_a), explanation

    # --- Step 2: Prepare Mantissas ---
    explanation.append("\n### 2. Prepare Mantissas with Implicit Leading Bit")
    
    # Add implicit leading bit (1 for normalized, 0 for denormalized)
    if exp_a_val == 0:  # Denormalized
        man_a_full = '0' + man_a
        effective_exp_a = 1 - bias  # Denormalized numbers have effective exponent of 1-bias
        explanation.append(f"- A is denormalized: mantissa = `0.{man_a}`, effective exponent = {effective_exp_a}")
    else:  # Normalized
        man_a_full = '1' + man_a
        effective_exp_a = exp_a_val - bias
        explanation.append(f"- A is normalized: mantissa = `1.{man_a}`, effective exponent = {effective_exp_a}")
    
    if exp_b_val == 0:  # Denormalized
        man_b_full = '0' + man_b
        effective_exp_b = 1 - bias
        explanation.append(f"- B is denormalized: mantissa = `0.{man_b}`, effective exponent = {effective_exp_b}")
    else:  # Normalized
        man_b_full = '1' + man_b
        effective_exp_b = exp_b_val - bias
        explanation.append(f"- B is normalized: mantissa = `1.{man_b}`, effective exponent = {effective_exp_b}")

    # --- Step 3: Align Mantissas ---
    explanation.append("\n### 3. Align Mantissas")
    
    # We need to align based on actual exponents
    if exp_a_val == 0 and exp_b_val == 0:
        # Both denormalized, same exponent
        exp_diff = 0
        target_exp = 0
        target_exp_unbiased = 1 - bias
    elif exp_a_val == 0:
        # A denormalized, B normalized
        exp_diff = exp_b_val - 1
        target_exp = exp_b_val
        target_exp_unbiased = effective_exp_b
    elif exp_b_val == 0:
        # B denormalized, A normalized
        exp_diff = 1 - exp_a_val
        target_exp = exp_a_val
        target_exp_unbiased = effective_exp_a
    else:
        # Both normalized
        exp_diff = exp_a_val - exp_b_val
        target_exp = max(exp_a_val, exp_b_val)
        target_exp_unbiased = max(effective_exp_a, effective_exp_b)
    
    # Extend mantissas with guard, round, and sticky bits
    guard_bits = 3  # Guard, Round, Sticky
    man_a_extended = man_a_full + '0' * guard_bits
    man_b_extended = man_b_full + '0' * guard_bits
    
    if exp_diff > 0:  # A's exponent is larger
        shift_amount = exp_diff
        explanation.append(f"- A's exponent ({effective_exp_a}) is larger than B's ({effective_exp_b}) by {shift_amount}")
        explanation.append(f"- Shift B's mantissa RIGHT by {shift_amount} positions")
        
        # Shift B right
        if shift_amount >= len(man_b_extended):
            man_b_shifted = '0' * len(man_b_extended)
            sticky = '1'  # All bits shifted out
        else:
            shifted_out = man_b_extended[-shift_amount:] if shift_amount > 0 else ''
            man_b_shifted = ('0' * shift_amount) + man_b_extended[:-shift_amount]
            sticky = '1' if '1' in shifted_out else '0'
            if sticky == '1' and shift_amount > guard_bits:
                # Set sticky bit in the result
                man_b_shifted = man_b_shifted[:-1] + '1'
        
        man_a_aligned = man_a_extended
        man_b_aligned = man_b_shifted
        
    elif exp_diff < 0:  # B's exponent is larger
        shift_amount = -exp_diff
        explanation.append(f"- B's exponent ({effective_exp_b}) is larger than A's ({effective_exp_a}) by {shift_amount}")
        explanation.append(f"- Shift A's mantissa RIGHT by {shift_amount} positions")
        
        # Shift A right
        if shift_amount >= len(man_a_extended):
            man_a_shifted = '0' * len(man_a_extended)
            sticky = '1'
        else:
            shifted_out = man_a_extended[-shift_amount:] if shift_amount > 0 else ''
            man_a_shifted = ('0' * shift_amount) + man_a_extended[:-shift_amount]
            sticky = '1' if '1' in shifted_out else '0'
            if sticky == '1' and shift_amount > guard_bits:
                man_a_shifted = man_a_shifted[:-1] + '1'
        
        man_a_aligned = man_a_shifted
        man_b_aligned = man_b_extended
        
    else:  # Same exponent
        explanation.append("- Exponents are equal, no alignment needed")
        man_a_aligned = man_a_extended
        man_b_aligned = man_b_extended
    
    explanation.append(f"- Aligned mantissa A: `{man_a_aligned[0]}.{man_a_aligned[1:]}`")
    explanation.append(f"- Aligned mantissa B: `{man_b_aligned[0]}.{man_b_aligned[1:]}`")

    # --- Step 4: Add or Subtract ---
    explanation.append("\n### 4. Perform Addition/Subtraction")
    
    if sign_a == sign_b:
        # Same sign: add magnitudes
        explanation.append(f"- Same signs: Add the mantissas")
        result_mantissa = add_binary_strings(man_a_aligned, man_b_aligned, len(man_a_aligned))
        result_sign = sign_a
        operation = "addition"
    else:
        # Different signs: subtract magnitudes
        explanation.append(f"- Different signs: Subtract the mantissas")
        
        # Determine which is larger in magnitude
        if man_a_aligned > man_b_aligned:
            result_mantissa, _ = subtract_binary_strings(man_a_aligned, man_b_aligned, len(man_a_aligned))
            result_sign = sign_a
            explanation.append(f"- |A| > |B|, so result sign = {'+' if sign_a == '0' else '-'}")
        elif man_b_aligned > man_a_aligned:
            result_mantissa, _ = subtract_binary_strings(man_b_aligned, man_a_aligned, len(man_b_aligned))
            result_sign = sign_b
            explanation.append(f"- |B| > |A|, so result sign = {'+' if sign_b == '0' else '-'}")
        else:
            # Equal magnitudes, result is zero
            explanation.append("- |A| = |B|, result is zero")
            return ('0', '0' * params['exp_bits'], '0' * params['man_bits']), explanation
        operation = "subtraction"
    
    explanation.append(f"- Raw result: `{result_mantissa}`")

    # --- Step 5: Normalize ---
    explanation.append("\n### 5. Normalize the Result")
    
    # Find position of leading 1
    leading_one_pos = result_mantissa.find('1')
    
    if leading_one_pos == -1:
        # Result is zero
        explanation.append("- Result is zero")
        return ('0', '0' * params['exp_bits'], '0' * params['man_bits']), explanation
    
    # Check for overflow (carry out)
    if len(result_mantissa) > len(man_a_aligned):
        # Overflow: shift right by 1
        explanation.append("- Overflow detected (carry bit set)")
        explanation.append("- Shift mantissa RIGHT by 1 and increment exponent")
        result_mantissa = result_mantissa[:-1]  # Remove the last bit
        target_exp += 1
        leading_one_pos = 0
    
    # Normalize: shift so leading 1 is at position 0
    if leading_one_pos > 0:
        # Need to shift left
        shift_left = leading_one_pos
        explanation.append(f"- Leading 1 at position {leading_one_pos}")
        explanation.append(f"- Shift mantissa LEFT by {shift_left} and decrement exponent by {shift_left}")
        result_mantissa = result_mantissa[shift_left:] + ('0' * shift_left)
        target_exp -= shift_left
    elif leading_one_pos == 0:
        explanation.append("- Mantissa already normalized (leading 1 at position 0)")
    
    # Check for underflow/overflow
    if target_exp <= 0:
        # Underflow to denormalized or zero
        explanation.append(f"- Exponent {target_exp} underflows")
        if target_exp < (1 - params['man_bits']):
            # Complete underflow to zero
            explanation.append("- Complete underflow: result rounds to zero")
            return ('0', '0' * params['exp_bits'], '0' * params['man_bits']), explanation
        else:
            # Denormalized result
            denorm_shift = 1 - target_exp
            explanation.append(f"- Result is denormalized, shift right by {denorm_shift}")
            result_mantissa = ('0' * denorm_shift) + result_mantissa[:-denorm_shift]
            target_exp = 0
    elif target_exp >= exp_max:
        # Overflow to infinity
        explanation.append(f"- Exponent {target_exp} overflows")
        explanation.append("- Result rounds to infinity")
        return (result_sign, '1' * params['exp_bits'], '0' * params['man_bits']), explanation

    # --- Step 6: Round ---
    explanation.append("\n### 6. Round to Fit Precision")
    
    # Extract the final mantissa (without implicit bit) and guard bits
    if target_exp == 0:
        # Denormalized: no implicit bit to remove
        final_mantissa = result_mantissa[0:params['man_bits']]
        guard_round_sticky = result_mantissa[params['man_bits']:params['man_bits']+3] if len(result_mantissa) > params['man_bits'] else '000'
    else:
        # Normalized: remove implicit leading 1
        final_mantissa = result_mantissa[1:params['man_bits']+1]
        guard_round_sticky = result_mantissa[params['man_bits']+1:params['man_bits']+4] if len(result_mantissa) > params['man_bits']+1 else '000'
    
    # Pad if necessary
    final_mantissa = (final_mantissa + '0' * params['man_bits'])[:params['man_bits']]
    
    # Round to nearest even
    if len(guard_round_sticky) >= 2:
        guard = guard_round_sticky[0] if len(guard_round_sticky) > 0 else '0'
        round_bit = guard_round_sticky[1] if len(guard_round_sticky) > 1 else '0'
        sticky = '1' if '1' in guard_round_sticky[2:] else '0' if len(guard_round_sticky) > 2 else '0'
        
        explanation.append(f"- Guard bit: {guard}, Round bit: {round_bit}, Sticky bit: {sticky}")
        
        # Round to nearest, ties to even
        if round_bit == '1' and (sticky == '1' or (sticky == '0' and guard == '0' and final_mantissa[-1] == '1')):
            explanation.append("- Rounding up")
            # Add 1 to mantissa
            mantissa_int = int(final_mantissa, 2) + 1
            if mantissa_int >= (1 << params['man_bits']):
                # Mantissa overflow after rounding
                target_exp += 1
                final_mantissa = '0' * params['man_bits']
                explanation.append("- Rounding caused mantissa overflow, increment exponent")
            else:
                final_mantissa = format(mantissa_int, f'0{params["man_bits"]}b')
        else:
            explanation.append("- No rounding needed")

    # --- Step 7: Assemble Result ---
    explanation.append("\n### 7. Assemble Final Result")
    
    final_exp = format(target_exp, f'0{params["exp_bits"]}b')
    
    explanation.append(f"- Sign: `{result_sign}` ({'+' if result_sign == '0' else '-'})")
    explanation.append(f"- Exponent: `{final_exp}` (biased value: {target_exp})")
    explanation.append(f"- Mantissa: `{final_mantissa}`")
    
    return (result_sign, final_exp, final_mantissa), explanation


def render():
    st.title("Floating-Point Arithmetic")
    st.markdown("""
    This tool demonstrates IEEE 754 floating-point addition/subtraction with proper handling of:
    - Denormalized numbers
    - Special values (Zero, Infinity, NaN)
    - Guard, round, and sticky bits for accurate rounding
    - Overflow and underflow conditions
    """)

    col1, col2 = st.columns(2)
    with col1:
        precision = st.radio("Select Precision:", ('Single (32-bit)', 'Double (64-bit)'), key='precision_arith')
    with col2:
        input_type = st.radio("Select Input Format:", ('Decimal', 'Binary', 'Hexadecimal'), key='input_type_arith')

    st.markdown("---")
    
    col_a, col_b = st.columns(2)
    with col_a:
        num_a_str = st.text_input("Number A", "12.75")
    with col_b:
        num_b_str = st.text_input("Number B", "-3.5")
    
    if st.button("Calculate", key='calculate_arith'):
        st.markdown("---")
        result, explanation = perform_fp_addition(num_a_str, num_b_str, precision, input_type)

        if result:
            sign, exponent, mantissa = result
            params = get_ieee_754_details(precision)
            full_binary = f"{sign}{exponent}{mantissa}"
            hex_val = f"0x{int(full_binary, 2):0{params['total_bits']//4}X}"

            st.subheader("Final Result")
            st.markdown(f"**Full Binary:**")
            st.code(f"{sign} {exponent} {mantissa}")
            st.markdown(f"**Hexadecimal:**")
            st.code(hex_val)

            # Convert back to decimal for verification
            exp_val = int(exponent, 2)
            man_val = int(mantissa, 2)
            
            if exp_val == 0 and man_val == 0:
                decimal_result = 0.0
            elif exp_val == (1 << params['exp_bits']) - 1:
                if man_val == 0:
                    decimal_result = float('inf') if sign == '0' else float('-inf')
                else:
                    decimal_result = float('nan')
            else:
                if exp_val == 0:
                    # Denormalized
                    significand = man_val / (1 << params['man_bits'])
                    decimal_result = (-1 if sign == '1' else 1) * significand * (2 ** (1 - params['bias']))
                else:
                    # Normalized
                    significand = 1 + (man_val / (1 << params['man_bits']))
                    decimal_result = (-1 if sign == '1' else 1) * significand * (2 ** (exp_val - params['bias']))
            
            st.markdown(f"**Decimal Value:** `{decimal_result}`")

            st.markdown("---")
            st.subheader("Step-by-Step Explanation")
            for step in explanation:
                st.markdown(step)
        else:
            st.error(explanation[0])