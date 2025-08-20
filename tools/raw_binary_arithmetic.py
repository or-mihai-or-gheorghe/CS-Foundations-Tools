# tools/raw_binary_arithmetic.py

import streamlit as st
from typing import Tuple, List, Optional, Dict

# --- Input Validation ---

def _clean_binary_input(s: str) -> Tuple[Optional[str], Optional[str]]:
    """Strips whitespace and validates if the string is binary."""
    cleaned = s.strip().replace(" ", "").replace("_", "")
    if not cleaned:
        return None, "Input cannot be empty."
    if not all(c in '01' for c in cleaned):
        return None, "Input must contain only '0' and '1'."
    return cleaned, None

# --- Core Arithmetic Logic & Explanation Generation ---

def _add_binary_core(a_str: str, b_str: str) -> Tuple[Dict[str, str], List[str]]:
    """Performs binary addition and generates a step-by-step explanation."""
    explanation = ["### 1. Setup"]
    max_len = max(len(a_str), len(b_str))
    a = a_str.zfill(max_len)
    b = b_str.zfill(max_len)
    
    # Initialize carry vector with spaces (one extra position for potential final carry)
    carry_vector = [' '] * (max_len + 1)
    
    # Initial display - properly aligned
    initial_display = []
    initial_display.append("We align both numbers to the right, padding with zeros as needed.")
    initial_display.append("")  # Empty line for spacing
    initial_display.append(''.join(carry_vector))  # Empty carry line
    initial_display.append(f" {a}")  # Space for alignment, then first number
    initial_display.append(f"+{b}")   # Plus sign and second number
    initial_display.append("-" * (max_len + 1))
    initial_display.append(' ' * (max_len + 1))  # Empty result line
    
    explanation.append("```\n" + "\n".join(initial_display) + "\n```")
    
    explanation.append("### 2. Column-by-Column Addition (Right to Left)")
    
    result = [' '] * max_len  # Initialize result with spaces
    carry = 0
    step_number = 0  # Track step number (1-based)
    
    for i in range(max_len - 1, -1, -1):
        step_number += 1  # Increment step counter
        bit_a = int(a[i])
        bit_b = int(b[i])
        
        col_sum = bit_a + bit_b + carry
        sum_bit = col_sum % 2
        new_carry = col_sum // 2
        
        # Update result at current position
        result[i] = str(sum_bit)
        
        # Update carry vector if there's a carry out
        # Using the user's formula: carry_vector[len(carry_vector) - 1 - step_number]
        # This places the carry above the column that will receive it
        if new_carry == 1 and step_number < max_len:
            carry_position = len(carry_vector) - 1 - step_number
            carry_vector[carry_position] = '1'
        
        # Create current state display with explanation as first line
        current_display = []
        current_display.append(f"Column {step_number}: {bit_a} + {bit_b} + {carry} = {col_sum} → sum bit = {sum_bit}, carry = {new_carry}")
        current_display.append("")  # Empty line for spacing
        current_display.append(''.join(carry_vector))
        current_display.append(f" {a}")
        current_display.append(f"+{b}")
        current_display.append("-" * (max_len + 1))
        
        # Build partial result string (show only computed digits)
        partial_result = ' '  # Leading space for alignment
        for j in range(max_len):
            if j < i:
                partial_result += ' '  # Not computed yet
            else:
                partial_result += result[j]
        current_display.append(partial_result)
        
        # Add position indicator - should be under the current column
        indicator = ' ' * (i + 1) + '^'  # Spaces then caret
        current_display.append(indicator)
        
        explanation.append("```\n" + "\n".join(current_display) + "\n```")
        
        carry = new_carry
    
    # Handle final carry if exists
    if carry:
        carry_vector[0] = '1'
        result = ['1'] + result
        explanation.append("\n**Final Carry:** A carry of `1` is prepended to the result.")
    
    final_result_str = "".join(result).strip()
    
    # Final display
    explanation.append("\n### 3. Final Result")
    final_display = []
    final_display.append("Complete addition with all carries:")
    final_display.append("")  # Empty line for spacing
    # Show final carry state
    final_display.append(''.join(carry_vector))
    final_display.append(f" {a}")
    final_display.append(f"+{b}")
    final_display.append("-" * (max_len + 1))
    final_display.append(f"{final_result_str.rjust(max_len + 1)}")
    
    explanation.append("```\n" + "\n".join(final_display) + "\n```")
    
    explanation.append(f"\n**Answer:** `{a_str} + {b_str} = {final_result_str}`")
    
    # Build the full trace for the results dict
    full_trace_lines = []
    full_trace_lines.append(''.join(carry_vector))
    full_trace_lines.extend([
        f" {a}",
        f"+{b}",
        "-" * (max_len + 1),
        f"{final_result_str.rjust(max_len + 1)}"
    ])
    full_trace = "\n".join(full_trace_lines)
    
    results_dict = {
        "result": final_result_str,
        "full_trace": full_trace
    }
    return results_dict, explanation

