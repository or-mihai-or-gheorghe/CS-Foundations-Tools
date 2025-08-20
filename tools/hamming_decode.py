# tools/hamming_decode.py
#
# Streamlit UI + pure logic for *systematic* Hamming decoding using the
# same “MSB-at-top columns” H you use for encoding.
#
# Method (mod 2 arithmetic):
# 1) Infer p from n = len(codeword): p = |{2^j ≤ n}|.
#    Then k = n - p. Parity positions are powers of two.
# 2) Build H (p×n) where column j (1-based) is the p-bit binary of j,
#    **MSB at the top row** (same “upside down” convention as in the encoder).
# 3) Compute the syndrome s = H · cᵀ (row-wise XOR checks).
# 4) Interpret s:
#    - s = 0 → no error.
#    - s ≠ 0 and equals an existing H column → single-bit error at that column index.
#    - s ≠ 0 and doesn’t equal any existing H column (can happen when n < 2^p - 1) →
#      likely 2+ errors → cannot correct with plain Hamming.
# 5) If correctable, flip that bit; verify s_after = 0; then extract data bits
#    (non-power-of-two positions) to produce the decoded payload.

import streamlit as st
import numpy as np
from typing import Dict, List, Tuple, Optional


# ---------- Utilities (shared style with encoder) ----------

def _to_subscript(s: object) -> str:
    SUBSCRIPT_MAP = {
        '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
        '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'
    }
    return "".join(SUBSCRIPT_MAP.get(ch, ch) for ch in str(s))

def _binary_str(x: int, width: int) -> str:
    return format(x, f"0{width}b")

def _format_matrix(matrix: np.ndarray, name: str) -> str:
    return f"{name} ({matrix.shape[0]}x{matrix.shape[1]}):\n{matrix}"

def _infer_p_from_n(n: int) -> int:
    """Number of parity positions among 1..n (powers of two ≤ n)."""
    p = 0
    while (1 << p) <= n:
        p += 1
    return p

def _positions(n: int, p: int) -> Tuple[List[int], List[int]]:
    parity_positions = [1 << j for j in range(p) if (1 << j) <= n]
    data_positions = [i for i in range(1, n + 1) if i not in parity_positions]
    return parity_positions, data_positions

def _build_H_msb_top(n: int, p: int) -> np.ndarray:
    """
    Build H with p rows and n columns; each column j (1-based) is the p-bit
    binary representation of j with **MSB at the top row**.
    """
    H = np.zeros((p, n), dtype=int)
    for col in range(1, n + 1):
        bits = _binary_str(col, p)  # MSB..LSB
        for r, ch in enumerate(bits):  # r=0 is the top row (MSB)
            H[r, col - 1] = 1 if ch == '1' else 0
    return H

def _xor_list_mod2(bits: List[int]) -> int:
    acc = 0
    for b in bits:
        acc ^= (b & 1)
    return acc


# ---------- Decoding Logic (row-equation method) ----------

