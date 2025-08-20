# tools/logic_kmap_sop.py
#
# K-Map SOP minimizer (≤ 5 variables):
#  - Input: Boolean expression OR minterms/don’t-cares
#  - Expression parser accepts multiple notations (case-insensitive):
#    OR:  + , U , V , OR , | 
#    AND: . , x , X , AND , * , adjacency (e.g., AB = A AND B)
#    NOT: ' (prime after symbol or ')', ! , ~ , NOT
#  - Auto-build truth table from expression
#  - K-map in Gray order (torus adjacency) with layered translucent groups
#  - Outputs minimized SOP and grouped implicants
#
# Display: Streamlit + embedded HTML/CSS (no external libs)

from __future__ import annotations
import re
import itertools as it
from typing import List, Tuple, Dict, Set, Optional
import streamlit as st

# --------------------------- Helpers: Gray code & layout ---------------------------

def gray_seq(k: int) -> List[int]:
    """Return sequence [0..2^k-1] in Gray-code order."""
    return [(i ^ (i >> 1)) for i in range(1 << k)]

def kmap_dims(nvars: int) -> Tuple[int,int,int,int]:
    """
    Return (R, C, row_bits, col_bits) for K-map layout.
    We use classic layouts:
      1 var → 1x2  (0/1 on columns)      row_bits=0, col_bits=1
      2 var → 2x2  (1 row bit, 1 col bit)
      3 var → 2x4  (1 row bit, 2 col bits)
      4 var → 4x4  (2 row bits, 2 col bits)
      5 var → 4x8  (2 row bits, 3 col bits)
    """
    n = nvars
    if n <= 0 or n > 5:
        raise ValueError("nvars must be in 1..5")
    if n == 1:
        return 1, 2, 0, 1
    if n == 2:
        return 2, 2, 1, 1
    if n == 3:
        return 2, 4, 1, 2
    if n == 4:
        return 4, 4, 2, 2
    return 4, 8, 2, 3  # n == 5

def bitstr_to_int(bits: List[int]) -> int:
    """MSB-first list of bits -> integer."""
    val = 0
    for b in bits:
        val = (val << 1) | (1 if b else 0)
    return val

# --------------------------- Expression parsing & eval -----------------------------

VAR_SET = ['A','B','C','D','E']

_OR_ALIASES  = r"(?:\+|\bU\b|\bV\b|\bOR\b|\|)"
_AND_ALIASES = r"(?:\.|x|X|\bAND\b|\*|·)"
_NOT_ALIASES = r"(?:!|~|\bNOT\b|¬)"

def _norm_expr(s: str) -> Tuple[str, List[str]]:
    """
    Normalize a user Boolean expression to a safe Python expression using
      'and', 'or', and 'not'.
    Accepts adjacency for AND and trailing apostrophes for negation.
    Returns (python_expr, variables_used_sorted_by_A_to_E).
    """
    if not isinstance(s, str):
        raise ValueError("Expression must be a string.")

    # Stage 1: Canonicalization.
    # Convert all user aliases into a simple, consistent internal format.
    # Use single characters: '&' for AND, '|' for OR, '!' for prefix NOT.
    s = s.strip()
    s = re.sub(r"[\s_]+", "", s)
    s = re.sub(_OR_ALIASES, '|', s, flags=re.IGNORECASE)
    s = re.sub(_AND_ALIASES, '&', s, flags=re.IGNORECASE)
    s = re.sub(_NOT_ALIASES, '!', s, flags=re.IGNORECASE)
    s = s.upper()

    # Stage 2: Adjacency Insertion.
    # On the canonical string, insert the explicit '&' for adjacency.
    result = []
    for i, char in enumerate(s):
        result.append(char)
        if i < len(s) - 1:
            next_char = s[i+1]
            # Adjacency occurs if a term-ender is followed by a term-starter.
            # Ender: Variable, closing parenthesis, or a prime.
            # Starter: Variable, opening parenthesis, or a prefix NOT.
            if char in "ABCDE)'" and next_char in "ABCDE(!":
                result.append('&')
    s = "".join(result)

    # Stage 3: Translation to Python's Boolean Syntax.
    # Convert the canonical format to a guaranteed-valid Python expression.

    # First, handle all forms of negation (postfix ' and prefix !).
    # The order is crucial: handle specific primes before the general '!' prefix.
    # A loop handles nested structures like ((A&B)')'.
    while "'" in s or '!' in s:
        s_before = s
        # Handle primes on parenthesized groups: (X)' -> not(X)
        s = re.sub(r"(\([^)]+\))'", r'not(\1)', s)
        # Handle primes on single variables: A' -> (not A)
        s = re.sub(r"([A-E])'", r'(not \1)', s)
        # Handle the prefix NOT operator: !X -> not X
        s = s.replace('!', 'not ')

        if s == s_before:
            # Break if no change was made, to prevent infinite loops on malformed input.
            break

    # Finally, replace the canonical AND/OR with Python's boolean operators.
    # Surrounding them with spaces is critical for the eval() parser.
    s = s.replace('&', ' and ')
    s = s.replace('|', ' or ')

    used = sorted({ch for ch in s if ch in VAR_SET}, key=lambda v: VAR_SET.index(v))
    return s, used