def _subtract_binary_core(a_str: str, b_str: str) -> Tuple[Dict[str, str], List[str]]:
    """Performs binary subtraction (A - B) and generates an explanation."""
    explanation = ["This tool performs subtraction on unsigned magnitudes."]
    
    # Ensure A >= B for simplicity. If not, compute B-A and add a negative sign.
    val_a = int(a_str, 2)
    val_b = int(b_str, 2)
    
    if val_a < val_b:
        explanation.append(f"Since {val_a} < {val_b}, we will compute `{b_str} - {a_str}` and prepend a negative sign to the result.")
        results, inner_explanation = _subtract_binary_core(b_str, a_str)
        results["result"] = "-" + results["result"]
        return results, explanation + inner_explanation

    explanation.append("### 1. Align the Numbers")
    max_len = len(a_str)
    a = a_str
    b = b_str.zfill(max_len)
    
    explanation.append("Pad the subtrahend (B) with leading zeros.")
    explanation.append(f"```\n  {a}\n- {b}\n-------\n```")

    explanation.append("### 2. Subtract Column by Column (Right to Left)")
    result = []
    borrow = 0
    
    for i in range(max_len - 1, -1, -1):
        bit_a = int(a[i])
        bit_b = int(b[i])
        
        # Apply borrow from previous column
        bit_a -= borrow
        
        if bit_a < bit_b:
            bit_a += 2  # Borrow from the left
            borrow = 1
            col_explanation = (f"**Column {max_len - 1 - i}:**\n"
                               f"- `({int(a[i])} - {1 if i < max_len-1 else 0}) < {bit_b}`. We need to **borrow**.\n"
                               f"- `({bit_a+borrow}) - {bit_b} = {bit_a - bit_b}`. Result bit is `{bit_a - bit_b}`.")

        else:
            borrow = 0
            col_explanation = (f"**Column {max_len - 1 - i}:**\n"
                               f"- `({int(a[i])} - {1 if i < max_len-1 and int(a[i+1]) < int(b[i+1]) else 0}) >= {bit_b}`. No borrow needed.\n"
                               f"- `{bit_a} - {bit_b} = {bit_a - bit_b}`. Result bit is `{bit_a - bit_b}`.")

        diff_bit = bit_a - bit_b
        result.insert(0, str(diff_bit))
        explanation.append(col_explanation)
    
    final_result_str = "".join(result).lstrip('0') or '0'
    
    explanation.append("### 3. Final Result")
    explanation.append(f"```\n  {a}\n- {b}\n" + "-" * (max_len + 2) + f"\n  {final_result_str.zfill(max_len)}\n```")

    results_dict = {"result": final_result_str}
    return results_dict, explanation

def _multiply_binary_core(a_str: str, b_str: str) -> Tuple[Dict[str, str], List[str]]:
    """Performs binary multiplication and generates an explanation."""
    explanation = ["### 1. Setup Long Multiplication"]
    explanation.append("We multiply `A` by each bit of `B`, creating shifted partial products.")
    
    trace = [f"  {a_str.zfill(len(a_str) + len(b_str))}", f"x {b_str.zfill(len(a_str) + len(b_str))}", "-" * (len(a_str) + len(b_str) + 2)]
    
    partial_products = []
    for i, bit_b in enumerate(reversed(b_str)):
        shift = i
        if bit_b == '1':
            product = a_str + '0' * shift
            explanation.append(f"- Multiplier bit at position {i} is `1`. Partial product is `{a_str}` shifted left by {i}: `{product}`")
        else:
            product = '0' * (len(a_str) + shift)
            explanation.append(f"- Multiplier bit at position {i} is `0`. Partial product is all zeros: `{product}`")
        
        partial_products.append(product)
        trace.append(f"  {product.zfill(len(a_str) + len(b_str))}")

    explanation.append("\n### 2. Sum the Partial Products")
    explanation.append("Now, we add all the partial products together.")
    trace.append("-" * (len(a_str) + len(b_str) + 2))
    
    total = "0"
    for p in partial_products:
        add_result, _ = _add_binary_core(total, p)
        total = add_result["result"]
    
    trace.append(f"  {total.zfill(len(a_str) + len(b_str))}")
    explanation.append(f"The sum of all partial products gives the final answer.")

    results_dict = {"result": total}
    return results_dict, explanation

