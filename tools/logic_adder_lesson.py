"""An interactive lesson from AND2/OR2/NOT full adders to an XOR simplification."""

from __future__ import annotations

import base64
from functools import lru_cache
from html import escape

import streamlit as st

from .logic_adder import (
    FULL_ADDER_TABLE, build_four_bit_adder, build_full_adder, build_xor_four_bit_adder,
    evaluate_four_bit, parse_operand,
)
from .logic_adder_svg import build_adder_scene, render_adder_svg
from .logic_adder_block_svg import render_adder_blocks_svg
from .logic_adder_xor_svg import build_xor_adder_scene, render_xor_adder_svg
from .logic_circuit import evaluate_network, gate_counts
from .logic_circuit_svg import build_layout, render_circuit_svg, svg_size_px
from .logic_kmap_sop import build_maps, render_kmap_html


_ONE_BIT_GROUPS = ("sum_bit", "sum_circuit", "carry_bit", "carry_circuit", "full_adder")
_ONE_BIT_DEFAULTS = {"A": True, "B": True, "Cin": False}


def _one_bit_key(group, name):
    return f"adder_input_{name}" if group == "sum_bit" else f"adder_input_{group}_{name}"


def _prepare_one_bit_inputs():
    """Hydrate all widget copies before rendering from persistent shared state."""
    if "adder_one_bit_inputs" not in st.session_state:
        st.session_state["adder_one_bit_inputs"] = {
            name: bool(st.session_state.get(f"adder_input_{name}", initial))
            for name, initial in _ONE_BIT_DEFAULTS.items()
        }
    values = st.session_state["adder_one_bit_inputs"]
    for group in _ONE_BIT_GROUPS:
        for name in _ONE_BIT_DEFAULTS:
            st.session_state[_one_bit_key(group, name)] = values[name]
    return {name: int(values[name]) for name in _ONE_BIT_DEFAULTS}


def _set_one_bit_input(name, key):
    # Callbacks run before the next render, so earlier diagrams update too.
    st.session_state["adder_one_bit_inputs"] = {
        **st.session_state["adder_one_bit_inputs"], name: bool(st.session_state[key]),
    }


def _one_bit_switches(group):
    with st.container(horizontal=True, key=f"adder_controls_{group}"):
        for name in _ONE_BIT_DEFAULTS:
            key = _one_bit_key(group, name)
            st.toggle(f"{name}={int(st.session_state[key])}", key=key,
                      help="Off = 0; on = 1. All copies stay synchronized.",
                      on_change=_set_one_bit_input, args=(name, key))


@lru_cache(maxsize=1)
def _lesson_assets():
    full = build_full_adder()
    four = build_four_bit_adder()
    return (full, four, build_layout(full.sum_circuit), build_layout(full.carry_circuit),
            build_adder_scene(full), build_adder_scene(four))


@lru_cache(maxsize=1)
def _xor_assets():
    four = build_xor_four_bit_adder()
    return four, build_xor_adder_scene(four)


def _term(cube):
    return "·".join(name if bit else f"{name}'"
                    for name, bit in zip(("A", "B", "Cin"), cube.literals)
                    if bit is not None) or "1"


def _table(headers, rows, *, name, active_row=None):
    """Use a static HTML table so all eight truth-table rows remain visible."""
    body = []
    for index, row in enumerate(rows):
        selected = index == active_row
        marker = " class='adder-selected' aria-current='true'" if selected else ""
        cells = "".join(f"<td>{escape(str(value))}</td>" for value in row)
        body.append(f"<tr{marker}>{cells}</tr>")
    st.html(
        f"<table class='adder-lesson-table' aria-label='{escape(name, quote=True)}'>"
        "<thead><tr>" + "".join(f"<th scope='col'>{escape(str(h))}</th>" for h in headers)
        + "</tr></thead><tbody>" + "".join(body) + "</tbody></table>"
        "<style>.adder-lesson-table {border-collapse:collapse;width:100%;max-width:640px;"
        "font-variant-numeric:tabular-nums;font-size:0.95rem;}"
        ".adder-lesson-table th,.adder-lesson-table td {padding:0.3rem 0.5rem;"
        "border-bottom:1px solid #94a3b866;text-align:center;}"
        ".adder-lesson-table .adder-selected {background:#e2e8f0;color:#17212b;font-weight:700;}"
        "</style>"
    )