def hamming_decode_logic(codeword_bits_str: str) -> Tuple[Optional[Dict[str, object]], Optional[str]]:
    """
    Decode a (possibly corrupted) **systematic** Hamming codeword using the same
    MSB-at-top H construction as the encoder.

    Returns (results, error_message).

    results keys:
      - n, p, k
      - parity_positions, data_positions
      - H
      - c (original), syndrome, syndrome_ok
      - row_equations (each row’s XOR and its result bit)
      - syndrome_int (1-based column index if it matches a column), match_positions
      - decision: {"status": "ok"|"corrected"|"uncorrectable", "explanation": str}
      - error_position (if corrected), c_corrected, syndrome_after
      - data_bits_positions, data_bits, data_bits_str
      - positions_table, columns_desc_str, highlighted_codeword_html, highlighted_corrected_codeword_html
    """
    # Validate
    if not isinstance(codeword_bits_str, str) or len(codeword_bits_str) == 0:
        return None, "Error: Input cannot be empty."
    if not all(c in "01" for c in codeword_bits_str):
        return None, "Error: Input must be a binary string (0/1)."

    # Parameters inferred from the codeword length
    n = len(codeword_bits_str)
    p = _infer_p_from_n(n)
    if p == 0 or n <= p:
        return None, f"Error: Codeword length {n} is too small for Hamming decoding."

    k = n - p
    parity_positions, data_positions = _positions(n, p)

    # Build H (MSB at top), and read codeword
    H = _build_H_msb_top(n, p)
    c = np.array([int(b) for b in codeword_bits_str], dtype=int)

    # ---- Row-by-row computation of s = H · cᵀ (mod 2) ----
    row_equations: List[Dict[str, object]] = []
    for r in range(p):
        selected_positions = [j for j in range(1, n + 1) if H[r, j - 1] == 1]
        selected_values = [int(c[j - 1]) for j in selected_positions]
        s_r = _xor_list_mod2(selected_values)

        pos_list_str = ", ".join(str(j) for j in selected_positions)
        compact = f"Row {r} (MSB row is 0): XOR positions {{{pos_list_str}}} = {s_r}"

        # Human-friendly equation text: e.g., "s₀ = c₁ ⊕ c₃ ⊕ c₅ = 1 ⊕ 0 ⊕ 1 = 0"
        names = [f"c{_to_subscript(j)}" for j in selected_positions]
        vals  = [str(c[j - 1]) for j in selected_positions]
        if names:
            lhs = f"s{_to_subscript(r)}"
            eqn_text = f"{lhs} = " + " ⊕ ".join(names) + "   ⇒   " + f"{lhs} = " + " ⊕ ".join(vals) + f" = {s_r}"
        else:
            eqn_text = f"s{_to_subscript(r)} = 0   (no positions in this row)"

        row_equations.append({
            "row_index": r,
            "selected_positions": selected_positions,
            "equation_text": eqn_text,
            "compact_text": compact,
            "row_sum": s_r,
        })

    # Syndrome via matrix product (sanity-check matches row-by-row sums)
    syndrome = (H @ c) % 2
    if any(eq["row_sum"] != int(syndrome[eq["row_index"]]) for eq in row_equations):
        return None, "Internal error: row-by-row sums disagree with H · cᵀ."

    syndrome_ok = bool((syndrome.sum() == 0))
    syndrome_bits = "".join(str(int(b)) for b in syndrome.tolist())  # MSB..LSB
    syndrome_int = int(syndrome_bits, 2) if not syndrome_ok else 0

    # Match syndrome to one of our **existing** columns (MSB-at-top)
    match_positions = [j for j in range(1, n + 1) if np.array_equal(H[:, j - 1], syndrome)]
    decision: Dict[str, object]
    error_position: Optional[int] = None
    c_corrected = c.copy()
    syndrome_after = None

    if syndrome_ok:
        decision = {
            "status": "ok",
            "explanation": "Syndrome is zero ⇒ no errors detected (H · cᵀ = 0)."
        }
    else:
        if len(match_positions) == 1:
            # Standard single-bit correction
            error_position = match_positions[0]
            c_corrected[error_position - 1] ^= 1
            syndrome_after = (H @ c_corrected) % 2
            if syndrome_after.sum() == 0:
                decision = {
                    "status": "corrected",
                    "explanation": (
                        f"Non-zero syndrome equals column {error_position} ⇒ single-bit error at "
                        f"position {error_position}. Bit flipped; new syndrome is zero."
                    )
                }
            else:
                decision = {
                    "status": "uncertain",
                    "explanation": (
                        "Syndrome matched a column, but post-correction syndrome is still non-zero. "
                        "This suggests multiple errors or inconsistent input."
                    )
                }
        else:
            # No column matches this syndrome (possible with shortened codes), or something is inconsistent.
            decision = {
                "status": "uncorrectable",
                "explanation": (
                    "Detected error (non-zero syndrome), but it does not match any existing column. "
                    "Likely 2 or more flipped bits; plain Hamming (distance 3) cannot correct this. "
                    "Extended Hamming (SECDED) with an overall parity would allow 2-bit detection."
                )
            }

    # Extract data bits from the **final** codeword (corrected if we corrected)
    final_c = c_corrected if decision["status"] in {"corrected", "ok"} else c
    data_bits = [int(final_c[pos - 1]) for pos in data_positions]
    data_bits_str = "".join(str(b) for b in data_bits)

    # ---- Explanations and helpers (mirroring encoder UI) ----
    columns_desc = [f"{col}:{_binary_str(col, p)}" for col in range(1, n + 1)]
    columns_desc_str = " | ".join(columns_desc)

    parity_set = set(parity_positions)
    pos_lines = []
    for pos in range(1, n + 1):
        tag = "P" if pos in parity_set else "D"
        pos_lines.append(f"{pos:>3}  [{_binary_str(pos, p)}]  {tag}")
    positions_table = "pos  [MSB..LSB]  type\n" + "\n".join(pos_lines)

    # Highlight parity positions in original and corrected codewords
    def _highlight_codeword(bits: np.ndarray) -> str:
        parts = []
        for idx, bit in enumerate(bits.tolist(), start=1):
            if idx in parity_set:
                parts.append(f"<span style='color:#FF4B4B;font-weight:700;'>{bit}</span>")
            else:
                parts.append(str(bit))
        return (
            "<div style='font-family:monospace;font-size:1.25rem;'>"
            + " ".join(parts)
            + "</div>"
        )

    highlighted_codeword_html = _highlight_codeword(c)
    highlighted_corrected_codeword_html = _highlight_codeword(final_c)

    results: Dict[str, object] = {
        "n": n, "p": p, "k": k,
        "parity_positions": parity_positions,
        "data_positions": data_positions,
        "H": H,
        "c": c,
        "row_equations": row_equations,
        "syndrome": syndrome,
        "syndrome_ok": syndrome_ok,
        "syndrome_bits": syndrome_bits,
        "syndrome_int": syndrome_int,
        "match_positions": match_positions,
        "decision": decision,
        "error_position": error_position,
        "c_corrected": final_c,
        "syndrome_after": syndrome_after,
        "data_bits_positions": data_positions,
        "data_bits": data_bits,
        "data_bits_str": data_bits_str,
        "columns_desc_str": columns_desc_str,
        "positions_table": positions_table,
        "highlighted_codeword_html": highlighted_codeword_html,
        "highlighted_corrected_codeword_html": highlighted_corrected_codeword_html,
    }
    return results, None