def _divide_binary_core(a_str: str, b_str: str) -> Tuple[Optional[Dict[str, str]], List[str]]:
    """Performs binary division and generates an explanation."""
    if int(b_str, 2) == 0:
        return None, ["Error: Division by zero is not allowed."]

    explanation = ["### 1. Setup Long Division"]
    val_a = int(a_str, 2)
    val_b = int(b_str, 2)
    
    if val_a < val_b:
        explanation.append(f"Since the dividend (`{a_str}`) is smaller than the divisor (`{b_str}`), the result is straightforward:")
        explanation.append("- **Quotient:** `0`")
        explanation.append(f"- **Remainder:** `{a_str}`")
        return {"quotient": "0", "remainder": a_str}, explanation
    
    explanation.append(f"We will perform long division for `{a_str} / {b_str}`.")
    
    quotient = ""
    remainder = ""
    
    dividend_bits = list(a_str)
    
    explanation.append("\n### 2. Step-by-Step Division")
    
    current_chunk = ""
    steps_trace = []
    
    for i, bit in enumerate(dividend_bits):
        current_chunk += bit
        steps_trace.append(f"**Step {i+1}: Bring down bit '{bit}'**")
        steps_trace.append(f"- Current dividend chunk: `{current_chunk}`")
        
        if int(current_chunk, 2) >= val_b:
            quotient += '1'
            steps_trace.append(f"- Chunk `{current_chunk}` >= Divisor `{b_str}`. Quotient bit is `1`.")
            sub_result, _ = _subtract_binary_core(current_chunk, b_str)
            new_chunk = sub_result["result"]
            steps_trace.append(f"- Subtract: `{current_chunk} - {b_str} = {new_chunk}`. This is the new remainder.")
            current_chunk = new_chunk
        else:
            quotient += '0'
            steps_trace.append(f"- Chunk `{current_chunk}` < Divisor `{b_str}`. Quotient bit is `0`.")
    
    remainder = current_chunk or "0"
    quotient = quotient.lstrip('0') or "0"

    explanation.extend(steps_trace)
    
    explanation.append("\n### 3. Final Result")
    explanation.append("After processing all bits of the dividend:")
    
    results_dict = {"quotient": quotient, "remainder": remainder}
    return results_dict, explanation

def render() -> None:
    """Renders the Raw Binary Arithmetic tool in Streamlit."""
    st.title("Raw Binary Arithmetic")
    st.markdown("""
    This tool performs basic arithmetic operations on **unsigned** binary integers, 
    providing a detailed, column-by-column breakdown of the process, similar to how you would do it by hand.
    """)

    # --- Inputs ---
    col1, col2 = st.columns(2)
    with col1:
        num_a_str = st.text_input("Binary Number A", "1101") # 13
    with col2:
        num_b_str = st.text_input("Binary Number B", "101")  # 5
    
    operation = st.radio(
        "Select Operation:",
        ('Addition', 'Subtraction', 'Multiplication', 'Division'),
        key='binary_op',
        horizontal=True
    )
    
    if st.button("Calculate", key='calc_binary_raw'):
        # --- Input Validation ---
        a_clean, err_a = _clean_binary_input(num_a_str)
        b_clean, err_b = _clean_binary_input(num_b_str)

        if err_a:
            st.error(f"Error in Number A: {err_a}")
            return
        if err_b:
            st.error(f"Error in Number B: {err_b}")
            return

        results = None
        explanation = []

        # --- Call the appropriate core function ---
        if operation == 'Addition':
            results, explanation = _add_binary_core(a_clean, b_clean)
        elif operation == 'Subtraction':
            results, explanation = _subtract_binary_core(a_clean, b_clean)
        elif operation == 'Multiplication':
            results, explanation = _multiply_binary_core(a_clean, b_clean)
        elif operation == 'Division':
            results, explanation = _divide_binary_core(a_clean, b_clean)

        # --- Display Results and Explanation ---
        if results is None:
            st.error(explanation[0] if explanation else "An unknown error occurred.")
            return

        st.subheader("Result")
        if operation == 'Division':
            st.success(f"**Quotient:** `{results['quotient']}`")
            st.info(f"**Remainder:** `{results['remainder']}`")
        else:
            st.success(f"**Result:** `{results['result']}`")

        st.subheader("Step-by-Step Explanation")
        for step in explanation:
            st.markdown(step, unsafe_allow_html=True)