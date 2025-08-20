# tools/crc_encode.py
#
# Streamlit UI + pure logic for CRC encoding with rule-based (LaTeX) explanations.
# Supports:
#   - variable-length input bits,
#   - preset short generator polynomials,
#   - custom generator given as MSB→LSB binary (e.g., "10011" for x^4 + x + 1),
#   - optional long-division trace over GF(2).
#
# Model (no reflection, init=0, xorout=0):
#   1) Let r = deg(G). Append r zeros to the message: M'(x) = M(x) * x^r.
#   2) Compute R(x) = M'(x) mod G(x) via polynomial long division in GF(2).
#   3) Codeword: C(x) = M(x) * x^r ⊕ R(x)  (i.e., append remainder bits).
#
# Verification step divides C(x) by G(x) and shows the remainder is 0^r.

import streamlit as st
import numpy as np
from typing import Dict, List, Tuple, Optional

# ---------- Bit & polynomial helpers ----------

def _clean_bits(s: str) -> str:
    """Remove spaces/underscores and validate binary."""
    t = "".join(ch for ch in s if ch in "01")
    return t

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
            exp = (n - 1) - i
            exps.append(exp)
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
    parts = [s[i:i+group] for i in range(0, len(s), group)]
    return " ".join(parts)

# ---------- CRC long division over GF(2) ----------

def _crc_divide(dividend_bits: np.ndarray, gen_bits: np.ndarray, trace: bool = False) -> Tuple[np.ndarray, List[str]]:
    """
    Perform polynomial long-division in GF(2):
      dividend_bits: the message with r zeros appended (length k+r)
      gen_bits: generator, length r+1, MSB=1
    Returns: remainder (length r), and an optional textual trace.
    """
    work = dividend_bits.copy()
    k_plus_r = len(work)
    g_len = len(gen_bits)
    r = g_len - 1
    k = k_plus_r - r

    steps: List[str] = []
    for i in range(k):  # only slide over the original message span
        if work[i] == 1:
            # XOR generator onto work[i : i + g_len]
            before = _array_to_bits_str(work[i:i+g_len]) if trace else ""
            work[i:i+g_len] ^= gen_bits
            after  = _array_to_bits_str(work[i:i+g_len]) if trace else ""
            if trace:
                steps.append(
                    f"i={i:>3}: lead 1 ⇒ XOR gen → slice[{i}:{i+g_len}) {before} ⊕ {_array_to_bits_str(gen_bits)} = {after}"
                )
        else:
            if trace:
                steps.append(f"i={i:>3}: lead 0 ⇒ no-op")

    remainder = work[k:]  # last r bits
    return remainder, steps

def _crc_encode_core(msg_bits_str: str, gen_bits_str: str, want_trace: bool = False) -> Tuple[Optional[Dict[str, object]], Optional[str]]:
    # --- Validate inputs ---
    msg_bits_str = _clean_bits(msg_bits_str)
    gen_bits_str = _clean_bits(gen_bits_str)

    if not msg_bits_str:
        return None, "Error: message bits cannot be empty."
    if not gen_bits_str or len(gen_bits_str) < 2:
        return None, "Error: generator must have length ≥ 2 bits."
    if gen_bits_str[0] != "1":
        return None, "Error: generator must be given with MSB=1 (leading coefficient 1)."
    if not all(c in "01" for c in msg_bits_str+gen_bits_str):
        return None, "Error: inputs must be binary (0/1)."

    k = len(msg_bits_str)
    g_len = len(gen_bits_str)
    r = g_len - 1  # degree

    msg = _bits_str_to_array(msg_bits_str)
    gen = _bits_str_to_array(gen_bits_str)

    # Dividend = msg || r zeros
    dividend = np.concatenate([msg, np.zeros(r, dtype=int)], axis=0)

    # Compute remainder
    remainder, trace_steps = _crc_divide(dividend_bits=dividend, gen_bits=gen, trace=want_trace)

    # Codeword = msg || remainder
    codeword = np.concatenate([msg, remainder], axis=0)

    # Verify: divide codeword by same generator → remainder should be all-zeros
    verify_remainder, _ = _crc_divide(codeword.copy(), gen, trace=False)
    verify_ok = int(verify_remainder.sum()) == 0

    # Prepare pretty math strings
    G_terms = _poly_bits_to_terms(gen_bits_str)
    G_latex = _poly_terms_to_latex(G_terms, name="G")

    results: Dict[str, object] = {
        # parameters
        "k": k,
        "r": r,
        "n": k + r,
        "gen_bits": gen_bits_str,
        "gen_degree": r,
        "G_terms": G_terms,
        "G_latex": G_latex,

        # bitstrings
        "msg_bits": msg_bits_str,
        "dividend_bits": _array_to_bits_str(dividend),
        "remainder_bits": _array_to_bits_str(remainder),
        "codeword_bits": _array_to_bits_str(codeword),

        # verification
        "verify_remainder_bits": _array_to_bits_str(verify_remainder),
        "verify_ok": verify_ok,

        # trace (optional)
        "trace_steps": trace_steps,
    }
    return results, None

