# tools/multi_format_converter.py
#
# Multi-format integer converter with live (keystroke) synchronization across:
#  - Decimal
#  - Base 2
#  - Base 8
#  - Base 16
#  - One's complement (width-selectable)
#  - Two's complement (width-selectable)
#  - BCD (4-bit per digit; optional leading '-')
#
# Notes
# - Integers only.
# - Bit width controls 1's and 2's complement encodings.
# - For 1's complement, -0 exists; we keep a flag if the source was -0.
# - Out-of-range values for complements are shown modulo 2^n and flagged.

import streamlit as st
from decimal import Decimal, getcontext

getcontext().prec = 200

# ------------------ small helpers ------------------

def _byteswap_bits(bits: str) -> str:
    """
    Reverse the order of 8-bit bytes in a bitstring.
    Left-pads to a whole number of bytes if needed.
    """
    if len(bits) % 8 != 0:
        bits = "0" * (8 - (len(bits) % 8)) + bits
    chunks = [bits[i:i+8] for i in range(0, len(bits), 8)]
    chunks.reverse()
    return "".join(chunks)

def _bits_to_hex(bits: str) -> str:
    """Convert bits (length multiple of 4) to upper-case hex, left-padded."""
    if len(bits) % 4 != 0:
        bits = "0" * (4 - (len(bits) % 4)) + bits
    return format(int(bits, 2), f"0{len(bits)//4}X")

def _hex_byteswap(hex_str: str) -> str:
    """Reverse order of bytes in a hex string (2 hex chars per byte)."""
    hs = hex_str.upper()
    if len(hs) % 2 != 0:
        hs = "0" + hs
    pairs = [hs[i:i+2] for i in range(0, len(hs), 2)]
    pairs.reverse()
    return "".join(pairs)

def _strip_ws_us(s: str) -> str:
    return s.replace(" ", "").replace("_", "")

def _group_nibbles(bits: str, pad_to: int | None = None) -> str:
    """
    Group a bitstring in 4-bit chunks. If pad_to is given, left-pad with zeros to that width.
    """
    if pad_to is not None and pad_to > 0:
        if len(bits) < pad_to:
            bits = "0" * (pad_to - len(bits)) + bits
        elif len(bits) > pad_to:
            bits = bits[-pad_to:]  # keep rightmost pad_to bits (useful for modulo views)
    # pad left to a multiple of 4
    if len(bits) % 4:
        bits = "0" * (4 - (len(bits) % 4)) + bits
    return " ".join(bits[i:i+4] for i in range(0, len(bits), 4)) if bits else "0000"

def _parse_int_decimal(s: str) -> tuple[int | None, str | None]:
    s = _strip_ws_us(s.strip())
    if s in {"", "+", "-"}:
        return None, "Enter an integer."
    try:
        val = int(s, 10)
        return val, None
    except Exception:
        return None, "Not a valid base-10 integer."

def _parse_int_base(s: str, base: int) -> tuple[int | None, str | None]:
    s0 = s.strip()
    neg = False
    if s0.startswith(("+", "-")):
        if s0[0] == "-":
            neg = True
        s0 = s0[1:]
    s0 = _strip_ws_us(s0)
    if base == 16 and (s0.startswith("0x") or s0.startswith("0X")):
        s0 = s0[2:]
    if s0 == "":
        return None, "Enter digits."
    try:
        val = int(s0, base)
        return (-val if neg else val), None
    except Exception:
        return None, f"Not a valid base-{base} integer."

def _parse_bits_fixed(s: str, width: int) -> tuple[str | None, str | None]:
    """Return cleaned bitstring of exactly width bits (or error)."""
    s0 = _strip_ws_us(s.strip())
    if s0 == "":
        return None, f"Enter {width} bits."
    if not all(ch in "01" for ch in s0):
        return None, "Only 0/1 allowed."
    if len(s0) != width:
        return None, f"Must be exactly {width} bits."
    return s0, None

def _ones_to_int(bits: str) -> tuple[int, bool]:
    """
    Decode one's complement bitstring to integer.
    Returns (value, is_negative_zero).
    Range: [-(2^{n-1}-1), +(2^{n-1}-1)], with -0 (all ones).
    """
    n = len(bits)
    msb = bits[0]
    if msb == "0":
        return int(bits, 2), False
    # negative: value = - (bitwise_not(bits))_unsigned
    inv = "".join("1" if b == "0" else "0" for b in bits)
    mag = int(inv, 2)
    if mag == 0:
        # this is -0 (bits were all 1)
        return 0, True
    return -mag, False

