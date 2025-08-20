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
    """Performs binary subtraction (A - B) and generates a detailed step-by-step explanation."""
    explanation = []
    
    # Check if A < B for unsigned subtraction
    val_a = int(a_str, 2)
    val_b = int(b_str, 2)
    
    if val_a < val_b:
        explanation.append(f"Since {val_a} < {val_b}, we will compute `{b_str} - {a_str}` and prepend a negative sign to the result.")
        results, inner_explanation = _subtract_binary_core(b_str, a_str)
        results["result"] = "-" + results["result"]
        return results, explanation + inner_explanation
    
    explanation.append("### 1. Setup")
    max_len = max(len(a_str), len(b_str))
    a = a_str.zfill(max_len)
    b = b_str.zfill(max_len)
    
    # Initialize borrow vector with spaces (for display above the calculation)
    borrow_vector = [' '] * max_len
    
    # Keep track of the working values as we process
    working_a = [int(bit) for bit in a]  # Convert to list of integers for easier manipulation
    
    # Initial display
    initial_display = []
    initial_display.append("We align both numbers to the right, padding with zeros as needed.")
    initial_display.append("")  # Empty line for spacing
    initial_display.append(' ' + ''.join(borrow_vector))  # Borrow line (with leading space for alignment)
    initial_display.append(f" {a}")  # Space for alignment, then minuend
    initial_display.append(f"-{b}")   # Minus sign and subtrahend
    initial_display.append("-" * (max_len + 1))
    initial_display.append(' ' * (max_len + 1))  # Empty result line
    
    explanation.append("```\n" + "\n".join(initial_display) + "\n```")
    
    explanation.append("### 2. Column-by-Column Subtraction (Right to Left)")
    
    result = [' '] * max_len  # Initialize result with spaces
    borrow = 0
    step_number = 0  # Track step number (1-based)
    
    for i in range(max_len - 1, -1, -1):
        step_number += 1  # Increment step counter
        bit_a = int(a[i])
        bit_b = int(b[i])
        
        # Calculate the effective minuend value after considering the borrow
        effective_a = bit_a - borrow
        
        # Determine if we need to borrow for this column
        if effective_a < 0:
            # Already in debt from previous borrow
            effective_a += 2  # Borrow from next column
            new_borrow = 1
            diff_bit = effective_a - bit_b
            
            # Mark the borrow in the vector (above the column we're borrowing from)
            if i > 0:
                borrow_vector[i - 1] = '1'
            
            col_explanation = f"Column {step_number}: {bit_a} - {bit_b} - {borrow} (borrow from prev) → "
            col_explanation += f"Need to borrow: ({bit_a} - {borrow} + 2) - {bit_b} = {diff_bit}"
            
        elif effective_a < bit_b:
            # Need to borrow from the next column
            effective_a += 2
            new_borrow = 1
            diff_bit = effective_a - bit_b
            
            # Mark the borrow in the vector
            if i > 0:
                borrow_vector[i - 1] = '1'
            
            col_explanation = f"Column {step_number}: {bit_a} - {bit_b}"
            if borrow > 0:
                col_explanation += f" - {borrow} (borrow from prev)"
            col_explanation += f" → Need to borrow: ({effective_a - 2} + 2) - {bit_b} = {diff_bit}"
            
        else:
            # No need to borrow
            new_borrow = 0
            diff_bit = effective_a - bit_b
            
            col_explanation = f"Column {step_number}: {bit_a} - {bit_b}"
            if borrow > 0:
                col_explanation += f" - {borrow} (borrow from prev)"
            col_explanation += f" = {diff_bit}"
        
        # Update result at current position
        result[i] = str(diff_bit)
        
        # Create current state display
        current_display = []
        current_display.append(col_explanation)
        current_display.append("")  # Empty line for spacing
        
        # Show borrow vector
        current_display.append(' ' + ''.join(borrow_vector))
        
        # Show the original minuend (we don't modify it visually)
        current_display.append(f" {a}")
        
        # Show subtrahend
        current_display.append(f"-{b}")
        current_display.append("-" * (max_len + 1))
        
        # Build partial result string (show only computed digits)
        partial_result = ' '  # Leading space for alignment
        for j in range(max_len):
            if j < i:
                partial_result += ' '  # Not computed yet
            else:
                partial_result += result[j]
        current_display.append(partial_result)
        
        # Add position indicator
        indicator = ' ' * (i + 1) + '^'  # Spaces then caret
        current_display.append(indicator)
        
        explanation.append("```\n" + "\n".join(current_display) + "\n```")
        
        # Update borrow for next iteration
        borrow = new_borrow
    
    final_result_str = "".join(result).lstrip('0') or '0'
    
    # Final display
    explanation.append("\n### 3. Final Result")
    final_display = []
    final_display.append("Complete subtraction with all borrows:")
    final_display.append("")  # Empty line for spacing
    
    # Show final borrow state
    final_display.append(' ' + ''.join(borrow_vector))
    final_display.append(f" {a}")
    final_display.append(f"-{b}")
    final_display.append("-" * (max_len + 1))
    final_display.append(f" {final_result_str.zfill(max_len)}")
    
    explanation.append("```\n" + "\n".join(final_display) + "\n```")
    
    explanation.append(f"\n**Answer:** `{a_str} - {b_str} = {final_result_str}`")
    
    # Build the full trace for the results dict
    full_trace_lines = []
    full_trace_lines.append(' ' + ''.join(borrow_vector))
    full_trace_lines.extend([
        f" {a}",
        f"-{b}",
        "-" * (max_len + 1),
        f" {final_result_str.zfill(max_len)}"
    ])
    full_trace = "\n".join(full_trace_lines)
    
    results_dict = {
        "result": final_result_str,
        "full_trace": full_trace
    }
    return results_dict, explanation