# ---------- Streamlit UI ----------

def render() -> None:
    st.title("Hamming Decoder")

    st.markdown(
        r"""
Decode a **systematic Hamming** codeword using the same MSB-at-top parity-check
matrix \(H\) as in the encoder.

### Rules (mod 2)
1. **Infer p** from codeword length \(n\): powers-of-two positions \(1,2,4,\dots\le n\) are parity; \(p\) is their count, and \(k=n-p\).
2. **Build \(H\)** (\(p\times n\)): column \(j\) is **binary of \(j\)** (1-based) with **MSB at the top row**.
3. **Compute syndrome** \(s = H\cdot c^{\mathsf T}\) by XOR-ing rows.
4. **Interpret \(s\)**:
   - \(s=\mathbf0\): no error,
   - \(s\) equals a column of \(H\): flip that bit (single-error correction),
   - otherwise: likely **2+ errors** → not correctable by plain Hamming.
5. **Extract data** from non-power-of-two positions.
        """
    )

    example = st.text_input("Enter a Hamming codeword (e.g., 0110011 or 1011010):", "1011010")

    if st.button("Decode", key="hamming_decode"):
        st.markdown("---")
        results, error = hamming_decode_logic(example)
        if error:
            st.error(error)
            return

        # 1) Parameters
        st.markdown("### 1) Parameters")
        st.markdown(
            f"- **n (codeword length):** `{results['n']}`  \n"
            f"- **p (parity bits):** `{results['p']}` (powers of two ≤ n)  \n"
            f"- **k (data bits):** `n - p = {results['k']}`  \n"
            f"- **Parity positions:** {results['parity_positions']}  \n"
            f"- **Data positions:** {results['data_positions']}"
        )

        st.markdown("**Codeword (parity bits highlighted):**")
        st.markdown(results["highlighted_codeword_html"], unsafe_allow_html=True)

        # 2) H construction and intuition
        st.markdown("### 2) Build H (MSB-at-top columns)")
        st.markdown("Columns (1-based) shown as MSB..LSB patterns per position:")
        st.code(results["positions_table"])
        st.markdown("Parity-check matrix **H**:")
        st.code(_format_matrix(results["H"], "H"))

        # 3) Show cᵀ and compute H · cᵀ row-by-row
        st.markdown("### 3) Transposed codeword **cᵀ** and row equations")
        SUBSCRIPT_MAP = {'0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅','6':'₆','7':'₇','8':'₈','9':'₉'}
        SUB_TRANS = str.maketrans(SUBSCRIPT_MAP)
        max_label = max(len(str(i)) for i in range(1, results['n'] + 1))
        cT_rows = [f"[c{str(i).translate(SUB_TRANS)} = {int(results['c'][i-1])}]" for i in range(1, results['n']+1)]
        st.code("cᵀ ({n}x1):\n{rows}".format(n=results['n'], rows="\n".join(cT_rows)))

        st.markdown("**Row-by-row XORs (each row produces one syndrome bit):**")
        for eq in results["row_equations"]:
            st.markdown(f"- {eq['compact_text']}")
            st.code(eq["equation_text"])

        # 4) Syndrome analysis
        st.markdown("### 4) Syndrome and analysis")
        st.markdown(f"- **Syndrome vector (MSB..LSB):** `{results['syndrome_bits']}`")
        if results["syndrome_ok"]:
            st.success("Syndrome is zero ⇒ no error detected.")
        else:
            matches = results["match_positions"]
            if len(matches) == 1:
                st.warning(f"Non-zero syndrome matches column **{matches[0]}** ⇒ single-bit error at position **{matches[0]}**.")
            elif len(matches) == 0:
                st.error(
                    "Non-zero syndrome does **not** match any existing column. "
                    "Likely 2+ flipped bits → cannot correct with plain Hamming."
                )
            else:
                st.error("Syndrome matches multiple columns (unexpected) → data inconsistent.")

        # 5) Correction decision and verification
        st.markdown("### 5) Correction decision")
        st.info(results["decision"]["explanation"])
        st.markdown("Codeword **after** possible correction (parity bits highlighted):")
        st.markdown(results["highlighted_corrected_codeword_html"], unsafe_allow_html=True)

        if results["decision"]["status"] in {"corrected", "ok"}:
            st.markdown("Verification: `H · cᵀ` **after** correction:")
            st.code(str(results["syndrome_after"] if results["syndrome_after"] is not None else results["syndrome"]))
            if results["decision"]["status"] == "corrected":
                st.success("Post-correction syndrome is zero ⇒ correction consistent.")
        else:
            st.warning("Leaving codeword unmodified due to uncorrectable/uncertain state.")

        # 6) Extract data bits
        st.markdown("### 6) Extract and assemble the data bits")
        positions = ", ".join(str(p) for p in results["data_positions"])
        st.markdown(f"- **Data positions (non-powers of two):** {positions}")
        st.markdown(f"- **Data bits (in-order):** `{''.join(str(b) for b in results['data_bits'])}`")
        st.success(f"**Decoded payload:** `{results['data_bits_str']}`")

        # 7) Note on 2-bit errors
        st.markdown(
            "> **Note:** With full-length Hamming \((n=2^p-1)\), a 2-bit error can produce a syndrome that "
            "matches another column, causing a *mis-correction*. To reliably detect double errors, use "
            "**extended Hamming (SECDED)** with an overall parity bit."
        )


# (optional) helpers for unit tests
def _decode_return_data_bits(codeword_bits_str: str) -> str:
    """Return only the decoded data bitstring (after correction if applicable)."""
    results, err = hamming_decode_logic(codeword_bits_str)
    if err:
        raise ValueError(err)
    return results["data_bits_str"]

def _decode_return_error_position(codeword_bits_str: str) -> int:
    """Return 0 if no error, or 1-based error position if a single-bit correction was made (else -1)."""
    results, err = hamming_decode_logic(codeword_bits_str)
    if err:
        raise ValueError(err)
    if results["syndrome_ok"]:
        return 0
    if results["decision"]["status"] == "corrected" and results["error_position"] is not None:
        return int(results["error_position"])
    return -1