def _eval_expr_to_minterms(expr: str, var_order: List[str]) -> Set[int]:
    """
    Evaluate expression for all 2^n assignments in var_order (MSB→LSB)
    and return the set of minterm indices that evaluate True.
    """
    py_expr, used = _norm_expr(expr)
    # If user uses fewer vars than var_order, shrink
    if used:
        var_order = [v for v in var_order if v in used]
    n = len(var_order)
    ones: Set[int] = set()
    # Build all assignments (MSB first)
    for bits in it.product([0,1], repeat=n):
        env = {var_order[i]: bool(bits[i]) for i in range(n)}
        val = eval(py_expr, {"__builtins__": {}}, env)  # safe enough; no names other than A..E exist
        if bool(val):
            idx = bitstr_to_int(list(bits))
            ones.add(idx)
    return ones

# --------------------------- K-map model & rectangles ------------------------------

def build_maps(nvars: int, var_order: List[str]):
    """Return model dict with dims, gray orders, and cell->minterm mapping."""
    R, C, rb, cb = kmap_dims(nvars)
    gray_rows = gray_seq(rb) if rb > 0 else [0]
    gray_cols = gray_seq(cb) if cb > 0 else [0]

    # Precompute: cell (r,c) -> minterm index (0..2^n-1) under var_order (MSB..LSB)
    cell_to_minterm: List[List[int]] = [[0]*C for _ in range(R)]
    minterm_to_cell: Dict[int, Tuple[int,int]] = {}

    for ri, rcode in enumerate(gray_rows):
        for ci, ccode in enumerate(gray_cols):
            bits = []
            # Row vars first (MSB..), then col vars
            for k in reversed(range(rb)):  # MSB first
                bits.append((rcode >> k) & 1)
            for k in reversed(range(cb)):
                bits.append((ccode >> k) & 1)
            idx = bitstr_to_int(bits)
            cell_to_minterm[ri][ci] = idx
            minterm_to_cell[idx] = (ri, ci)

    return {
        "R": R, "C": C, "rb": rb, "cb": cb,
        "rows_gray": gray_rows, "cols_gray": gray_cols,
        "cell_to_min": cell_to_minterm,
        "min_to_cell": minterm_to_cell,
        "var_order": var_order[:nvars]
    }

def rect_cells(R, C, r0, c0, h, w):
    """Cells covered by wrapping rectangle (r0..r0+h-1, c0..c0+w-1) modulo R,C."""
    for dr in range(h):
        for dc in range(w):
            yield ((r0 + dr) % R, (c0 + dc) % C)

def all_power2_sizes(R, C):
    hs = [1,2,4,8,16,32]
    ws = [1,2,4,8,16,32]
    return [ (h,w) for h in hs if h<=R for w in ws if w<=C ]

def enumerate_prime_rects(model, ones: Set[int], dcs: Set[int]) -> List[Set[int]]:
    """Enumerate maximal (prime) implicant rectangles using ones + don't-cares."""
    R, C = model["R"], model["C"]
    cell_to_min = model["cell_to_min"]
    valid = []
    # collect all rectangles that contain only 1 or X (and at least one 1)
    for h,w in sorted(all_power2_sizes(R,C), key=lambda s: s[0]*s[1], reverse=True):
        seen_sets = set()
        for r0 in range(R):
            for c0 in range(C):
                mins = []
                has_one = False
                ok = True
                for (r,c) in rect_cells(R,C,r0,c0,h,w):
                    m = cell_to_min[r][c]
                    mins.append(m)
                    if m in ones:
                        has_one = True
                    elif m in dcs:
                        pass
                    else:
                        ok = False
                        break
                if ok and has_one:
                    s = frozenset(mins)
                    if s not in seen_sets:
                        seen_sets.add(s)
                        valid.append(set(s))
    # Keep only prime rectangles (not a proper subset of any other)
    primes: List[Set[int]] = []
    for s in valid:
        if not any( (s < t) for t in valid ):  # strict subset test
            primes.append(s)
    return primes