def _truth_table(output_index, active_minterm, output_name):
    rows = [(*row[:3], row[output_index], "Active" if m == active_minterm else "")
            for m, row in enumerate(FULL_ADDER_TABLE)]
    _table(("A", "B", "Cin", output_name, "State"), rows,
           name=f"{output_name} truth table", active_row=active_minterm)


def _diagram(name, signature, render_svg, description):
    """Retain only the most recent SVG for each lesson diagram."""
    key = f"adder_svg_{name}"
    previous = st.session_state.get(key)
    if previous is None or previous["signature"] != signature:
        previous = {"signature": signature, "data": render_svg()}
        st.session_state[key] = previous
    svg_bytes = previous["data"]
    width, height = svg_size_px(svg_bytes)
    encoded = base64.b64encode(svg_bytes).decode("ascii")
    st.html(
        f'<div role="region" aria-label="{escape(description, quote=True)}">'
        f'<img alt="{escape(description, quote=True)}" src="data:image/svg+xml;base64,{encoded}" '
        f'style="display:block;width:{width * 0.5:.2f}px;max-width:100%;height:auto;'
        f'aspect-ratio:{width:.6f}/{height:.6f};" /></div>'
    )
    st.download_button(f"Download {name.replace('_', ' ')} SVG", svg_bytes,
                       file_name=f"adder_{name}.svg", mime="image/svg+xml",
                       key=f"adder_download_{name}")


def _function_section(full, result, circuit, layout, values, signature, name, title, explanation):
    st.header(title)
    _one_bit_switches(f"{name}_bit")
    st.markdown(explanation)
    minterm = signature[0] * 4 + signature[1] * 2 + signature[2]
    output = "S" if name == "sum" else "Cout"
    # Horizontal containers wrap whole panels; 300 px also fits the K-map.
    with st.container(horizontal=True, key=f"adder_{name}_analysis"):
        with st.container(width=300, key=f"adder_{name}_truth_table"):
            st.subheader("Truth table")
            _truth_table(3 if name == "sum" else 4, minterm, output)
        with st.container(width=300, key=f"adder_{name}_kmap"):
            st.subheader("Karnaugh map")
            model = build_maps(3, list(result.var_order))
            cell_values = {m: str(int(m in result.ones)) for m in range(8)}
            st.html(render_kmap_html(model, cell_values, result.cover,
                                    input_labels={"C": "Cin"}, compact_headers=True,
                                    active_minterm=minterm))
            st.caption("Rows: A. Columns: (B, Cin) in Gray order 00, 01, 11, 10. "
                       "The dark dashed outline marks the current input, even when its output is 0.")
        with st.container(width=300, key=f"adder_{name}_groups"):
            st.subheader("Minimized function")
            st.code(f"{output} = " + " + ".join(_term(cube) for cube in result.cover),
                    language=None, wrap_lines=True)
            for index, cube in enumerate(result.cover, 1):
                st.markdown(f"**G{index} / T{index}:** `{sorted(cube.covered_minterms)}` → `{_term(cube)}`")
    stage = full.stages[0]
    mapping = stage.sum_nodes if name == "sum" else stage.carry_nodes
    local_values = {local: values[global_id] for local, global_id in mapping}
    counts = gate_counts(circuit)
    st.subheader(f"{output} circuit")
    _one_bit_switches(f"{name}_circuit")
    st.caption(f"{counts['AND']} AND + {counts['OR']} OR + {counts['NOT']} NOT "
               f"= {counts['total']} gates. Each G number matches its product term T.")
    st.metric(output, str(local_values[circuit.output]))
    _diagram(name, signature, lambda: render_circuit_svg(
        circuit, layout, local_values, input_labels={"C": "Cin"}, output_label=output),
        f"AND/OR/NOT {output} circuit; A={signature[0]}, B={signature[1]}, "
        f"Cin={signature[2]}; {output}={local_values[circuit.output]}.")


