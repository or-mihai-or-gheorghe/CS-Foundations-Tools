# tools/hamming_encode.py
#
# Streamlit UI + pure logic for *systematic* Hamming encoding using the
# “row-equations from H · cᵀ = 0” method you requested.
#
# Method (mod 2 arithmetic):
# 1) Choose the smallest p s.t. 2^p >= k + p + 1. Let n = k + p.
# 2) Build an H matrix with p rows and n columns where each column is the **binary
#    representation of its 1-based column index**, **MSB at the top row**.
#    (This is the “upside down” version compared to the LSB-at-top convention.)
# 3) Place data bits in non-parity positions (positions that are NOT powers of two).
# 4) Form the p row equations from H · cᵀ = 0 (one per row):
#    - Row r collects all codeword positions j whose column’s bit r is 1.
#    - Exactly one of those positions is a parity position (a power of two).
#    - That equation therefore has a **single unknown parity bit**, so:
#         p_at_that_position  =  XOR of all **data bits** selected in that row.
# 5) Fill those parity bits back into the codeword; the result c satisfies H · cᵀ = 0.
#
# This is algebraically equivalent to the usual “each parity checks a specific row/bit”
# rule, but we present it **as H · cᵀ = 0** with **one unknown per equation**, as requested.

import streamlit as st
import numpy as np
from typing import Dict, List, Tuple, Optional


# ---------- Utilities ----------

def _to_subscript(s: object) -> str:
    """Converts a number or string of digits to unicode subscript characters."""
    SUBSCRIPT_MAP = {
        '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
        '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'
    }
    return "".join(SUBSCRIPT_MAP.get(char, char) for char in str(s))

def _find_p(k: int) -> int:
    """
    Return the minimal number of parity bits p such that 2^p >= k + p + 1.
    Supports both full and (if needed) shortened Hamming lengths.
    """
    p = 0
    while (1 << p) < (k + p + 1):
        p += 1
    return p


def _positions(n: int, p: int) -> Tuple[List[int], List[int]]:
    """
    Return (parity_positions, data_positions) as 1-based indices.
    Parity positions are powers of two within 1..n.
    """
    parity_positions = [1 << j for j in range(p) if (1 << j) <= n]
    data_positions = [i for i in range(1, n + 1) if i not in parity_positions]
    return parity_positions, data_positions


def _binary_str(x: int, width: int) -> str:
    """Binary string MSB..LSB with fixed width."""
    return format(x, f"0{width}b")


def _format_matrix(matrix: np.ndarray, name: str) -> str:
    return f"{name} ({matrix.shape[0]}x{matrix.shape[1]}):\n{matrix}"


# ---------- Build user-described H (MSB-at-top) ----------

def _build_H_msb_top(n: int, p: int) -> np.ndarray:
    """
    Build H with P rows and N columns; each column j (1-based) is the P-bit
    binary representation of j with **MSB at top row**.

    Example for n=7, p=3 (rows top→bottom are MSB→LSB):
    columns 1..7 are 001, 010, 011, 100, 101, 110, 111.
    """
    H = np.zeros((p, n), dtype=int)
    for col in range(1, n + 1):
        bits = _binary_str(col, p)  # MSB..LSB
        for r, ch in enumerate(bits):  # r=0 top row (MSB)
            H[r, col - 1] = 1 if ch == '1' else 0
    return H


def _xor_list_mod2(bits: List[int]) -> int:
    """XOR-reduce a list of 0/1 ints; empty list → 0."""
    if not bits:
        return 0
    acc = 0
    for b in bits:
        acc ^= (b & 1)
    return acc


# ---------- Encoding Logic (row-equation method) ----------