def pick_cover(primes: List[Set[int]], ones: Set[int]) -> List[Set[int]]:
    """Essential primes + greedy set cover for remaining ones."""
    cover: List[Set[int]] = []
    uncovered = set(ones)
    # Essential
    for m in list(uncovered):
        candidates = [p for p in primes if m in p]
        if len(candidates) == 1 and candidates[0] not in cover:
            cover.append(candidates[0])
            uncovered -= candidates[0]
    # Greedy
    while uncovered:
        best = max(primes, key=lambda p: len(p & uncovered))
        if len(best & uncovered) == 0:
            break
        cover.append(best)
        uncovered -= best
    return cover

def implicant_to_term(minset: Set[int], nvars: int, var_order: List[str]) -> str:
    """
    For a set of minterms, find literals that don't change across the set
    (0 → var', 1 → var). Output product term like A·B'·D.
    """
    if not minset:
        return "1"
    # Build per-variable bit consistency
    bits_by_var = [set() for _ in range(nvars)]
    for m in minset:
        for i in range(nvars):
            bit = (m >> (nvars-1-i)) & 1  # MSB var_order[0]
            bits_by_var[i].add(bit)
    lits = []
    for i,var in enumerate(var_order[:nvars]):
        vals = bits_by_var[i]
        if vals == {0}:
            lits.append(f"{var}'")
        elif vals == {1}:
            lits.append(f"{var}")
        else:
            # eliminates this variable
            pass
    if not lits:
        return "1"
    return "·".join(lits)

# --------------------------- HTML rendering (layered groups) -----------------------

def _segments_for_wrap(r0,c0,h,w,R,C):
    """Split a wrapping rectangle into 1/2/4 non-wrapping segments (for drawing)."""
    r_splits = []
    if r0 + h <= R:
        r_splits.append( (r0, h) )
    else:
        h1 = R - r0
        h2 = (r0 + h) % R
        r_splits.extend( [(r0, h1), (0, h2)] )

    c_splits = []
    if c0 + w <= C:
        c_splits.append( (c0, w) )
    else:
        w1 = C - c0
        w2 = (c0 + w) % C
        c_splits.extend( [(c0, w1), (0, w2)] )

    segs = []
    for (rs, rh) in r_splits:
        for (cs, cw) in c_splits:
            segs.append( (rs, cs, rh, cw) )
    return segs

PALETTE = [
    "255,99,132","54,162,235","255,206,86","75,192,192","153,102,255",
    "255,159,64","199,199,199","255,99,71","60,179,113","100,149,237",
    "238,130,238","210,105,30","106,90,205","46,139,87","139,69,19",
]