def render():
    st.title("4-bit Adder (AND/OR/NOT)")
    st.markdown(
        "Build an unsigned binary adder step by step: **sum bit → carry bit → "
        "one full adder → four connected full adders**. Every AND and OR gate has "
        "exactly two inputs; each NOT gate has one input. Finally, simplify the "
        "same adder using two-input XOR gates."
    )
    st.caption("Wire values: 0 = red, 1 = green. Dots mark connections; crossings without "
               "dots are separate wires. Each diagram fits the page width and keeps its "
               "full height. Download its SVG to enlarge details, especially on a phone.")
    full, four, sum_layout, carry_layout, full_scene, four_scene = _lesson_assets()

    assignment = _prepare_one_bit_inputs()
    signature = tuple(assignment[name] for name in full.network.var_order)
    values = evaluate_network(full.network, assignment)
    stage = full.stages[0]
    st.caption("The A, B and Cin switches beside each one-bit section stay synchronized. "
               "They control both truth tables, both K-maps and the first three circuits. "
               "Cin is the carry arriving from the previous bit. "
               f"Current minterm: m = 4A + 2B + Cin = {signature[0]*4+signature[1]*2+signature[2]}.")
    st.info("In the Boolean formulas below, + means OR, · means AND and ' means NOT.")

    _function_section(full, full.sum_result, full.sum_circuit, sum_layout, values, signature,
                      "sum", "1. Sum bit — S",
                      "The sum bit is 1 when **an odd number of the three input bits is 1**. "
                      "The four 1 cells in its K-map have no adjacent 1 cells, including "
                      "across the map edges, so each remains a separate group.")
    _function_section(full, full.carry_result, full.carry_circuit, carry_layout, values, signature,
                      "carry", "2. Carry bit — Cout",
                      "The carry bit is 1 when **at least two input bits are 1**. "
                      "Three groups of two cells give the three product terms. The cell "
                      "for minterm 7 belongs to every group: **overlapping groups are allowed**.")

    st.header("3. One-bit full adder")
    _one_bit_switches("full_adder")
    st.markdown("Connect both branches to the **same A, B and Cin inputs**. The separate "
                "outputs are S and Cout. This SOP construction has **19 gates: 14 for S "
                "and 5 for Cout**. We preserve these branches to show how the maps become "
                "a circuit; this is not a claim of the smallest possible gate count.")
    _diagram("full_adder", signature, lambda: render_adder_svg(full, full_scene, values),
             f"One-bit full adder; A={signature[0]}, B={signature[1]}, Cin={signature[2]}; "
             f"S={values[stage.sum_output]}, Cout={values[stage.carry_output]}.")

    st.header("4. Four-bit ripple-carry adder")
    st.markdown("Repeat the full adder four times: **FA₀ → FA₁ → FA₂ → FA₃**. "
                "Each carry output connects to the next carry input. The initial carry "
                "**C₀ is fixed at 0 inside the circuit**, so there are only eight external "
                "input bits. All four stages keep their 19 gates: **76 gates in total**.")
    st.markdown("Write each operand **most significant bit first**, from bit 3 to bit 0. "
                "Addition starts at FA₀ with the **rightmost bit**, then the carry travels "
                "through the stages with weights 1, 2, 4 and 8.")
    st.caption("These two operands control the four-bit simulator independently of the "
               "one-bit switches. Press Enter or leave a field to update the result. "
               "The colors show the stable logical result, without physical gate delays.")
    left, right = st.columns(2)
    with left:
        a_text = st.text_input("Operand A (A3 A2 A1 A0)", "0101", key="adder_operand_a")
    with right:
        b_text = st.text_input("Operand B (B3 B2 B1 B0)", "0011", key="adder_operand_b")
    operands = []
    for name, text in (("A", a_text), ("B", b_text)):
        try:
            operands.append(parse_operand(text))
        except ValueError as exc:
            st.error(f"Operand {name}: {exc}")
    if len(operands) != 2:
        return
    a, b = operands
    result = evaluate_four_bit(four, a, b)
    col1, col2, col3 = st.columns(3)
    col1.metric("Sum (4 bits)", result.sum_bits)
    col2.metric("Carry C4", str(result.carry_out))
    col3.metric("Full result (5 bits)", result.full_bits)
    st.caption(f"Unsigned operands: A = {a}₂ = {int(a, 2)}, B = {b}₂ = {int(b, 2)}. "
               f"Four-bit sum = {int(result.sum_bits, 2)}; full result = {int(result.full_bits, 2)}.")
    st.markdown("**C₄ indicates overflow beyond four unsigned bits.** The main result is "
                "S₃S₂S₁S₀; prefix it with C₄ to retain the complete five-bit sum.")
    with st.container(horizontal=True, key="adder_four_bit_overview"):
        # Keep the block SVG at its 50% size when both panels fit side by side.
        with st.container(width=580, key="adder_block_overview"):
            st.subheader("Block overview")
            st.caption("Each box contains one complete full adder. Bit 3 is on the left and bit 0 "
                       "on the right, like the operands you entered. The arrows show carry moving "
                       "right to left, from the fixed C₀ = 0 to the final C₄.")
            _diagram("four_bit_blocks", (a, b), lambda: render_adder_blocks_svg(four, result.values),
                     f"Four-bit full-adder block overview; A={a}, B={b}; "
                     f"S={result.sum_bits}, C4={result.carry_out}.")
        with st.container(width=380, key="adder_carry_trace"):
            st.subheader("Follow the carry")
            _table(("i", "Aᵢ", "Bᵢ", "Cᵢ", "Sᵢ", "Cᵢ₊₁"), result.stages,
                   name="Four-bit carry propagation")
            st.caption("At every stage: Aᵢ + Bᵢ + Cᵢ = Sᵢ + 2·Cᵢ₊₁. "
                       "Try 1111 + 0001 to follow a carry through all four stages.")
    st.subheader("Complete AND/OR/NOT circuit")
    st.caption("The same four blocks are expanded below, with FA₀ at the top and FA₃ "
               "at the bottom. Carry now travels downward through the same connections.")
    _diagram("four_bit", (a, b), lambda: render_adder_svg(four, four_scene, result.values),
             f"Four-bit ripple-carry circuit; A={a}, B={b}; "
             f"S={result.sum_bits}, C4={result.carry_out}.")

    st.header("5. Simplify with XOR")
    st.markdown("A two-input **XOR** gate outputs 1 when its inputs differ. The symbol "
                "⊕ means XOR. Reuse the intermediate signal Pᵢ = Aᵢ ⊕ Bᵢ in both "
                "branches of each full adder:")
    st.code("Pᵢ = Aᵢ ⊕ Bᵢ\nSᵢ = Pᵢ ⊕ Cᵢ\nCᵢ₊₁ = Aᵢ·Bᵢ + Pᵢ·Cᵢ", language=None)
    st.markdown("The carry is 1 when **both operand bits are 1**, or when **exactly one "
                "operand bit is 1 and an incoming carry is present**. This gives the "
                "same sum and carry truth tables as the AND/OR/NOT construction.")
    xor_four, xor_scene = _xor_assets()
    xor_result = evaluate_four_bit(xor_four, a, b)
    counts = gate_counts(xor_four.network)
    st.caption(f"Per bit: 2 XOR + 2 AND + 1 OR = 5 gates. Four bits: {counts['XOR']} XOR "
               f"+ {counts['AND']} AND + {counts['OR']} OR = {counts['total']} gates "
               "instead of 76. This counts XOR as one gate; its internal construction "
               "is not expanded. All gates have two inputs.")
    st.caption(f"Uses the same operands above: {a} + {b} → S = {xor_result.sum_bits}, "
               f"C₄ = {xor_result.carry_out}, full result = {xor_result.full_bits}. "
               "C₀ stays fixed at 0; carry connects FA₀ through FA₃ from top to bottom.")
    _diagram("four_bit_xor", (a, b), lambda: render_xor_adder_svg(
        xor_four, xor_scene, xor_result.values),
        f"Simplified four-bit XOR/AND/OR circuit; A={a}, B={b}; "
        f"S={xor_result.sum_bits}, C4={xor_result.carry_out}.")