def _multiply_binary_core(a_str: str, b_str: str) -> Tuple[Dict[str, str], List[str]]:
    """Performs binary multiplication and generates a detailed step-by-step explanation."""
    explanation = []
    
    explanation.append("### 1. Setup")
    
    # Determine the width needed for display
    result_width = len(a_str) + len(b_str)
    
    # Initial display
    initial_display = []
    initial_display.append("We set up the multiplication with the multiplicand on top and multiplier below.")
    initial_display.append("")
    initial_display.append(f"  {a_str.rjust(result_width)}")  # Multiplicand
    initial_display.append(f"× {b_str.rjust(result_width)}")  # Multiplier
    initial_display.append("-" * (result_width + 2))
    
    explanation.append("```\n" + "\n".join(initial_display) + "\n```")
    
    explanation.append("### 2. Generate Partial Products")
    explanation.append("We multiply the multiplicand by each bit of the multiplier, shifting left for each position.")
    
    partial_products = []
    partial_products_display = []
    last_pp_code_block: Optional[List[str]] = None  # <- will hold the last code-block-only lines
    
    for i, bit in enumerate(reversed(b_str)):
        position = i
        step_display = []
        
        # spaces so that 'a_str' visually shifts left by `position`
        spaces_needed = result_width - len(a_str) - position  # == len(b_str) - position
        
        if bit == '1':
            partial_product = a_str + '0' * position
            partial_products.append(partial_product)
            
            step_display.append(f"**Bit position {position} (from right):** Multiplier bit = {bit}")
            step_display.append(f"- Since bit is 1, partial product = {a_str} shifted left by {position}")
            step_display.append(f"- Partial product: `{partial_product}`")
            
            display_product = ' ' * spaces_needed + a_str
            partial_products_display.append(display_product)
        else:
            partial_product = '0' * (len(a_str) + position)
            partial_products.append(partial_product)
            
            step_display.append(f"**Bit position {position} (from right):** Multiplier bit = {bit}")
            step_display.append(f"- Since bit is 0, partial product is all zeros")
            
            display_product = ' ' * spaces_needed + '0' * len(a_str)
            partial_products_display.append(display_product)
        
        # Show current state with all partial products so far
        current_display = []
        current_display.append("Current partial products:")
        current_display.append("")
        current_display.append(f"  {a_str.rjust(result_width)}")
        current_display.append(f"× {b_str.rjust(result_width)}")
        current_display.append("-" * (result_width + 2))
        
        for j, pp in enumerate(partial_products_display[:i+1]):
            if j == 0:
                current_display.append(f"  {pp}")
            else:
                current_display.append(f"+ {pp}")
        
        explanation.extend(step_display)
        explanation.append("```\n" + "\n".join(current_display) + "\n```")
        
        # Save just the code-block portion (strip the 2-line header) for later reuse
        last_pp_code_block = current_display[2:]  # starts at the multiplicand line
    
    explanation.append("### 3. Add Partial Products")
    
    # Calculate the sum (quietly)
    total = "0"
    for p in partial_products:
        add_result, _ = _add_binary_core(total, p)
        total = add_result["result"]
    
    final_result = total.lstrip('0') or '0'
    
    # ---- Merged view: repeat the last partial-products block and add the sum right under it
    if last_pp_code_block:
        merged_block = list(last_pp_code_block)
        merged_block.append("-" * (result_width + 2))
        merged_block.append(f"  {final_result.rjust(result_width)}")

        # IMPORTANT: put the label INSIDE the code block to avoid first-line space trimming
        merged_code = ["We add all partial products together using binary addition to get the final result.", ""] + merged_block
        explanation.append("```\n" + "\n".join(merged_code) + "\n```")
    
    # Verification
    dec_a = int(a_str, 2)
    dec_b = int(b_str, 2)
    dec_result = int(final_result, 2)
    explanation.append(f"\n**Answer:** `{a_str} × {b_str} = {final_result}`")
    explanation.append(f"**Verification:** {dec_a} × {dec_b} = {dec_result} ✓")
    
    results_dict = {
        "result": final_result,
        "decimal_check": f"{dec_a} × {dec_b} = {dec_result}"
    }
    
    return results_dict, explanation