def render_kmap_html(model, values: Dict[int,str], groups: List[Set[int]]):
    R, C = model["R"], model["C"]
    cell_to_min = model["cell_to_min"]

    # Compute back rectangle geometry (r0,c0,h,w) for each group by scanning
    # Choose a canonical (minimal area, then top-left) rectangle that generates the same set.
    # Because groups are power-of-two rectangles with wrap, we can find an h,w,r0,c0 that matches.
    def find_rect_for_group(minset: Set[int]) -> Tuple[int,int,int,int]:
        target = set(minset)
        for h,w in sorted(all_power2_sizes(R,C), key=lambda s: s[0]*s[1], reverse=True):
            for r0 in range(R):
                for c0 in range(C):
                    cover = {cell_to_min[(r0+dr)%R][(c0+dc)%C] for dr in range(h) for dc in range(w)}
                    if cover == target:
                        return (r0,c0,h,w)
        # Fallback (shouldn't happen)
        return (0,0,1,1)

    # Build HTML
    CELL = 44   # px per cell
    GAP  = 4    # px
    W = C*CELL + (C-1)*GAP
    H = R*CELL + (R-1)*GAP

    # Cells
    cells_html = []
    for r in range(R):
        for c in range(C):
            m = cell_to_min[r][c]
            v = values.get(m, "0")
            cls = "v1" if v=="1" else ("vx" if v in {"X","x","-"} else "v0")
            cells_html.append(
                f"<div class='cell {cls}' style='grid-row:{r+1};grid-column:{c+1};'>"
                f"<div class='minidx'>{m}</div>"
                f"<div class='val'>{v}</div>"
                f"</div>"
            )

    # Groups (layers)
    layers = []
    for gi, g in enumerate(groups):
        color = PALETTE[gi % len(PALETTE)]
        r0,c0,h,w = find_rect_for_group(g)
        for (rs,cs,rh,cw) in _segments_for_wrap(r0,c0,h,w,R,C):
            left = cs*CELL + cs*GAP
            top  = rs*CELL + rs*GAP
            width  = cw*CELL + (cw-1)*GAP
            height = rh*CELL + (rh-1)*GAP
            layers.append(
                f"<div class='group' style="
                f"'left:{left}px;top:{top}px;width:{width}px;height:{height}px;"
                f"background:rgba({color},0.28);border:2px solid rgba({color},0.9);'></div>"
            )

    html = f"""
    <div class="wrap">
      <div class="kmap" style="width:{W}px;height:{H}px;">
        {''.join(cells_html)}
        {''.join(layers)}
      </div>
    </div>
    <style>
      .wrap {{ position:relative; margin: 6px 0 18px 0; }}
      .kmap {{
         position: relative;
         display: grid;
         grid-template-rows: repeat({R}, 1fr);
         grid-template-columns: repeat({C}, 1fr);
         gap: {GAP}px;
         background: #f7f7fb;
         border: 1px solid #ddd;
         border-radius: 10px;
         box-shadow: 0 1px 4px rgba(0,0,0,0.06) inset;
      }}
      .cell {{
         position: relative;
         background: white;
         border: 1px solid #e3e3e3;
         border-radius: 8px;
         display:flex; align-items:center; justify-content:center;
         font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
         font-size: 16px;
         font-weight: 600;
      }}
      .cell .minidx {{
         position:absolute; top:4px; left:6px; font-size: 11px; color:#667; font-weight:500;
      }}
      .cell .val {{
         transform: translateY(1px);
      }}
      .cell.v1 {{ background: #fffefd; border-color:#f1d1d1; }}
      .cell.v0 {{ color:#99a; font-weight:500; }}
      .cell.vx {{ color:#aa6; }}
      .group {{
         position:absolute; pointer-events:none; border-radius: 10px;
      }}
    </style>
    """
    return html

# --------------------------- UI & glue --------------------------------------------

EXAMPLES = [
    "A + B·C",
    "A'B + C(D + E')",
    "a b' + !c",
    "(A + B)(C' + D)  # adjacency means AND",
    "A + B + C",  # <= 3 vars
]

def _parse_minterm_lists(nvars: int, mins_txt: str, dcs_txt: str) -> Tuple[Set[int], Set[int], Optional[str]]:
    def _parse_one(s: str) -> Set[int]:
        s = s.strip()
        if not s: return set()
        raw = re.split(r"[,\s]+", s)
        out = set()
        for t in raw:
            if t == "": continue
            v = int(t)
            out.add(v)
        return out
    try:
        ones = _parse_one(mins_txt)
        dcs  = _parse_one(dcs_txt)
    except ValueError:
        return set(), set(), "Minterms/Don't cares must be integers separated by commas or spaces."
    limit = 1 << nvars
    if any(m < 0 or m >= limit for m in ones | dcs):
        return set(), set(), f"Indices must be in [0, {limit-1}] for {nvars} variables."
    if ones & dcs:
        return set(), set(), "A minterm cannot be both 1 and don't care."
    return ones, dcs, None