def _int_to_ones(val: int, width: int, negative_zero: bool = False) -> tuple[str, bool]:
    """
    Encode integer in one's complement with given width.
    If val==0 and negative_zero=True, returns all ones.
    Returns (bits, overflow_flag).
    """
    max_pos = (1 << (width - 1)) - 1
    min_neg = -max_pos
    overflow = val > max_pos or val < min_neg
    mask = (1 << width) - 1
    if val == 0:
        return ("1" * width) if negative_zero else ("0" * width), overflow
    if val > 0:
        return format(val & mask, f"0{width}b"), overflow
    # negative: invert magnitude
    mag = -val
    bits = format(mag & mask, f"0{width}b")
    inv = "".join("1" if b == "0" else "0" for b in bits)
    return inv, overflow

def _twos_to_int(bits: str) -> int:
    """Decode two's complement bitstring to integer."""
    n = len(bits)
    unsigned = int(bits, 2)
    if bits[0] == "0":
        return unsigned
    return unsigned - (1 << n)

def _int_to_twos(val: int, width: int) -> tuple[str, bool]:
    """
    Encode integer to two's complement with width.
    Returns (bits, overflow_flag) — overflow if value not in [-2^{n-1}, 2^{n-1}-1].
    """
    min_neg = -(1 << (width - 1))
    max_pos = (1 << (width - 1)) - 1
    overflow = val < min_neg or val > max_pos
    mask = (1 << width) - 1
    return format((val & mask), f"0{width}b"), overflow

def _parse_bcd(s: str) -> tuple[int | None, bool, str | None]:
    """
    Parse a BCD bitstring like '0011 1001 0001' or with leading '-' sign.
    Returns (value, neg_zero_flag, error).
    """
    s0 = s.strip()
    neg = False
    if s0.startswith(("+", "-")):
        neg = s0[0] == "-"
        s0 = s0[1:]
    bits = "".join(ch for ch in s0 if ch in "01")
    if bits == "":
        return None, False, "Enter 4-bit groups (0–9)."
    if len(bits) % 4 != 0:
        return None, False, "Total number of bits must be a multiple of 4."
    digits = []
    for i in range(0, len(bits), 4):
        nib = int(bits[i:i+4], 2)
        if nib > 9:
            return None, False, f"Nibble '{bits[i:i+4]}' is not a BCD digit (0–9)."
        digits.append(str(nib))
    sval = "".join(digits) or "0"
    ival = int(sval, 10)
    if neg:
        if ival == 0:
            return 0, True, None  # -0 in BCD
        ival = -ival
    return ival, False, None

def _int_to_bcd(val: int, neg_zero_flag: bool = False) -> str:
    """
    Encode integer to plain BCD (no sign nibble): 4 bits per digit of |val|.
    Negative values are shown with a '-' prefix before the groups.
    If val==0 and neg_zero_flag=True, show '-' before '0000'.
    """
    neg = val < 0 or (val == 0 and neg_zero_flag)
    mag = abs(val)
    digits = list(str(mag))
    groups = " ".join(format(int(d), "04b") for d in digits) if digits else "0000"
    return ("-" if neg else "") + groups

def _digits_for_width(base: int, width: int) -> int:
    """How many digits are needed to represent `width` bits in the given base."""
    if base == 2:
        return width
    if base == 8:   # ceil(width / 3)
        return (width + 2) // 3
    if base == 16:  # ceil(width / 4)
        return (width + 3) // 4
    raise ValueError("Unsupported base")

def _format_baseN_signed(val: int, base: int, width: int) -> str:
    """
    Sign-preserving, left-padded formatting for base 2/8/16 according to `width`.
    For base 2, groups by 4 bits.
    """
    neg = val < 0
    mag = abs(val)
    if base == 2:
        digits = format(mag, "b")
    elif base == 8:
        digits = format(mag, "o")
    elif base == 16:
        digits = format(mag, "X")
    else:
        raise ValueError("base must be 2, 8, or 16")

    pad = _digits_for_width(base, width)
    if len(digits) < pad:
        digits = "0" * (pad - len(digits)) + digits

    if base == 2:
        # group nibbles
        digits = " ".join(digits[i:i+4] for i in range(0, len(digits), 4))
    return ("-" if neg else "") + digits

def _format_bin_signed(val: int, width: int) -> str:
    """Binary (base-2) sign-preserving, zero-left-padded to `width`, grouped by 4."""
    return _format_baseN_signed(val, 2, width)

# ------------------ main compute ------------------

