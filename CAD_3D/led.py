"""
3 mm round THT LED - simplified body for placement and interference checks, and the cutter for its panel hole.

Frame: see LedData (origin on the board top surface midway between the leads, leads along X, Z up).

    python CAD_3D/led.py          # build, print a summary, show in ocp_vscode
"""

import build123d as bd

from geom_defs import LedData

BODY_COLOR = bd.Color(0.9, 0.1, 0.1, 0.8)
METAL_COLOR = "#c0c0c0"

# cutter reach above the body, more than any panel thickness
CUTTER_HEIGHT = 30

LED_3MM = LedData()

_Z_MIN = (bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)


def create_led(data: LedData = LED_3MM) -> bd.Compound:
    """LED as an assembly of labelled parts (body, 2 leads) in the LED frame."""
    d = data
    radius = d.body_diameter / 2

    body = bd.Cylinder(d.flange_diameter / 2, d.flange_height, align=_Z_MIN)
    body += bd.Cylinder(radius, d.body_height - radius, align=_Z_MIN)
    body += bd.Pos(0, 0, d.body_height - radius) * bd.Sphere(radius)
    body = bd.Pos(0, 0, d.standoff) * body
    body.label, body.color = "body", BODY_COLOR

    leads = []
    for x, name in ((-d.pin_pitch / 2, "lead_1"), (d.pin_pitch / 2, "lead_2")):
        lead = bd.Pos(x, 0, -d.lead_protrusion) * bd.Box(
            d.lead_section, d.lead_section, d.lead_length_used, align=_Z_MIN
        )
        lead.label, lead.color = name, bd.Color(METAL_COLOR)
        leads.append(lead)

    return bd.Compound(label="LED", children=[body, *leads])


def create_led_cutter(data: LedData = LED_3MM) -> bd.Part:
    """To be subtracted from the panel: the hole for the body above the flange, with hole_clearance all round."""
    return bd.Pos(0, 0, data.standoff + data.flange_height) * bd.Cylinder(
        data.hole_diameter / 2, CUTTER_HEIGHT, align=_Z_MIN
    )


def print_summary(data: LedData = LED_3MM) -> None:
    d = data
    print(
        f"LED body       Z {d.standoff:.2f} .. {d.top_z:.2f}, panel hole {d.hole_diameter:.2f} dia"
    )
    print(
        f"LED leads      {d.lead_length_used:.2f} of {d.lead_length:.2f} used "
        f"({d.standoff:.2f} standoff + {d.lead_protrusion:.2f} below the board top surface)"
    )
    if d.lead_length_used > d.lead_length:
        print("LED leads are too short for this standoff")


if __name__ == "__main__":
    from ocp_vscode import show

    print_summary()
    show(create_led(), create_led_cutter(), alphas=[1, 0.3])
