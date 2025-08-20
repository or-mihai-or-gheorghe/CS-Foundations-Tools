# tools/crc_decode.py
#
# Streamlit UI + pure logic for CRC decoding with rule-based (LaTeX) explanations.
# Supports:
#   - variable-length received bits (codeword or noisy codeword),
#   - preset short generator polynomials,
#   - custom generator given as MSB→LSB binary (e.g., "10011" for x^4 + x + 1),
#   - optional long-division trace over GF(2),
#   - optional single-bit auto-correction (exhaustive search).
#
# Model (no reflection, init=0, xorout=0):
#   Given generator G(x) of degree r and received vector R(x) (length n),
#   let k = n - r. The leftmost k bits are the message guess, the last r bits
#   are the received check (remainder) bits in the textbook systematic form.
#
#   1) Compute the syndrome S(x) = R(x) mod G(x) via long division in GF(2).
#   2) If S(x) = 0, codeword is valid and message = R[0:k].
#   3) If S(x) ≠ 0, an error is detected; optionally try single-bit correction
#      by flipping each bit and checking divisibility by G(x).
#
# Verification step divides the (possibly corrected) vector by G(x) and shows
# the remainder is 0^r.

import streamlit as st
import numpy as np
from typing import Dict, List, Tuple, Optional

# ---------- Bit & polynomial helpers ----------

def _clean_bits(s: str) -> str:
    """Remove spaces/underscores and keep only binary chars."""
    return "".join(ch for ch in s if ch in "01")

def _bits_str_to_array(bits: str) -> np.ndarray:
    return np.array([int(b) for b in bits], dtype=int)

def _array_to_bits_str(a: np.ndarray) -> str:
    return "".join(str(int(b)) for b in a.tolist())

def _poly_bits_to_terms(bits: str) -> List[int]:
    """
    Return descending exponents present in a polynomial given as MSB→LSB bits.
    Example: "10011" -> [4, 1, 0]  (x^4 + x + 1)
    """
    n = len(bits)
    exps = []
    for i, b in enumerate(bits):
        if b == "1":
            exps.append((n - 1) - i)
    return exps

def _poly_terms_to_latex(exps: List[int], name: str = "G") -> str:
    if not exps:
        return fr"{name}(x)=0"
    parts = []
    for e in exps:
        if e == 0:
            parts.append("1")
        elif e == 1:
            parts.append("x")
        else:
            parts.append(fr"x^{{{e}}}")
    return fr"{name}(x)= " + " + ".join(parts)

def _group_bits(s: str, group: int = 4) -> str:
    if group <= 0:
        return s
    return " ".join(s[i:i+group] for i in range(0, len(s), group))

# ---------- CRC long division over GF(2) ----------

def _crc_divide(dividend_bits: np.ndarray, gen_bits: np.ndarray, trace: bool = False) -> Tuple[np.ndarray, List[str]]:
    """
    Perform polynomial long-division in GF(2):
      dividend_bits: received vector (any length n)
      gen_bits: generator, length r+1, MSB=1
    Returns: remainder (length r), and an optional textual trace.
    """
    work = dividend_bits.copy()
    n = len(work)
    g_len = len(gen_bits)
    r = g_len - 1
    k = n - r  # number of positions we slide over

    steps: List[str] = []
    for i in range(max(0, k)):
        if work[i] == 1:
            before = _array_to_bits_str(work[i:i+g_len]) if trace else ""
            work[i:i+g_len] ^= gen_bits
            after = _array_to_bits_str(work[i:i+g_len]) if trace else ""
            if trace:
                steps.append(
                    f"i={i:>3}: lead 1 ⇒ XOR gen → slice[{i}:{i+g_len}) {before} ⊕ {_array_to_bits_str(gen_bits)} = {after}"
                )
        else:
            if trace:
                steps.append(f"i={i:>3}: lead 0 ⇒ no-op")

    remainder = work[k:] if k >= 0 else work  # last r bits (or all if n<r)
    return remainder, steps

# ---------- CRC decode core ----------