def hamming_encode_logic(data_bits_str: str) -> Tuple[Optional[Dict[str, object]], Optional[str]]:
    """
    Pure logic function. Performs systematic Hamming encoding by building the
    “upside down” H and solving the parity bits directly from the p equations of
    H · cᵀ = 0. Returns (results, error_message).

    The displayed explanation is **rule-based** and **row-by-row**:
    each row yields one simple equation with one unknown parity bit.
    """
    # Validate input
    if not isinstance(data_bits_str, str) or len(data_bits_str) == 0:
        return None, "Error: Input cannot be empty."
    if not all(c in "01" for c in data_bits_str):
        return None, "Error: Input must be a binary string (0/1)."

    # Parameters
    k = len(data_bits_str)
    p = _find_p(k)
    n = k + p

    parity_positions, data_positions = _positions(n, p)
    d_bits = np.array([int(b) for b in data_bits_str], dtype=int)  # shape (k,)

    # Build H as described (MSB at top)
    H = _build_H_msb_top(n, p)

    # Place data bits into codeword positions (parity bits unknown for now)
    c = np.zeros(n, dtype=int)
    for i, pos in enumerate(data_positions):
        c[pos - 1] = d_bits[i]

    # Helper: map codeword position -> data index (for readable equations)
    pos_to_didx = {pos: i for i, pos in enumerate(data_positions)}  # 0-based data index

    # ---- Rule-based equations from H · cᵀ = 0 (mod 2) ----
    # Row r selects all columns where H[r, j] == 1. Exactly one of those columns
    # is a parity position; call it ppos. Then:
    #    c[ppos] ⊕ (XOR of selected data bits) = 0  ⇒  c[ppos] = XOR(selected data bits)
    row_equations: List[Dict[str, object]] = []
    parity_by_position: Dict[int, int] = {}  # pos -> bit

    for r in range(p):
        selected_positions = [j for j in range(1, n + 1) if H[r, j - 1] == 1]
        parity_in_row = [j for j in selected_positions if j in parity_positions]
        if len(parity_in_row) != 1:
            # For this construction, there must be exactly one parity column per row
            return None, "Internal error: row does not have exactly one parity position."

        ppos = parity_in_row[0]  # the unique parity position for this row
        data_positions_used = [j for j in selected_positions if j not in parity_positions]
        data_bits_used = [int(c[j - 1]) for j in data_positions_used]
        parity_value = _xor_list_mod2(data_bits_used)

        parity_by_position[ppos] = parity_value

        # Build human-friendly equation text with subscripts
        # Example: p₄ = d₂ ⊕ d₃ ⊕ d₄   ⇒   p₄ = 1 ⊕ 0 ⊕ 1 = 0
        lhs = f"p{_to_subscript(ppos)}"
        rhs_terms_names = []
        rhs_terms_vals = []
        for j in data_positions_used:
            didx = pos_to_didx[j]  # 0-based in input string
            rhs_terms_names.append(f"d{_to_subscript(didx + 1)}")
            rhs_terms_vals.append(str(c[j - 1]))

        if rhs_terms_names:
            rhs_names = " ⊕ ".join(rhs_terms_names)
            rhs_vals = " ⊕ ".join(rhs_terms_vals)
            eqn_text = f"{lhs} = {rhs_names}   ⇒   {lhs} = {rhs_vals} = {parity_value}"
        else:
            # No data terms on this row ⇒ parity is 0
            eqn_text = f"{lhs} = 0   (no data terms selected on this row)"

        # Also provide a compact “row sums these positions” view with subscript
        pos_list_str = ", ".join(str(j) for j in selected_positions)
        compact = f"Row {r} (MSB row is 0): XOR positions {{{pos_list_str}}} = 0 ⇒ unknown is p{_to_subscript(ppos)}."

        row_equations.append({
            "row_index": r,
            "parity_position": ppos,
            "selected_positions": selected_positions,
            "data_positions_used": data_positions_used,
            "equation_text": eqn_text,
            "compact_text": compact,
            "computed_parity": parity_value,
        })

    # Fill parity bits into codeword
    for pos, bit in parity_by_position.items():
        c[pos - 1] = bit

    # Verify H · cᵀ = 0
    syndrome = (H @ c) % 2
    syndrome_ok = bool((syndrome.sum() == 0))

    # ---- Explanations and helpful tables ----

    # Show columns of H as col#:bits (MSB..LSB)
    columns_desc = []
    for col in range(1, n + 1):
        columns_desc.append(f"{col}:{_binary_str(col, p)}")
    columns_desc_str = " | ".join(columns_desc)

    # Positions helper table (P for parity, D for data)
    parity_set = set(parity_positions)
    pos_lines = []
    for pos in range(1, n + 1):
        tag = "P" if pos in parity_set else "D"
        pos_lines.append(f"{pos:>3}  [{_binary_str(pos, p)}]  {tag}")
    positions_table = "pos  [MSB..LSB]  type\n" + "\n".join(pos_lines)

    # Highlight parity bits in the final codeword
    highlighted_parts = []
    for idx, bit in enumerate(c.tolist(), start=1):
        if idx in parity_set:
            highlighted_parts.append(f"<span style='color:#FF4B4B;font-weight:700;'>{bit}</span>")
        else:
            highlighted_parts.append(str(bit))
    highlighted_codeword_html = (
        "<div style='font-family:monospace;font-size:1.25rem;'>"
        + " ".join(highlighted_parts)
        + "</div>"
    )

    # Map parity positions to the row that solved them (top row is r=0)
    parity_row_map = {eq["parity_position"]: eq["row_index"] for eq in row_equations}

    # Results package (no exposed H-splitting; everything is driven by row equations)
    results: Dict[str, object] = {
        "k": k,
        "p": p,
        "n": n,
        "parity_positions": parity_positions,
        "data_positions": data_positions,
        "H": H,
        "d_bits": d_bits,
        "row_equations": row_equations,
        "parity_by_position": parity_by_position,           # {position: bit}
        "parity_positions_ordered_bits": [parity_by_position[pos] for pos in parity_positions],
        "parity_row_map": parity_row_map,                   # {position: row_index}
        "codeword": c,
        "syndrome": syndrome,
        "syndrome_ok": syndrome_ok,
        "columns_desc_str": columns_desc_str,
        "highlighted_codeword_html": highlighted_codeword_html,
        "positions_table": positions_table,
    }
    return results, None