def render() -> None:
    st.title("K-Map Minimizer (SOP)")

    st.markdown(
        """
Minimize a **Sum of Products** using a Karnaugh map (**≤ 5 variables**).
Choose **Expression** or **Truth Table** input. The K-map is drawn in **Gray order**
and behaves like a **torus** (groups may wrap around the edges). Overlapping groups
are shown with translucency and distinct colors.
        """
    )

    mode = st.radio("Input type", ["Expression", "Truth Table"], horizontal=True)

    with st.expander("Accepted expression syntax", expanded=False):
        st.markdown(
            r"""
- **Variables:** A–E (case-insensitive).  
- **OR:** `+`, `U`, `V`, `OR`, `|`  
- **AND:** `.`, `x`, `X`, `AND`, `*`, **adjacency** (e.g., `AB` = `A AND B`)  
- **NOT:** trailing prime `'` (e.g., `A'`, `(BC)'`), or `!`, `~`, `NOT`  
- **Spaces** are ignored. Parentheses ok.

**Examples**
`A + B·C`,
`A'B + C(D + E')`,
`a b' + !c`,
`(A + B)(C' + D)`

            """
        )

    if mode == "Expression":
        expr = st.text_input("Boolean expression", EXAMPLES[0])
        var_order_all = [v for v in VAR_SET]  # default A..E
        # We auto-detect used vars; you can still force order via this field if needed.
        if st.button("Minimize (Expression)"):
            # Normalize & detect used variables
            try:
                py_expr, used = _norm_expr(expr)
            except Exception as e:
                st.error(f"Parse error: {e}")
                return
            if not used:
                st.error("No variables found. Use A..E.")
                return
            if len(used) > 5:
                st.error("Use at most 5 variables.")
                return

            nvars = len(used)
            var_order = [v for v in VAR_SET if v in used][:nvars]
            ones = _eval_expr_to_minterms(expr, var_order)
            dcs  = set()

            _run_kmap_pipeline(nvars, var_order, ones, dcs, source_label="(from expression)")

    else:
        col1, col2 = st.columns(2)
        with col1:
            nvars = st.selectbox("Number of variables", [1,2,3,4,5], index=3)
        with col2:
            var_order_str = st.text_input("Variable order (MSB→LSB, subset of A..E)", "ABCDE")
        var_order = [ch for ch in var_order_str if ch.upper() in VAR_SET][:nvars]
        if len(var_order) != nvars:
            var_order = VAR_SET[:nvars]

        st.caption("Truth table via minterm indices (base-10). Use X or don't-care by listing indices below.")
        c1, c2 = st.columns(2)
        with c1:
            mt = st.text_area("Minterms = 1 (indices, comma/space separated)", "1,3,7,11,15")
        with c2:
            dc = st.text_area("Don't-cares (optional)", "")

        if st.button("Minimize (Truth Table)"):
            ones, dcs, err = _parse_minterm_lists(nvars, mt, dc)
            if err:
                st.error(err); return
            _run_kmap_pipeline(nvars, var_order, ones, dcs, source_label="(from minterms)")

def _run_kmap_pipeline(nvars: int, var_order: List[str], ones: Set[int], dcs: Set[int], source_label: str):
    model = build_maps(nvars, var_order)

    # Value map by minterm index
    values: Dict[int,str] = {m:"0" for m in range(1<<nvars)}
    for m in ones: values[m] = "1"
    for m in dcs:
        if values[m] != "1":
            values[m] = "X"

    # Prime implicants and cover
    primes = enumerate_prime_rects(model, ones, dcs)
    cover  = pick_cover(primes, ones)

    # Produce SOP
    terms = [implicant_to_term(g, nvars, var_order) for g in cover]
    sop = " + ".join(t for t in terms) if terms else "0"

    st.subheader("Minimized SOP")
    st.success(f"`F({','.join(var_order)}) = {sop}`  {source_label}")

    # List implicants
    with st.expander("Selected implicants", expanded=True):
        for i, (g, t) in enumerate(zip(cover, terms), start=1):
            st.markdown(f"- **Group {i}**: covers minterms `{sorted(g)}` → term **{t}**")

    # K-map HTML
    st.subheader("K-map (Gray order, torus wrap, layered groups)")
    html = render_kmap_html(model, values, cover)
    st.components.v1.html(html, height= (model["R"]*48 + 40))

    # Small help
    with st.expander("Notes", expanded=False):
        st.markdown(
            """
- **Gray order** on rows/columns ensures every neighbor differs by one bit.
- The map is a **torus**: left↔right and top↔bottom wrap. Groups may span edges.
- Don’t-cares (`X`) can be absorbed to make groups larger, but they don’t need to be covered.
- Result uses **SOP** with `'` for negation and `·` for AND; `+` means OR.
            """
        )
