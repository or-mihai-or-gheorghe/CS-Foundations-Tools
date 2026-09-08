"""A block-level view of the four real ripple-carry stages."""

from __future__ import annotations

from html import escape
from typing import Mapping
import xml.etree.ElementTree as ET

import schemdraw
from schemdraw import elements as elm

from .logic_adder import AdderDefinition
from .logic_circuit_svg import (
    CIRCUIT_FONT_SIZE, CIRCUIT_STROKE_WIDTH, GATE_COLOR, SIGNAL_COLORS,
    SVG_STROKE_STYLE, _validate_values,
)


def render_adder_blocks_svg(adder: AdderDefinition, values: Mapping[str, int]) -> bytes:
    """Show MSB on the left, with carry arrows going from bit 0 to bit 3.

    Every colored connection reads its source in the evaluated gate network;
    the blocks do not calculate a separate arithmetic approximation.
    """
    if len(adder.stages) != 4:
        raise ValueError("The block overview requires four full-adder stages.")
    _validate_values(adder.network.nodes, values)
    drawing = schemdraw.Drawing(canvas="svg", show=False, bgcolor="white", color=GATE_COLOR,
                                inches_per_unit=0.4, fontsize=CIRCUIT_FONT_SIZE,
                                lw=CIRCUIT_STROKE_WIDTH, margin=1.2)

    def label(text, point, *, align="center"):
        drawing.add(elm.Label().right().at(point).label(
            text, loc="center", ofst=0, halign=align, color=GATE_COLOR))

    def wire(source, start, end):
        drawing.add(elm.Arrow(arrowwidth=0.12, arrowlength=0.2)
                    .at(start).to(end).color(SIGNAL_COLORS[values[source]]))

    for stage in adder.stages:
        i = stage.index
        x = (3 - i) * 6.4
        left, right = x - 2.2, x + 2.2
        drawing.add(elm.Rect((left, -1.6), (right, 1.6), fill="white")
                    .right().at((0, 0)))
        label(f"FA{i}", (x, 1.0))
        label("Full adder", (x, 0.25))
        label("Cout", (left + 0.2, -0.45), align="left")
        label("Cin", (right - 0.2, -0.45), align="right")
        label("S", (x, -1.25))
        for operand, source, offset in zip("AB", stage.inputs[:2], (-1.2, 1.2)):
            wire(source, (x + offset, 3.1), (x + offset, 1.6))
            label(f"{operand}{i}={values[source]}", (x + offset, 3.6))
        wire(stage.sum_output, (x, -1.6), (x, -3.0))
        label(f"S{i}={values[stage.sum_output]}", (x, -3.5))
        # The next stage is to the left, as in conventional binary notation.
        wire(stage.carry_output, (left, -0.45), (left - 2.0, -0.45))
        label(f"C{i + 1}={values[stage.carry_output]}", (left - 1.0, 0.1))
        if i == 0:
            source = stage.inputs[2]
            wire(source, (right + 2.0, -0.45), (right, -0.45))
            drawing.add(elm.Dot(open=True, radius=0.07).at((right + 2.0, -0.45)))
            label(f"C0={values[source]}", (right + 1.0, 0.1))
            label("Fixed 0", (right + 1.0, -1.1))

    svg = drawing.get_imagedata("svg")
    root = ET.fromstring(svg)
    x, y, width, height = root.attrib["viewBox"].split()
    outputs = ", ".join(f"{output.name}={values[output.source]}" for output in adder.network.outputs)
    description = ("Four full adders, FA3 to FA0 from left to right. A and B enter above; "
                   "S exits below. Carry travels right to left: C0=0, then C1, C2, C3, C4. "
                   f"{outputs}. 0 is red; 1 is green.")
    additions = ("<title>Four-bit ripple-carry adder: block overview</title>"
                 f"<desc>{escape(description)}</desc>"
                 f"{SVG_STROKE_STYLE}"
                 f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="white"/>').encode()
    end = svg.index(b">", svg.index(b"<svg")) + 1
    return svg[:end] + additions + svg[end:]