# ---------- Streamlit UI ----------

def render() -> None:
    st.title("CRC Encoder")

    st.markdown(
    """
Encode a message with a **Cyclic Redundancy Check (CRC)** using polynomial division over $ \mathrm{GF}(2) $.

### Rules (no reflection, init=0, xorout=0)
1. Choose a generator polynomial $G(x)$ of degree $r$.
2. Let the message bits define $M(x)$. Append $r$ zeros: $M'(x)=M(x)\,x^{r}$.
3. Compute the remainder $R(x) = M'(x) \: mod \: G(x)$ using long division in $ \mathrm{GF}(2) $ (XOR = addition).
4. Form the codeword:
$$
C(x) \;=\; M(x)\,x^{r} \;\oplus\; R(x),
\quad{i.e.}\quad
{codeword} \;=\; {message} \;\Vert\; {remainder}.
$$
5. Verification: $G(x)$ divides $C(x)$ exactly $\Rightarrow$ the remainder of $C(x) \div G(x)$ is the all-zeros vector of length $r$.
"""
)

    # --- Inputs ---
    msg_default = "1011001"
    st.subheader("1) Message bits")
    msg_bits_str = st.text_input("Message (binary, any length):", msg_default)

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
        gen_default = "10011"  # x^4 + x + 1
        gen_bits_str = st.text_input("Custom generator (MSB→LSB binary, leading 1 required):", gen_default)
    else:
        gen_bits_str = presets[choice]
        st.info(f"Using generator bits: **{gen_bits_str}**")

    want_trace = st.checkbox("Show long-division trace", value=False)

    if st.button("Encode CRC", key="crc_encode"):
        st.markdown("---")
        results, error = _crc_encode_core(msg_bits_str, gen_bits_str, want_trace)
        if error:
            st.error(error)
            return

        # 1) Parameters
        st.markdown("### 1) Parameters")
        st.markdown(
            f"- **Message length (k):** `{results['k']}`  \n"
            f"- **Generator degree (r):** `{results['r']}`  \n"
            f"- **Codeword length (n = k + r):** `{results['n']}`  \n"
            f"- **Generator bits (MSB→LSB):** `{_group_bits(results['gen_bits'], 4)}`"
        )
        st.latex(results["G_latex"])

        # 2) Construction recap
        st.markdown("### 2) Construction (math recap)")
        st.latex(r"M'(x) = M(x)\,x^{r},\qquad R(x) = M'(x)\bmod G(x),\qquad C(x) = M(x)\,x^{r}\oplus R(x)")

        # 3) Division inputs
        st.markdown("### 3) Dividend and remainder")
        st.markdown(f"- **Dividend** (message with r zeros appended): `{_group_bits(results['dividend_bits'], 4)}`")
        st.markdown(f"- **Remainder** (length r): `{results['remainder_bits']}`")

        if want_trace:
            st.markdown("#### Long-division trace:")
            gen_bits = results["gen_bits"]
            msg_bits = results["msg_bits"]
            r        = results["r"]
            k        = results["k"]

            # Work buffer = dividend (message ∥ r zeros)
            dividend_bits = results["dividend_bits"]           # as a string
            work = np.array([int(b) for b in dividend_bits], dtype=int)
            gen  = np.array([int(b) for b in gen_bits], dtype=int)
            g_len = len(gen_bits)

            lines = []
            # Header like the example (show message and appended zeros separated by a space)
            lines.append(f"M'(x) = {msg_bits} {'0'*r}")
            lines.append(f" G(x) = {gen_bits}")
            lines.append("")

            # Show only the XOR steps where the leading bit at position i is 1
            for i in range(k):
                if work[i] == 1:
                    # Current buffer before XOR
                    current = "".join(str(b) for b in work.tolist())
                    lines.append(f"{current} XOR")
                    lines.append(f"{' ' * i}{gen_bits}")
                    lines.append("-----------")
                    # Apply XOR of generator aligned at i
                    work[i:i+g_len] ^= gen

            remainder = "".join(str(b) for b in work[k:].tolist())

            # Final remainder line aligned under the remainder window
            lines.append(f"{' ' * k}{remainder} => degree lower than G(x)")
            lines.append(f"            => R(x) = {remainder}")
            lines.append("")
            lines.append(f"So C(x): {msg_bits} {remainder}")

            st.code("\n".join(lines))

        # 4) Codeword and verification
        st.markdown("### 4) Codeword and verification")
        st.markdown(f"- **Codeword** = message ∥ remainder: `{_group_bits(results['codeword_bits'], 4)}`")
        st.markdown(f"- **Verify remainder (C ÷ G)**: `{results['verify_remainder_bits']}`")
        if results["verify_ok"]:
            st.success("Verification OK: remainder is all zeros ⇒ G(x) divides C(x).")
        else:
            st.error("Verification failed: non-zero remainder. Check your inputs.")

        # 5) Notes
        st.markdown(
            """
**Notes**
- Arithmetic is in $ \mathrm{GF}(2) $: subtraction = addition = XOR.
- This tool uses the textbook CRC model (no bit reflection, zero initial register, no final XOR).
- For named CRC families (CRC-8/CRC-16/CRC-32 variants), reflection, non-zero init, and xorout
  parameters vary. Those can be added as options if you need them.
"""
        )

    with st.expander("ℹ️ What does “Arithmetic is in GF(2)” mean?", expanded=False):
        st.markdown(r"""
    **GF(2)** is the Galois field with two elements $\{0,1\}$.
    All operations are **modulo 2**, which maps perfectly to digital logic circuitry.

    ### Operations in GF(2)

    - **Addition = XOR (no carries)**
    
    $$
    \begin{align*}
    0+0 &= 0 \\
    0+1 &= 1 \\
    1+0 &= 1 \\
    1+1 &= \color{#c00}{0}
    \end{align*}
    $$
    
    Subtraction is equivalent to addition in GF(2): $a-b \equiv a+b \pmod 2$.

    - **Multiplication = AND**
    
    $$
    \begin{align*}
    0\cdot0 &= 0 \\
    0\cdot1 &= 0 \\
    1\cdot0 &= 0 \\
    1\cdot1 &= 1
    \end{align*}
    $$


    ### Application to Polynomials & CRCs

    - **Polynomials over GF(2)** Bits are treated as coefficients (0 or 1). For example, the bitstring `10011` corresponds to the polynomial $x^4 + x + 1$. Adding these polynomials is a coefficient-wise **XOR**.

    - **CRC Long Division** The division process is "carry-less." Each subtraction step in traditional long division is replaced by an **XOR operation** with the aligned generator polynomial. This is why CRC hardware is so efficient.

    - **Why GF(2) is Ideal for CRCs** It allows for simple hardware implementation (XOR/AND gates), enables extremely fast carry-less division, and provides robust algebraic properties for error detection.


    ### Quick Examples

    - **Bitstring XOR** (addition in GF(2)):  
    $\texttt{10110} \oplus \texttt{11001} = \texttt{01111}$ *(Notice: no carries)*
    - **Bitwise AND** (multiplication in GF(2)):  
    $1\cdot1=1$, $1\cdot0=0$, $0\cdot1=0$, $0\cdot0=0$

    **Useful Identities**

    $$
    \begin{align*}
    a \oplus b & \;=\; (a+b)\bmod 2 \\
    (a\oplus b)\oplus c & \;=\; a\oplus(b\oplus c)
    \end{align*}
    $$
    """)

# Optional helpers (useful for tests)
def _crc_encode_return_codeword(msg_bits_str: str, gen_bits_str: str) -> str:
    results, err = _crc_encode_core(msg_bits_str, gen_bits_str, want_trace=False)
    if err:
        raise ValueError(err)
    return results["codeword_bits"]

def _crc_remainder(msg_bits_str: str, gen_bits_str: str) -> str:
    results, err = _crc_encode_core(msg_bits_str, gen_bits_str, want_trace=False)
    if err:
        raise ValueError(err)
    return results["remainder_bits"]
