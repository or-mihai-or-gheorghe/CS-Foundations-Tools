# tools/logic_kmap_sop.py
#
# K-Map SOP minimizer (≤ 5 variables):
#  - Input: Boolean expression OR minterms/don’t-cares
#  - Expression parser accepts multiple notations (case-insensitive):
#    OR:  + , U , V , OR , | 
#    AND: . , x , X , AND , * , adjacency (e.g., AB = A AND B)
#    NOT: ' (prime after symbol or ')', ! , ~ , NOT
#  - Auto-build truth table from expression
#  - Exact SOP cover, K-map groups, and two-input logic circuit simulation
#
# Display: Streamlit, HTML/CSS, and Schemdraw SVG

from __future__ import annotations
import ast
import base64
from html import escape
import re
import itertools as it
from typing import List, Tuple, Dict, Set, Optional
import streamlit as st

from tools.logic_minimization import Cube, cube_segments, minimize_sop, normalize_var_order
from tools.logic_circuit import build_circuit, evaluate_circuit, gate_counts
from tools.logic_circuit_svg import build_layout, render_circuit_svg, svg_size_px

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
    # Recognize words before removing their whitespace boundaries.
    s = re.sub(_OR_ALIASES, '|', s, flags=re.IGNORECASE)
    s = re.sub(_AND_ALIASES, '&', s, flags=re.IGNORECASE)
    s = re.sub(_NOT_ALIASES, '!', s, flags=re.IGNORECASE)
    s = re.sub(r"[\s_]+", "", s)
    # Retain the original pass for existing forms such as N_O_T(A).
    s = re.sub(_OR_ALIASES, '|', s, flags=re.IGNORECASE)
    s = re.sub(_AND_ALIASES, '&', s, flags=re.IGNORECASE)
    s = re.sub(_NOT_ALIASES, '!', s, flags=re.IGNORECASE)
    s = s.upper()
    if not re.fullmatch(r"[A-E01&|!()']+", s):
        raise ValueError("Use variables A–E, constants 0/1, and supported Boolean operators.")

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
    # Convert the canonical format to Python, then validate its syntax below.

    # First, handle all forms of negation (postfix ' and prefix !).
    # The order is crucial: handle specific primes before the general '!' prefix.
    # Repeat for supported chains of negation such as A''.
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

    try:
        parsed = ast.parse(s, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid Boolean expression syntax. Check operators and parentheses.") from exc
    allowed_nodes = (
        ast.Expression, ast.BoolOp, ast.UnaryOp, ast.Name, ast.Load,
        ast.And, ast.Or, ast.Not, ast.Constant,
    )
    for node in ast.walk(parsed):
        if not isinstance(node, allowed_nodes):
            raise ValueError("Only Boolean operations on A–E and constants 0/1 are supported.")
        if isinstance(node, ast.Name) and node.id not in VAR_SET:
            raise ValueError("Use variables A–E only.")
        if isinstance(node, ast.Constant) and (
            type(node.value) is not int or node.value not in (0, 1)
        ):
            raise ValueError("Only Boolean constants 0 and 1 are supported.")

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
        val = eval(py_expr, {"__builtins__": {}}, env)  # Boolean syntax and names validated above.
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

# --------------------------- HTML rendering (layered groups) -----------------------

PALETTE = [
    "255,99,132","54,162,235","255,206,86","75,192,192","153,102,255",
    "255,159,64","199,199,199","255,99,71","60,179,113","100,149,237",
    "238,130,238","210,105,30","106,90,205","46,139,87","139,69,19",
]

def render_kmap_html(model, values: Dict[int,str], groups: Tuple[Cube, ...], *,
                     input_labels=None, compact_headers=False, active_minterm=None):
    """Render groups, with optional lesson labels and a selected input cell.

    Compact headers name each axis once and show only Gray bits beside cells.
    The selection is independent of the cell's Boolean value and group cover.
    """
    R, C = model["R"], model["C"]
    rb, cb = model["rb"], model["cb"]
    rows_gray, cols_gray = model["rows_gray"], model["cols_gray"]
    var_order = model["var_order"]
    cell_to_min = model["cell_to_min"]
    labels = {name: escape(str((input_labels or {}).get(name, name))) for name in var_order}
    if active_minterm is not None and active_minterm not in model["min_to_cell"]:
        raise ValueError("Selected minterm must belong to the K-map.")

    CELL = 44
    GAP  = 4
    W = C*CELL + (C-1)*GAP
    H = R*CELL + (R-1)*GAP

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

    layers = []
    group_labels = []
    occupied_labels = set()
    for gi, g in enumerate(groups):
        color = PALETTE[gi % len(PALETTE)]
        segments = cube_segments(g, cell_to_min)
        for si, (rs,cs,rh,cw) in enumerate(segments):
            left = cs*CELL + cs*GAP
            top  = rs*CELL + rs*GAP
            width  = cw*CELL + (cw-1)*GAP
            height = rh*CELL + (rh-1)*GAP
            layers.append(
                f"<div class='group' data-group='{gi+1}' title='Group {gi+1}' style="
                f"'left:{left}px;top:{top}px;width:{width}px;height:{height}px;"
                f"background:rgba({color},0.20);border:2px solid rgba({color},0.9);'></div>"
            )
            # Give each segment a readable badge inside one of its cells.
            # Separate badges from the colored layers so later groups cannot
            # cover an earlier group's identifier at a shared corner.
            cells = [(r, c) for r in range(rs, rs + rh)
                     for c in reversed(range(cs, cs + cw))]
            slots = [(r, c, corner) for corner in range(3) for r, c in cells]
            r, c, corner = next(slot for slot in slots if slot not in occupied_labels)
            occupied_labels.add((r, c, corner))
            label_left = c * (CELL + GAP) + (1 if corner == 2 else CELL - 21)
            label_top = r * (CELL + GAP) + (1 if corner == 0 else CELL - 11)
            part = sorted(cell_to_min[r][c] for r, c in cells)
            description = f"Group {gi+1}, part {si+1} of {len(segments)}: minterms {part}"
            group_labels.append(
                f"<span class='group-label' data-group='{gi+1}' data-segment='{si+1}' "
                f"title='{escape(description, quote=True)}' "
                f"style='left:{label_left}px;top:{label_top}px;'>G{gi+1}</span>"
            )

    if active_minterm is not None:
        r, c = model["min_to_cell"][active_minterm]
        layers.append(
            f"<div class='active-cell' data-active-minterm='{active_minterm}' "
            f"role='img' aria-label='Selected input: minterm {active_minterm}, "
            f"output {escape(str(values.get(active_minterm, '0')))}' "
            f"style='left:{c*(CELL+GAP)+5}px;top:{r*(CELL+GAP)+14}px;"
            f"width:{CELL-10}px;height:{CELL-19}px;'></div>"
        )

    # --- put headers OUTSIDE the grid (reserve space around it) ---
    PAD_L = 72 if rb > 0 else 0   # left gutter for row labels
    PAD_T = (68 if compact_headers else 48) if cb > 0 else 0

    row_hdrs = []
    if rb > 0:
        row_vars_label = ",".join(labels[name] for name in var_order[:rb]) if compact_headers else "".join(labels[name] for name in var_order[:rb])
        if compact_headers:
            row_hdrs.append(f"<div class='rowhdr' style='left:8px;top:{PAD_T-29}px;'>"
                            f"{row_vars_label}</div>")
        for r, rcode in enumerate(rows_gray):
            bits = format(rcode, f"0{rb}b")
            cy = PAD_T + r*CELL + r*GAP + CELL/2
            row_hdrs.append(
                f"<div class='rowhdr' style='top:{cy}px;left:8px;transform:translateY(-50%);'>"
                f"{bits if compact_headers else row_vars_label + ' - ' + bits}</div>"
            )

    col_hdrs = []
    if cb > 0:
        col_vars_label = ",".join(labels[name] for name in var_order[rb:rb+cb]) if compact_headers else "".join(labels[name] for name in var_order[rb:rb+cb])
        if compact_headers:
            col_hdrs.append(f"<div class='colhdr' style='left:{PAD_L+W/2}px;top:3px;"
                            f"transform:translateX(-50%);'>({col_vars_label})</div>")
        for c, ccode in enumerate(cols_gray):
            bits = format(ccode, f"0{cb}b")
            cx = PAD_L + c*CELL + c*GAP + CELL/2
            col_hdrs.append(
                f"<div class='colhdr' style='left:{cx}px;top:{35 if compact_headers else 8}px;transform:translateX(-50%);'>"
                f"{bits if compact_headers else col_vars_label + '<br>' + bits}</div>"
            )

    html = f"""
    <div class="logic-kmap-display">
    <div class="wrap" style="padding-left:{PAD_L}px;padding-top:{PAD_T}px;">
      <div class="kmap" style="width:{W}px;height:{H}px;">
        {''.join(cells_html)}
        {''.join(layers)}
        {''.join(group_labels)}
      </div>
      {''.join(row_hdrs)}
      {''.join(col_hdrs)}
    </div>
    <style>
      .logic-kmap-display .wrap {{ position:relative; margin: 6px 0 18px 0; }}
      .logic-kmap-display .kmap {{
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
      .logic-kmap-display .cell {{
         position: relative;
         background: white;
         color: #17212b;
         border: 1px solid #e3e3e3;
         border-radius: 8px;
         display:flex; align-items:center; justify-content:center;
         font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
         font-size: 16px;
         font-weight: 600;
      }}
      .logic-kmap-display .cell .minidx {{ position:absolute; top:4px; left:6px; font-size: 11px; color:#667; font-weight:500; }}
      .logic-kmap-display .cell .val {{ transform: translateY(1px); }}
      .logic-kmap-display .cell.v1 {{ background: #fffefd; border-color:#f1d1d1; }}
      .logic-kmap-display .cell.v0 {{ color:#99a; font-weight:500; }}
      .logic-kmap-display .cell.vx {{ color:#aa6; }}
      .logic-kmap-display .group {{ position:absolute; pointer-events:none; border-radius: 10px; z-index:1; }}
      .logic-kmap-display .group-label {{ position:absolute; z-index:3; width:20px; height:10px;
                       box-sizing:border-box; text-align:center; font:9px/10px monospace;
                       color:#223; background:#ffffffee; border-radius:3px; padding:0 1px; }}
      .logic-kmap-display .active-cell {{ position:absolute; z-index:2; pointer-events:none;
                      border:2px dashed #17212b; border-radius:4px; box-sizing:border-box; }}
      .logic-kmap-display .rowhdr, .logic-kmap-display .colhdr {{
         position:absolute; z-index:3;
         font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
         font-size: 12px; color:#445;
         background: rgba(255,255,255,0.92);
         border: 1px solid #e3e3e3; border-radius: 6px;
         padding: 2px 6px; pointer-events:none; white-space: pre; text-align:center;
      }}
    </style>
    </div>
    """
    return html

# --------------------------- UI & glue --------------------------------------------

EXAMPLES = [
    "A + B·C",
    "A'B + C(D + E')",
    "a b' + !c",
    "(A + B)(C' + D)",  # adjacency means AND
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

def _clear_result() -> None:
    st.session_state.pop("kmap_result", None)
    for key in list(st.session_state):
        if key.startswith("kmap_sim_") or key.startswith("kmap_zoom_"):
            del st.session_state[key]


def _store_result(nvars, var_order, ones, dcs, signature, source_label):
    result = minimize_sop(nvars, ones, dcs, var_order=var_order)
    circuit = build_circuit(result.cover, result.var_order)
    layout = build_layout(circuit)
    _clear_result()
    generation = st.session_state.get("kmap_generation", 0) + 1
    st.session_state["kmap_generation"] = generation
    st.session_state["kmap_result"] = {
        "minimization": result, "circuit": circuit, "layout": layout,
        "generation": generation, "signature": signature, "source_label": source_label,
    }
    st.session_state["kmap_needs_minimize"] = False


def render() -> None:
    st.title("K-Map Minimizer (SOP)")
    st.markdown(
        "Minimize a **Sum of Products** for **1–5 variables**, then explore its "
        "**AND/OR/NOT circuit**. AND and OR gates each have exactly two inputs."
    )
    mode = st.radio("Input type", ["Expression", "Truth Table"], horizontal=True,
                    key="kmap_input_mode")
    with st.expander("Accepted expression syntax", expanded=False):
        st.markdown(
            """
- **Variables:** A–E (case-insensitive).
- **OR:** `+`, `U`, `V`, `OR`, `|`
- **AND:** `.`, `x`, `X`, `AND`, `*`, adjacency (e.g. `AB`)
- **NOT:** trailing prime `'`, or `!`, `~`, `NOT`
- Spaces are ignored. Parentheses are supported.

Examples: `A + B·C`, `A'B + C(D + E')`, `a b' + !c`, `(A + B)(C' + D)`.
            """
        )

    if mode == "Expression":
        expr = st.text_input("Boolean expression", EXAMPLES[0], key="kmap_expression")
        signature = (mode, expr)
        minimize = st.button("Minimize (Expression)", key="kmap_minimize_expression")
    else:
        col1, col2 = st.columns(2)
        with col1:
            nvars = st.selectbox("Number of variables", [1, 2, 3, 4, 5], index=3,
                                key="kmap_nvars")
        with col2:
            order_text = st.text_input("Variable order (first n letters, MSB→LSB)",
                                       "ABCDE", key="kmap_variable_order")
        st.caption("Use distinct A–E variables. Minterms are base-10 indices in this order.")
        col1, col2 = st.columns(2)
        with col1:
            mt = st.text_area("Minterms = 1 (indices, comma/space separated)",
                              "1,3,7,11,15", key="kmap_minterms")
        with col2:
            dc = st.text_area("Don't-cares (optional)", "", key="kmap_dont_cares")
        signature = (mode, nvars, order_text, mt, dc)
        minimize = st.button("Minimize (Truth Table)", key="kmap_minimize_truth_table")

    previous_signature = st.session_state.get("kmap_source_signature")
    if previous_signature != signature:
        _clear_result()
        st.session_state["kmap_source_signature"] = signature
        st.session_state["kmap_needs_minimize"] = previous_signature is not None

    if minimize:
        _clear_result()
        try:
            if mode == "Expression":
                _, used = _norm_expr(expr)
                if not used:
                    raise ValueError("No variables found. Use A..E.")
                nvars = len(used)
                var_order = tuple(used)
                ones = _eval_expr_to_minterms(expr, list(var_order))
                dcs = set()
                source_label = "(from expression)"
            else:
                var_order = normalize_var_order(nvars, order_text)
                ones, dcs, err = _parse_minterm_lists(nvars, mt, dc)
                if err:
                    raise ValueError(err)
                source_label = "(from minterms)"
        except ValueError as exc:
            st.error(f"Input error: {exc}")
            return
        with st.spinner("Minimizing and drawing the circuit…"):
            _store_result(nvars, var_order, ones, dcs, signature, source_label)

    snapshot = st.session_state.get("kmap_result")
    if snapshot is not None:
        _render_result(snapshot)
    elif st.session_state.get("kmap_needs_minimize"):
        st.caption("Inputs changed. Select Minimize to calculate a new result.")


def _render_result(snapshot):
    result = snapshot["minimization"]
    model = build_maps(result.nvars, list(result.var_order))
    values = {m: "1" if m in result.ones else "X" if m in result.dont_cares else "0"
              for m in range(1 << result.nvars)}

    st.subheader("Minimized SOP")
    st.success(f"`F({','.join(result.var_order)}) = {result.sop}`  {snapshot['source_label']}")
    st.caption("Minimum number of SOP terms, then minimum literal count. "
               "This circuit implements that SOP using two-input AND/OR gates.")
    st.subheader("Selected implicants")
    for index, (cube, term) in enumerate(zip(result.cover, result.terms), 1):
        st.markdown(f"- **Group {index} / T{index}**: minterms "
                    f"`{sorted(cube.covered_minterms)}` → **{term}**")
        segments = cube_segments(cube, model["cell_to_min"])
        if len(segments) > 1:
            parts = [sorted(model["cell_to_min"][r][c]
                            for r in range(rs, rs + rh) for c in range(cs, cs + cw))
                     for rs, cs, rh, cw in segments]
            st.caption(f"G{index} is one group drawn in {len(parts)} parts: "
                       + " and ".join(str(part) for part in parts) + ".")
    if not result.cover:
        st.caption("No product terms are needed: F = 0.")

    st.subheader("K-map (Karnaugh)")
    html = render_kmap_html(model, values, result.cover)
    height = model["R"] * 44 + (model["R"] - 1) * 4 + 68
    st.iframe(html, height=height)
    st.caption("Parts with the same G number belong to one logical group, including across map edges. "
               "For five variables, cells that differ in one variable can be separated visually. "
               "X cells can enlarge a group but do not need to be covered.")
    _render_circuit(snapshot)


def _render_circuit(snapshot):
    circuit = snapshot["circuit"]
    result = snapshot["minimization"]
    generation = snapshot["generation"]
    st.subheader("Logic circuit")
    counts = gate_counts(circuit)
    st.caption(f"AND: {counts['AND']} · OR: {counts['OR']} · NOT: {counts['NOT']} "
               f"· Total: {counts['total']}. AND/OR: 2 inputs; NOT: 1 input.")

    used_signals = {signal for node in circuit.nodes for signal in node.inputs}
    if circuit.output:
        used_signals.add(circuit.output)
    used_variables = {node.variable for node in circuit.nodes
                      if node.kind == "INPUT" and node.id in used_signals}
    assignment = {}
    for column, variable in zip(st.columns(len(circuit.var_order)), circuit.var_order):
        with column:
            label = variable if variable in used_variables else f"{variable} (unused)"
            assignment[variable] = int(st.toggle(label, value=False,
                key=f"kmap_sim_{generation}_{variable}", help="Off = 0; on = 1."))
    zoom = st.slider("Circuit zoom (%)", 25, 200, 100, step=25,
                     key=f"kmap_zoom_{generation}")

    signals = evaluate_circuit(circuit, assignment)
    st.metric("F", str(signals[circuit.output]))
    bits = tuple(assignment[var] for var in circuit.var_order)
    minterm = bitstr_to_int(list(bits))
    inputs_text = ", ".join(f"{var}={assignment[var]}" for var in circuit.var_order)
    expected = "X (don't-care)" if minterm in result.dont_cares else str(int(minterm in result.ones))
    st.caption(f"Inputs: {inputs_text} · Minterm: {minterm} · Specified output: {expected}")
    if minterm in result.dont_cares:
        st.caption("This input is unspecified. The chosen circuit produces the concrete F value shown above.")

    if snapshot.get("svg_assignment") != bits:
        snapshot["svg_bytes"] = render_circuit_svg(circuit, snapshot["layout"], signals)
        snapshot["svg_assignment"] = bits
    svg_bytes = snapshot["svg_bytes"]
    width, height = svg_size_px(svg_bytes)
    image_data = base64.b64encode(svg_bytes).decode("ascii")
    description = escape(f"AND/OR/NOT circuit for F = {result.sop}. {inputs_text}; F={signals[circuit.output]}.")
    # Fit the whole circuit to the page width and let its height grow naturally.
    # Reserve its aspect ratio while the browser decodes the SVG image.
    # SVG is an image because st.html's HTML-only sanitizer removes inline svg.
    st.html(
        f'<div role="region" aria-label="Logic circuit diagram">'
        f'<img alt="{description}" src="data:image/svg+xml;base64,{image_data}" '
        f'style="display:block;width:{width * zoom / 100:.2f}px;max-width:100%;'
        f'height:auto;aspect-ratio:{width:.6f}/{height:.6f};" />'
        '</div>'
    )
    st.caption("Wire values: 0 = red, 1 = green. Dots mark connections; crossings without dots are separate wires. "
               "The diagram scales to fit the page width.")
    st.download_button("Download SVG", data=svg_bytes, file_name="kmap_circuit.svg",
                       mime="image/svg+xml", key="kmap_download_svg")