def _crc_decode_core(
    recv_bits_str: str,
    gen_bits_str: str,
    want_trace: bool = False,
    try_single_fix: bool = False,
) -> Tuple[Optional[Dict[str, object]], Optional[str]]:
    # --- Validate inputs ---
    recv_bits_str = _clean_bits(recv_bits_str)
    gen_bits_str  = _clean_bits(gen_bits_str)

    if not recv_bits_str:
        return None, "Error: received bits cannot be empty."
    if not gen_bits_str or len(gen_bits_str) < 2:
        return None, "Error: generator must have length ≥ 2 bits."
    if gen_bits_str[0] != "1":
        return None, "Error: generator must be given with MSB=1 (leading coefficient 1)."
    if not all(c in "01" for c in recv_bits_str + gen_bits_str):
        return None, "Error: inputs must be binary (0/1)."

    n = len(recv_bits_str)
    g_len = len(gen_bits_str)
    r = g_len - 1
    if n < g_len:
        return None, f"Error: received length n={n} must be ≥ generator length {g_len}."

    k = n - r  # inferred message length for systematic form

    recv = _bits_str_to_array(recv_bits_str)
    gen  = _bits_str_to_array(gen_bits_str)

    # Compute syndrome (remainder of received ÷ G)
    syndrome, trace_steps = _crc_divide(dividend_bits=recv.copy(), gen_bits=gen, trace=want_trace)
    verify_ok = int(syndrome.sum()) == 0

    # Extract systematic fields (interpretation)
    msg_guess = recv[:k]
    recv_check = recv[k:]

    # Optional: single-bit auto-correction by brute force flip & test
    corrected_bits: Optional[np.ndarray] = None
    corrected_index: Optional[int] = None  # 0-based from the left (MSB index)
    corrected_ok = False

    if (not verify_ok) and try_single_fix:
        for i in range(n):
            trial = recv.copy()
            trial[i] ^= 1  # flip bit i
            rem, _ = _crc_divide(trial, gen, trace=False)
            if int(rem.sum()) == 0:
                corrected_bits = trial
                corrected_index = i
                corrected_ok = True
                break

    # If corrected, recompute message guess and syndrome for the corrected vector
    final_bits = corrected_bits if corrected_ok else recv
    final_syndrome, _ = _crc_divide(final_bits.copy(), gen, trace=False)
    final_ok = int(final_syndrome.sum()) == 0

    # Pretty math strings
    G_terms = _poly_bits_to_terms(gen_bits_str)
    G_latex = _poly_terms_to_latex(G_terms, name="G")

    results: Dict[str, object] = {
        # parameters
        "k": k,
        "r": r,
        "n": n,
        "gen_bits": gen_bits_str,
        "gen_degree": r,
        "G_terms": G_terms,
        "G_latex": G_latex,

        # received & interpretation
        "recv_bits": recv_bits_str,
        "msg_guess_bits": _array_to_bits_str(msg_guess),
        "recv_check_bits": _array_to_bits_str(recv_check),

        # syndrome / verification (on original)
        "syndrome_bits": _array_to_bits_str(syndrome),
        "verify_ok": verify_ok,

        # trace (optional)
        "trace_steps": trace_steps,

        # correction attempt
        "tried_single_fix": try_single_fix,
        "corrected_ok": corrected_ok,
        "corrected_index": corrected_index,  # 0-based from left (MSB=0)
        "corrected_bits": None if corrected_bits is None else _array_to_bits_str(corrected_bits),
        "final_bits": _array_to_bits_str(final_bits),
        "final_syndrome_bits": _array_to_bits_str(final_syndrome),
        "final_ok": final_ok,
        "final_msg_bits": _array_to_bits_str(final_bits[:k]),
    }
    return results, None

# ---------- Streamlit UI ----------