def _compute_from_active(active: str, width: int) -> tuple[int | None, bool, list[str]]:
    """
    Reads st.session_state[...] for all fields, determines the authoritative value
    from the 'active' field, and returns:
      (integer_value or None on error, ones_neg_zero_flag, messages[])
    """
    msgs: list[str] = []
    neg_zero = False
    val: int | None = None

    try:
        if active == "decimal":
            val, err = _parse_int_decimal(st.session_state.mf_dec)
            if err: msgs.append(f"Decimal: {err}")

        elif active == "bin":
            val, err = _parse_int_base(st.session_state.mf_bin, 2)
            if err: msgs.append(f"Base-2: {err}")

        elif active == "oct":
            val, err = _parse_int_base(st.session_state.mf_oct, 8)
            if err: msgs.append(f"Base-8: {err}")

        elif active == "hex":
            val, err = _parse_int_base(st.session_state.mf_hex, 16)
            if err: msgs.append(f"Base-16: {err}")

        elif active == "ones":
            bits, err = _parse_bits_fixed(st.session_state.mf_ones, width)
            if err:
                msgs.append(f"1's complement: {err}")
            else:
                v, negz = _ones_to_int(bits)
                val, neg_zero = v, negz

        elif active == "twos":
            bits, err = _parse_bits_fixed(st.session_state.mf_twos, width)
            if err:
                msgs.append(f"2's complement: {err}")
            else:
                val = _twos_to_int(bits)

        elif active == "bcd":
            v, negz, err = _parse_bcd(st.session_state.mf_bcd)
            if err:
                msgs.append(f"BCD: {err}")
            else:
                val, neg_zero = v, negz

        else:
            msgs.append("Internal: unknown active field.")
    except Exception as e:
        msgs.append(f"Internal error: {e!s}")

    return val, neg_zero, msgs

def _update_all_views(val: int, width: int, ones_neg_zero: bool):
    """Writes all st.session_state[...] string fields from integer val."""
    # Bases (left-padded to the selected width)
    st.session_state.mf_dec = str(val)
    st.session_state.mf_bin = _format_bin_signed(val, width)
    st.session_state.mf_oct = _format_baseN_signed(val, 8, width)
    st.session_state.mf_hex = _format_baseN_signed(val, 16, width)

    # 1's complement
    ones_bits, ones_over = _int_to_ones(val, width, negative_zero=ones_neg_zero)
    st.session_state.mf_ones = _group_nibbles(ones_bits, pad_to=width)
    st.session_state.mf_ones_over = ones_over

    # 2's complement
    twos_bits, twos_over = _int_to_twos(val, width)
    st.session_state.mf_twos = _group_nibbles(twos_bits, pad_to=width)
    st.session_state.mf_twos_over = twos_over

    # BCD (sign as leading '-'; 4-bit per digit)
    st.session_state.mf_bcd = _int_to_bcd(val, neg_zero_flag=ones_neg_zero)

    # -------- Byte-order (BE/LE) derived views --------
    # We'll show binary/hex from the fixed-width encodings so endianness is meaningful.

    # Two's complement bits (width bits) → Binary (BE/LE)
    tw_be_bits = twos_bits  # already width bits
    tw_le_bits = _byteswap_bits(tw_be_bits)
    st.session_state.mf_bin_be = _group_nibbles(tw_be_bits, pad_to=width)
    st.session_state.mf_bin_le = _group_nibbles(tw_le_bits, pad_to=width)

    # Two's complement bits → Hex (BE/LE)
    tw_be_hex = _bits_to_hex(tw_be_bits)
    tw_le_hex = _hex_byteswap(tw_be_hex)
    st.session_state.mf_hex_be = tw_be_hex
    st.session_state.mf_hex_le = tw_le_hex

    # One's complement bits (width bits) → BE/LE
    on_be_bits = ones_bits
    on_le_bits = _byteswap_bits(on_be_bits)
    st.session_state.mf_ones_be = _group_nibbles(on_be_bits, pad_to=width)
    st.session_state.mf_ones_le = _group_nibbles(on_le_bits, pad_to=width)

    # Two's complement bits again for labeled BE/LE fields (explicit)
    st.session_state.mf_twos_be = _group_nibbles(tw_be_bits, pad_to=width)
    st.session_state.mf_twos_le = _group_nibbles(tw_le_bits, pad_to=width)

    # Decimal duplicates (unaltered by endianness)
    st.session_state.mf_dec_be = st.session_state.mf_dec
    st.session_state.mf_dec_le = st.session_state.mf_dec

    # BCD: pack to bits (4 per digit). First pad to the selected bit width (if needed),
    # then perform endianness. If byte padding is added for swapping, trim it back
    # so BE and LE displays have the same bit-length as the width-padded input.
    bcd_disp = st.session_state.mf_bcd  # e.g., "- 0001 0010 ..."
    sign_bcd = bcd_disp.strip().startswith("-")
    bits_only = "".join(ch for ch in bcd_disp if ch in "01")

    if bits_only:
        # 1) Ensure at least `width` bits before applying endianness (no truncation).
        if len(bits_only) < width:
            bits_w = "0" * (width - len(bits_only)) + bits_only
        else:
            bits_w = bits_only  # longer than width is allowed/kept for display

        # 2) LE view requires byte swapping. The helper pads to full bytes on the left;
        #    after swapping, trim back to the original (width-padded) length.
        le_swapped_full = _byteswap_bits(bits_w)
        le_swapped = le_swapped_full[-len(bits_w):]

        # 3) Group both BE and LE in nibbles for readability.
        bcd_be = " ".join(bits_w[i:i+4] for i in range(0, len(bits_w), 4))
        bcd_le = " ".join(le_swapped[i:i+4] for i in range(0, len(le_swapped), 4))
    else:
        bcd_be = bcd_le = "0000"

    st.session_state.mf_bcd_be = ("-" if sign_bcd else "") + bcd_be
    st.session_state.mf_bcd_le = ("-" if sign_bcd else "") + bcd_le