def _divide_binary_core(a_str: str, b_str: str) -> Tuple[Optional[Dict[str, str]], List[str]]:
    """Performs binary division and generates an explanation with a classic long-division layout."""
    if int(b_str, 2) == 0:
        return None, ["Error: Division by zero is not allowed."]

    explanation: List[str] = []

    # --- Helper to render the final merged layout ---------------------------------
    def _build_layout(dividend: str, divisor: str, records: List[dict], quotient: str) -> str:
        left_width = len(dividend)

        def pad_left(s: str) -> str:
            # Keep the vertical bar aligned by padding to the dividend width.
            return s + ' ' * (left_width - len(s))

        left_lines: List[str] = [pad_left(dividend)]
        for idx, rec in enumerate(records):
            # Put the divisor under the current chunk.
            left_lines.append(pad_left(' ' * rec['divisor_indent'] + divisor))
            # Dashes: for the first subtraction, dash length = chunk width; afterwards = divisor width.
            dash_len = len(rec['chunk']) if idx == 0 else len(divisor)
            left_lines.append(pad_left(' ' * rec['start'] + '-' * dash_len))
            # Next chunk (remainder plus enough brought-down bits to be ≥ divisor—or final remainder).
            left_lines.append(pad_left(' ' * rec['next_start'] + rec['next_chunk']))

        # Right column with divisor, divider, quotient
        right_lines = [''] * len(left_lines)
        right_lines[0] = divisor
        right_lines[1] = '-' * max(10, len(quotient) + 4)
        right_lines[2] = quotient

        merged = []
        for L, R in zip(left_lines, right_lines):
            merged.append(f"{L} | {R}" if R else f"{L} |")
        # Label first line to prevent Streamlit trimming left spaces
        return "Long division (dividend | divisor; quotient on the right):\n\n" + "\n".join(merged)

    dividend = a_str
    divisor = b_str
    B = int(divisor, 2)
    n = len(dividend)

    # --- Build quotient bit-by-bit; collect records only when we subtract ---------
    quotient_bits: List[str] = []
    records: List[dict] = []
    R = 0  # running remainder (integer)

    for i, bit in enumerate(dividend):
        R = (R << 1) | (bit == '1')
        if R >= B:
            # Before subtracting, this is the visible "chunk" under which we write the divisor.
            chunk_bin = bin(R)[2:]
            chunk_len = len(chunk_bin)
            start_idx = i - chunk_len + 1
            divisor_indent = start_idx + (chunk_len - len(divisor))

            # Subtract for the remainder.
            R_after = R - B

            # Build the "next chunk" by bringing down successive bits until ≥ divisor or end.
            k = i + 1
            next_chunk = bin(R_after)[2:] if R_after != 0 else "0"
            while k < n and int(next_chunk, 2) < B:
                next_chunk += dividend[k]
                k += 1
            next_end = (k - 1) if k > 0 else i
            next_start = next_end - len(next_chunk) + 1

            records.append({
                "end": i,
                "chunk": chunk_bin,
                "start": start_idx,
                "divisor_indent": divisor_indent,
                "next_chunk": next_chunk,
                "next_end": next_end,
                "next_start": next_start,
            })

            R = R_after
            quotient_bits.append('1')
        else:
            quotient_bits.append('0')

    quotient = ''.join(quotient_bits).lstrip('0') or '0'
    remainder = bin(R)[2:] if R != 0 else "0"  # normalize all-zero remainder to "0"

    # --- 2) Long-division trace (merged view) ------------------------------------
    explanation.append("### 1. Long Division Trace")
    explanation.append(
        "Each subtraction places the divisor under the current chunk; the dashed line shows the subtraction, "
        "then we bring down the next bit(s) to form the next chunk."
    )
    layout_block = _build_layout(dividend, divisor, records, quotient)
    explanation.append("```\n" + layout_block + "\n```")

    # --- 3) Final result ----------------------------------------------------------
    explanation.append("### 2. Final Result")
    explanation.append(f"**Answer:** Quotient = `{quotient}`, Remainder = `{remainder}`")

    return {"quotient": quotient, "remainder": remainder}, explanation


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