# ---------- Streamlit UI ----------

def render() -> None:
    st.title("Hamming Encoder")

    st.markdown(
        """
    This tool encodes data with a systematic **Hamming code** by solving the parity bits
    **directly from the equations** of the parity-check system $H \\cdot c^{\\mathsf T} = 0$.

    ### Rules used (mod 2)
    1. **Pick p**: the smallest integer with $2^p \\ge k + p + 1$. Then $n = k + p$.
    2. **Build H** (p×n): column *j* equals the **binary of j (1-based)** with **MSB at the top row**.
    - For $n = 7, p = 3$, columns are: `001, 010, 011, 100, 101, 110, 111` (top→bottom = MSB→LSB).
    3. **Place data** in the non-power-of-two positions. Positions $1,2,4,\\dots$ are parity.
    4. **Form p equations** from $H \\cdot c^{\\mathsf T} = 0$ (one per row):
    - Row *r* XORs all codeword positions whose column has bit *r* = 1.
    - Exactly **one** of those positions is a parity position $\\Rightarrow$ the row equation has **one unknown**.
    - Solve that row for its parity:
        $$ p(\\text{parity position in row }r) = \\bigoplus \\text{(row-selected data bits)}. $$
    5. Fill those parity bits back into the codeword. By construction, $H \\cdot c^{\\mathsf T} = 0$.
        """
    )

    data_bits_str = st.text_input("Enter a binary data string (e.g., 1011):", "1011")

    if st.button("Encode", key="hamming_encode"):
        st.markdown("---")
        results, error = hamming_encode_logic(data_bits_str)

        if error:
            st.error(error)
            return

        # 1) Parameters
        st.markdown("### 1) Parameters")
        st.markdown(
            f"- **k (data bits):** `{results['k']}`  \n"
            f"- **p (parity bits):** `{results['p']}` (smallest p with 2^p ≥ k + p + 1)  \n"
            f"- **n (codeword length):** `k + p = {results['n']}`  \n"
            f"- **Parity positions (powers of two):** {results['parity_positions']}  \n"
            f"- **Data positions:** {results['data_positions']}"
        )

        st.markdown("**Initial codeword structure (data bits placed, parity bits unknown):**")
        
        # Create a mapping from data position to the actual data bit
        data_map = {pos: bit for pos, bit in zip(results['data_positions'], results['d_bits'])}
        
        # Build the list of parts for the initial codeword display
        initial_codeword_parts = []
        parity_set = set(results['parity_positions'])
        for i in range(1, results['n'] + 1):
            if i in parity_set:
                # Placeholder for unknown parity bits, styled like the final ones
                part = f"<span style='color:#FF4B4B;font-weight:700;'>p<sub>{i}</sub></span>"
                initial_codeword_parts.append(part)
            else:
                # Data bit
                part = str(data_map[i])
                initial_codeword_parts.append(part)
        
        # Assemble into the final HTML string with the same styling as the final codeword
        initial_codeword_html = (
            "<div style='font-family:monospace;font-size:1.25rem;'>"
            + " ".join(initial_codeword_parts)
            + "</div>"
        )
        
        st.markdown(initial_codeword_html, unsafe_allow_html=True)        

        # 2) H construction and intuition
        st.markdown("### 2) Build H (MSB-at-top columns)")
        st.markdown(
            "Each column equals the binary of its **1-based** index (MSB at the top row). "
            "Below shows the MSB..LSB pattern per position:"
        )
        st.code(results["positions_table"])
        st.markdown("Parity-check matrix **H**:")
        st.code(_format_matrix(results["H"], "H"))

        # Helper for unicode subscripts, defined locally for simple insertion
        SUBSCRIPT_MAP = {
            '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
            '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'
        }
        SUB_TRANS = str.maketrans(SUBSCRIPT_MAP)

        st.markdown("Transposed codeword **cᵀ**:")
        # Build the vector rows
        c_transpose_rows = []
        parity_set = set(results['parity_positions'])
        data_map = {pos: bit for pos, bit in zip(results['data_positions'], results['d_bits'])}

        for i in range(1, results['n'] + 1):
            if i in parity_set:
                label = f"p{str(i).translate(SUB_TRANS)}"
                c_transpose_rows.append(label)
            else:
                label = str(data_map[i])
                c_transpose_rows.append(label)
        
        # Find max width for alignment and format the matrix string
        max_width = max(len(s) for s in c_transpose_rows)
        formatted_rows = [f"[{s:^{max_width}}]" for s in c_transpose_rows]
        c_transpose_str = "cᵀ ({n}x1):\n{matrix}".format(
            n=results['n'],
            matrix="\n".join(formatted_rows)
        )
        st.code(c_transpose_str)       

        # 3) Place data and form H · cᵀ = 0
        st.markdown("### 3) Form the row equations from H · cᵀ = 0")
        st.markdown(
            "We put your data bits in the non-parity positions. For each row *r*, we XOR all "
            "positions where the row has a 1. Exactly one of those positions is a parity slot, "
            "so that row solves that parity immediately."
        )

        st.markdown("**Row-by-row equations (each solves exactly one parity bit):**")
        for eq in results["row_equations"]:
            st.markdown(f"- {eq['compact_text']}")
            st.code(eq["equation_text"])

        # 4) Parity values by position
        st.markdown("### 4) Parity values by position")
        pretty_parity = ", ".join([
            f"p{_to_subscript(pos)} = {bit}" 
            for pos, bit in sorted(results["parity_by_position"].items())
        ])
        st.markdown(f"**{pretty_parity}**")

        # 5) Assemble and verify
        st.markdown("### 5) Final codeword and verification")
        st.markdown("Codeword (parity bits highlighted):")
        st.markdown(results["highlighted_codeword_html"], unsafe_allow_html=True)
        st.markdown("Syndrome `H · cᵀ` (should be all zeros):")
        st.code(str(results["syndrome"]))
        if results["syndrome_ok"]:
            st.success("Syndrome is zero ⇒ H · cᵀ = 0. Encoding is consistent.")
        else:
            st.error("Non-zero syndrome (unexpected). Please report this.")


# (optional) expose a small helper for external unit tests
def _encode_return_codeword(data_bits_str: str) -> str:
    """Return just the final codeword string for quick tests."""
    results, err = hamming_encode_logic(data_bits_str)
    if err:
        raise ValueError(err)
    return "".join(str(b) for b in results["codeword"].tolist())