# ------------------ UI ------------------

def render() -> None:
    st.title("Multi-Format Integer Converter")

    st.markdown(
        r"""
Type in **any** one of the boxes — all the others update instantly.

**Formats**
- **Decimal** (base-10)
- **Base 2, 8, 16** (sign allowed, `_` and spaces ignored)
- **1’s complement** (fixed width; `-0` is all 1s)
- **2’s complement** (fixed width)
- **BCD** (4-bit groups per digit; optional leading `-` sign; no sign nibble)
"""
    )

    # ---------- session state defaults ----------
    if "mf_width" not in st.session_state:
        st.session_state.mf_width = 16  # default 16-bit

    if "mf_active" not in st.session_state:
        st.session_state.mf_active = "decimal"

    width0 = st.session_state.mf_width

    defaults = {
        "mf_dec": "0",
        "mf_bin": "",  # will be set below from formatter
        "mf_oct": "",
        "mf_hex": "",
        "mf_ones": _group_nibbles("0"*width0, pad_to=width0),
        "mf_twos": _group_nibbles("0"*width0, pad_to=width0),
        "mf_bcd": "0000",
        "mf_ones_over": False,
        "mf_twos_over": False,
        "mf_dec_be": "0",
        "mf_dec_le": "0",
        "mf_bin_be": "",
        "mf_bin_le": "",
        "mf_hex_be": "",
        "mf_hex_le": "",
        "mf_ones_be": "",
        "mf_ones_le": "",
        "mf_twos_be": "",
        "mf_twos_le": "",
        "mf_bcd_be": "",
        "mf_bcd_le": "",
    }
    # set padded base defaults
    defaults["mf_bin"] = _format_bin_signed(0, width0)
    defaults["mf_oct"] = _format_baseN_signed(0, 8, width0)
    defaults["mf_hex"] = _format_baseN_signed(0, 16, width0)

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
            
    # callbacks to mark which field the user edited
    def _mark_active(name: str):
        st.session_state.mf_active = name

    # ---------- Controls ----------
    width = st.selectbox("Bit width (for complements)", [4, 8, 16, 32, 64], index=2, key="mf_width")
    st.caption("Used for **1’s** and **2’s** complement encodings.")

    # Compute from last edited field before drawing inputs
    val, neg_zero, messages = _compute_from_active(st.session_state.mf_active, width)
    if val is not None:
        _update_all_views(val, width, neg_zero)

    # ---------- Inputs (keystroke-live) ----------
    c1, c2 = st.columns(2)

    with c1:
        st.text_input("Decimal", key="mf_dec", on_change=lambda: _mark_active("decimal"))
        st.text_input("Base 2 (grouped by 4; optional '-')", key="mf_bin", on_change=lambda: _mark_active("bin"))
        st.text_input("Base 8 (octal)", key="mf_oct", on_change=lambda: _mark_active("oct"))
        st.text_input("Base 16 (hex, upper)", key="mf_hex", on_change=lambda: _mark_active("hex"))

    with c2:
        st.text_input(f"1’s complement ({width} bits)", key="mf_ones", on_change=lambda: _mark_active("ones"))
        st.text_input(f"2’s complement ({width} bits)", key="mf_twos", on_change=lambda: _mark_active("twos"))
        st.text_input("BCD (4-bit groups; optional '-')", key="mf_bcd", on_change=lambda: _mark_active("bcd"))

        # Inline range status for complements (clear 'Out of range' per field)
        if st.session_state.mf_ones_over:
            st.error(f"Out of range for {width}-bit 1’s complement. Showing modulo 2^{width}.")
            st.caption(f"Valid range (1’s complement): −(2^{width-1}−1) … +(2^{width-1}−1).")

        if st.session_state.mf_twos_over:
            st.error(f"Out of range for {width}-bit 2’s complement. Showing modulo 2^{width}.")
            st.caption(f"Valid range (2’s complement): [−2^{width-1}, 2^{width-1}−1].")


    # Errors (if any) from the active parse
    if messages:
        for m in messages:
            st.error(m)

    st.subheader("Byte-order views (read-only)")

    be_col, le_col = st.columns(2)
    with be_col:
        st.caption("Big-endian (MSB-first byte order)")
        st.text_input("Binary (2’s complement, BE)", key="mf_bin_be", disabled=True)
        st.text_input("Hex (2’s complement, BE)", key="mf_hex_be", disabled=True)
        st.text_input("BCD (packed, BE)", key="mf_bcd_be", disabled=True)

    with le_col:
        st.caption("Little-endian (bytes reversed)")
        st.text_input("Binary (2’s complement, LE)", key="mf_bin_le", disabled=True)
        st.text_input("Hex (2’s complement, LE)", key="mf_hex_le", disabled=True)
        st.text_input("BCD (packed, LE)", key="mf_bcd_le", disabled=True)


    with st.expander("ℹ️ What is Endianness? (Byte Order)", expanded=False):
        st.markdown(r"""
        **Endianness** defines the order in which bytes of a multi-byte data word are stored in computer memory. Think of it as the computer's convention for writing down numbers.

        Imagine the 4-byte hexadecimal number `0x0A0B0C0D`. It has four bytes: `0A`, `0B`, `0C`, and `0D`.
        - The **most significant byte (MSB)** is `0A` (the "big end").
        - The **least significant byte (LSB)** is `0D` (the "little end").

        How does a computer store these four bytes in four sequential memory addresses (e.g., `1000` to `1003`)? There are two primary ways:

        ### Big-Endian: "Big End First"

        This is the intuitive way, similar to how we write numbers and read text (left-to-right). The **most significant byte (MSB)** is stored at the **lowest memory address**.

        - **Analogy:** Writing the number "123". You write the most significant digit '1' first.
        - **Used In:** Networking protocols (like TCP/IP), older Mac processors (PowerPC), and many RISC architectures.

        **Example:** Storing `0x0A0B0C0D` in memory:
        $$
        \begin{array}{c|c}
        \text{Memory Address} & \text{Value Stored} \\
        \hline
        \texttt{1000} & \texttt{0A} \\
        \texttt{1001} & \texttt{0B} \\
        \texttt{1002} & \texttt{0C} \\
        \texttt{1003} & \texttt{0D} \\
        \end{array}
        $$

        ### Little-Endian: "Little End First"

        This is the more common convention in modern consumer hardware. The **least significant byte (LSB)** is stored at the **lowest memory address**.

        - **Analogy:** Writing a date in `DD-MM-YYYY` format. The least significant component (day) comes first.
        - **Used In:** Intel and AMD x86/x64 processors, modern Apple Silicon (ARM), and various file formats.

        **Example:** Storing `0x0A0B0C0D` in memory:
        $$
        \begin{array}{c|c}
        \text{Memory Address} & \text{Value Stored} \\
        \hline
        \texttt{1000} & \texttt{0D} \\
        \texttt{1001} & \texttt{0C} \\
        \texttt{1002} & \texttt{0B} \\
        \texttt{1003} & \texttt{0A} \\
        \end{array}
        $$

        ### Why Does It Matter?

        - **Networking:** Data sent over a network must be in a standard order (Network Byte Order, which is Big-Endian). Little-endian machines must convert their byte order before sending and after receiving.
        - **File Formats:** Files like images (`.bmp`) or executables (`.exe`) have specified endianness. Reading them on a machine with the wrong native order requires byte swapping.
        - **Hardware:** It can simplify certain arithmetic operations at the circuit level, which is one reason for the prevalence of little-endian in modern CPUs.

        ### Check Your System's Endianness in Python
        You can easily check your machine's native byte order:
        ```python
        import sys
        # This will print 'little' or 'big'
        print(sys.byteorder)
        ```
        Most likely, your personal computer will print `little`.
        """)