def render() -> None:
    st.title("CRC Decoder")

    st.markdown(
    r"""
Decode (and optionally validate/correct) a **Cyclic Redundancy Check (CRC)** codeword using polynomial division over $ \mathrm{GF}(2) $.

### Rules (no reflection, init=0, xorout=0)
Given a generator $G(x)$ of degree $r$, a received vector $R(x)$ of length $n$ is in systematic form
$R(x)=C(x)=M(x)\,x^r \oplus Remainder(x)$. Let $k=n-r$.

1. Compute the **syndrome** $S(x)=R(x)\bmod G(x)$.
2. If $S(x)=0$, the word is valid and the message is the first $k$ bits.
3. If $S(x)\neq 0$, an error is detected. Optionally try a **single-bit** correction by flipping each bit and rechecking $S(x)=0$.
"""
)

    # --- Inputs ---
    st.subheader("1) Received bits")
    # Provide a small working default by synthesizing a valid codeword on the fly
    default_msg = "1011001"
    default_gen = "10011"  # x^4 + x + 1  (degree 4)
    # Build a valid codeword for defaults
    msg_arr = _bits_str_to_array(default_msg)
    gen_arr = _bits_str_to_array(default_gen)
    r = len(default_gen) - 1
    dividend = np.concatenate([msg_arr, np.zeros(r, dtype=int)], axis=0)
    rem, _ = _crc_divide(dividend.copy(), gen_arr, trace=False)
    default_recv = _array_to_bits_str(np.concatenate([msg_arr, rem], axis=0))

    recv_bits_str = st.text_input("Received vector (binary):", default_recv)

    st.subheader("2) Generator polynomial")
    presets = {
        "x³ + x + 1  (degree 3)   →  1011":      "1011",
        "x⁴ + x + 1  (degree 4)   →  10011":     "10011",
        "x⁵ + x² + 1 (degree 5)   →  100101":    "100101",
        "x⁷ + x³ + 1 (degree 7)   →  10001001":  "10001001",
        "x⁸ + x² + x + 1 (deg 8)  →  100000111": "100000111",
        "Custom…": "CUSTOM",
    }
    choice = st.selectbox("Pick a preset or choose Custom:", list(presets.keys()), index=1)

    if presets[choice] == "CUSTOM":
        gen_default = default_gen
        gen_bits_str = st.text_input("Custom generator (MSB→LSB binary, leading 1 required):", gen_default)
    else:
        gen_bits_str = presets[choice]
        st.info(f"Using generator bits: **{gen_bits_str}**")

    want_trace = st.checkbox("Show long-division trace", value=False)
    try_single_fix = st.checkbox("Try one-bit auto-correction (exhaustive)", value=False)

    if st.button("Decode CRC", key="crc_decode"):
        st.markdown("---")
        results, error = _crc_decode_core(recv_bits_str, gen_bits_str, want_trace, try_single_fix)
        if error:
            st.error(error)
            return

        # 1) Parameters
        st.markdown("### 1) Parameters")
        st.markdown(
            f"- **Codeword length (n):** `{results['n']}`  \n"
            f"- **Generator degree (r):** `{results['r']}`  \n"
            f"- **Message length (k = n − r):** `{results['k']}`  \n"
            f"- **Generator bits (MSB→LSB):** `{_group_bits(results['gen_bits'], 4)}`"
        )
        st.latex(results["G_latex"])

        # 2) Interpretation
        st.markdown("### 2) Interpretation (systematic form)")
        st.markdown(f"- **Received**: `{_group_bits(results['recv_bits'], 4)}`")
        st.markdown(f"- **Message guess (first k bits)**: `{_group_bits(results['msg_guess_bits'], 4)}`")
        st.markdown(f"- **Received check (last r bits)**: `{results['recv_check_bits']}`")

        # 3) Syndrome and trace
        st.markdown("### 3) Syndrome and validation")
        st.markdown(f"- **Syndrome (R ÷ G remainder)**: `{results['syndrome_bits']}`")
        if results["verify_ok"]:
            st.success("Syndrome is all zeros ⇒ valid codeword under this CRC model.")
        else:
            st.error("Non-zero syndrome ⇒ error detected.")

        if want_trace:
            st.markdown("#### Long-division trace:")
            recv_bits = results["recv_bits"]
            gen_bits  = results["gen_bits"]
            n         = results["n"]
            r         = results["r"]
            k         = results["k"]

            work = np.array([int(b) for b in recv_bits], dtype=int)
            gen  = np.array([int(b) for b in gen_bits], dtype=int)
            g_len = len(gen_bits)

            lines = []
            lines.append(f"R(x) = {recv_bits}")
            lines.append(f"G(x) = {gen_bits}")
            lines.append("")
            for i in range(k):
                if work[i] == 1:
                    current = "".join(str(b) for b in work.tolist())
                    lines.append(f"{current} XOR")
                    lines.append(f"{' ' * i}{gen_bits}")
                    lines.append("-----------")
                    work[i:i+g_len] ^= gen
            remainder = "".join(str(b) for b in work[k:].tolist())
            lines.append(f"{' ' * k}{remainder} => degree lower than G(x)")
            lines.append(f"            => S(x) = {remainder}")
            st.code("\n".join(lines))

        # 4) Optional single-bit correction
        st.markdown("### 4) Optional single-bit correction")
        if results["tried_single_fix"]:
            if results["corrected_ok"]:
                idx = results["corrected_index"]
                from_left = idx
                from_right = results["n"] - 1 - idx
                st.success(
                    f"Found a 1-bit fix at index {from_left} from the left (MSB=0), "
                    f"i.e. {from_right} from the right (LSB=0)."
                )
                st.markdown(f"- **Corrected vector**: `{_group_bits(results['corrected_bits'], 4)}`")
                st.markdown(f"- **Corrected syndrome**: `{results['final_syndrome_bits']}`")
                st.markdown(f"- **Final message (first k bits)**: `{_group_bits(results['final_msg_bits'], 4)}`")
                if results["final_ok"]:
                    st.success("Verification OK after correction: remainder is all zeros.")
                else:
                    st.error("Unexpected: correction found but final remainder non-zero.")
            else:
                st.warning("No single-bit correction found (or multiple-bit errors present).")
        else:
            st.info("Single-bit auto-correction not attempted.")

        # 5) Notes
        st.markdown(
            r"""
**Notes**
- Arithmetic is in $ \mathrm{GF}(2) $: subtraction = addition = XOR.
- This tool uses the textbook CRC model (no bit reflection, zero initial register, no final XOR).
- CRCs are designed for **detection**, not general error correction; the 1-bit search here is a convenience and succeeds only for single-bit errors.
- For named CRC families (CRC-8/CRC-16/CRC-32 variants), reflection, non-zero init, and xorout parameters vary.
"""
        )

# ---------- Optional helpers (useful for tests & programmatic use) ----------

def _crc_decode_syndrome(recv_bits_str: str, gen_bits_str: str) -> str:
    """Return the syndrome (remainder of received ÷ generator)."""
    results, err = _crc_decode_core(recv_bits_str, gen_bits_str, want_trace=False, try_single_fix=False)
    if err:
        raise ValueError(err)
    return results["syndrome_bits"]  # type: ignore[index]

def _crc_decode_message_if_valid(recv_bits_str: str, gen_bits_str: str) -> str:
    """
    Return the message (first k bits) if the received vector is a valid codeword.
    Raises ValueError if the syndrome is non-zero.
    """
    results, err = _crc_decode_core(recv_bits_str, gen_bits_str, want_trace=False, try_single_fix=False)
    if err:
        raise ValueError(err)
    if not results["verify_ok"]:  # type: ignore[index]
        raise ValueError("Non-zero syndrome: received vector is not a valid codeword.")
    return results["msg_guess_bits"]  # type: ignore[index]

def _crc_try_single_bit_fix(recv_bits_str: str, gen_bits_str: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Attempt a single-bit fix via exhaustive flip & test.
    Returns (corrected_bits_str, corrected_index_from_left) if found, else (None, None).
    """
    results, err = _crc_decode_core(recv_bits_str, gen_bits_str, want_trace=False, try_single_fix=True)
    if err:
        raise ValueError(err)
    if results["corrected_ok"]:  # type: ignore[index]
        return results["corrected_bits"], results["corrected_index"]  # type: ignore[index]
    return None, None