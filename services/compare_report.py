"""Planner-facing PDF from saved comparison evidence; no simulation or data mutation."""
from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.graphics.shapes import Drawing, Line, Rect, String, Circle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

from services.metric_definitions import metric_value, METRIC_DEFINITIONS

BLUE = colors.HexColor("#2463A5")
GREEN = colors.HexColor("#087F68")
INK = colors.HexColor("#183344")
MUTED = colors.HexColor("#526575")
LIGHT = colors.HexColor("#EDF3F5")
WIDTH = A4[0] - 76
PHASE_COLORS = {"north": "#2463A5", "east": "#087F68", "south": "#9156AA", "west": "#CE6B25", "pedestrian": "#156E85"}
KEYS = ["avg_wait", "throughput", "avg_queue", "max_queue", "unfinished_vehicles", "avg_ped_delay"]


def text(value) -> str:
    return str(value).replace("\u2014", "-").replace("\u2013", "-").replace("\u00d7", "x").replace("\u2192", "to").encode("latin-1", "replace").decode("latin-1")


def number(value, digits=1):
    return "Unavailable" if value is None else f"{value:,.{digits}f}"


def controller(bundle):
    run = bundle["option"]["run"]
    mode = run.get("control_mode", "unknown")
    name = {"fixed-time": "Fixed-time signal", "no-signal": "No signal"}.get(mode, str(mode).upper())
    return name + (f" model #{run['rl_model_id']}" if run.get("rl_model_id") else "")


def phase_label(phase):
    return str(phase).replace("_GREEN", "").replace("_YELLOW", "").replace("_", " ").title()


def phase_color(segment):
    if segment["stage"] == "yellow": return colors.HexColor("#E9AD2F")
    if segment["stage"] == "red": return colors.HexColor("#D65151")
    if segment["stage"] in {"unknown", "unsignalized"}: return colors.HexColor("#B1BCC3")
    return colors.HexColor(PHASE_COLORS.get(phase_label(segment["phase"]).lower(), "#156E85"))


def bars(pair):
    d = Drawing(WIDTH, 186)
    for i, key in enumerate(KEYS):
        y = 166 - i * 30
        a, b = (metric_value(pair[side]["metrics"], key) for side in ("left", "right"))
        label = {"avg_wait": "Stopped vehicle wait (s)", "throughput": "Completed trips", "avg_queue": "Mean lane queue (vehicles)",
                 "max_queue": "Maximum lane queue", "unfinished_vehicles": "Unfinished vehicles", "avg_ped_delay": "Pedestrian wait (s)"}[key]
        d.add(String(0, y, label, fontName="Helvetica", fontSize=9, fillColor=INK))
        maxv = max(a or 0, b or 0, 0.001)
        for j, (value, color) in enumerate(((a, BLUE), (b, GREEN))):
            d.add(Rect(196, y - j * 11 - 1, 185 * (value or 0) / maxv, 7, fillColor=color, strokeColor=None))
            digits = 0 if key in {"throughput", "max_queue", "unfinished_vehicles"} else 2
            d.add(String(388, y - j * 11 - 1, number(value, digits), fontSize=8, fillColor=color))
        delta = None if a is None or b is None else b-a
        label = "--" if delta is None else f"{delta:+.2f}" + (f" ({delta/a*100:+.1f}%)" if a else "")
        d.add(String(445, y - 5, label, fontSize=7.2, fillColor=INK))
    return d


def junction_map(geometry, junction_id):
    d = Drawing(210, 155)
    if not geometry:
        d.add(String(8, 75, "Recorded geometry unavailable", fontSize=9, fillColor=MUTED))
        return d
    node = next((j for j in geometry.get("junctions", []) if j["id"] == junction_id), None)
    if not node:
        d.add(String(8, 75, "Study junction unavailable", fontSize=9, fillColor=MUTED))
        return d
    cx, cy = node["x"], node["y"]
    scale = 1.1
    # Clip each line to the local diagram box. No dependence on current installed network.
    def clip(a, b):
        dx, dy = b[0]-a[0], b[1]-a[1]
        lo, hi = 0.0, 1.0
        for p, q in ((-dx, a[0]-10), (dx, 200-a[0]), (-dy, a[1]-10), (dy, 145-a[1])):
            if p == 0:
                if q < 0: return None
            elif p < 0: lo = max(lo, q/p)
            else: hi = min(hi, q/p)
        if lo > hi: return None
        return (a[0]+lo*dx, a[1]+lo*dy, a[0]+hi*dx, a[1]+hi*dy)
    d.add(Rect(0, 0, 210, 155, fillColor=LIGHT, strokeColor=None))
    for road in geometry.get("roads", []):
        for lane in road.get("lanes", []):
            shape = [(105+(p["x"]-cx)*scale, 78-(p["y"]-cy)*scale) for p in lane.get("shape", [])]
            for a, b in zip(shape, shape[1:]):
                points = clip(a, b)
                if points: d.add(Line(*points, strokeWidth=max(1, lane.get("width", 3)*scale), strokeColor=colors.HexColor("#ADB9BF")))
    d.add(Circle(105, 78, 5, fillColor=GREEN, strokeColor=colors.white))
    d.add(String(10, 140, "Recorded study junction", fontSize=8, fillColor=INK))
    d.add(String(185, 130, "N", fontSize=8, fillColor=INK))
    d.add(Line(188, 111, 188, 126, strokeColor=INK))
    d.add(Line(188, 126, 185, 121, strokeColor=INK))
    return d


def signal_diagram(signals):
    start, end = signals["start"], min(signals["end"], signals["start"]+120)
    span = max(end-start, 0.1)
    d = Drawing(WIDTH, 120)
    for row, side in enumerate(("left", "right")):
        y = 76-row*38
        d.add(String(0, y+13, "Baseline" if side == "left" else "Compared", fontSize=9, fillColor=INK))
        for s in signals[side]["segments"]:
            a, b = max(start, s["start"]), min(end, s["end"])
            if b <= a: continue
            x, width = 74+(a-start)/span*(WIDTH-80), (b-a)/span*(WIDTH-80)
            d.add(Rect(x, y, width, 21, fillColor=phase_color(s), strokeColor=colors.white, strokeWidth=0.3))
            if width > 17 and s["stage"] not in {"red", "yellow", "unknown"}:
                d.add(String(x+3, y+7, phase_label(s["phase"])[0], fontSize=8, fillColor=colors.white))
    for i in range(7):
        x = 74+i/6*(WIDTH-80)
        d.add(String(x-7, 20, f"{start+span*i/6:g}", fontSize=8, fillColor=MUTED))
    d.add(String(74, 4, "Recorded simulation time (s)", fontSize=8, fillColor=MUTED))
    return d


def build_comparison_pdf(pair: dict, signals: dict) -> bytes:
    out = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("BodySmall", fontName="Helvetica", fontSize=9, leading=13, textColor=INK, spaceAfter=7))
    styles.add(ParagraphStyle("Fine", parent=styles["BodySmall"], fontSize=7.5, leading=10, textColor=MUTED))
    styles["Title"].textColor = INK
    styles["Heading2"].textColor = GREEN
    def p(value, style="BodySmall"): return Paragraph(escape(text(value)), styles[style])
    def table(rows, widths=None):
        t = Table([[p(v, "Fine") for v in row] for row in rows], colWidths=widths, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0),LIGHT), ("VALIGN", (0,0),(-1,-1),"TOP"),
                               ("LINEBELOW", (0,0),(-1,-1),0.35,colors.HexColor("#D8E1E5")),
                               ("LEFTPADDING",(0,0),(-1,-1),7), ("RIGHTPADDING",(0,0),(-1,-1),7)]))
        return t
    left, right = pair["left"], pair["right"]
    run = left["option"]["run"]
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    story = [p("SMARTFLOW / COMPARISON BRIEF", "Heading2"), p("Traffic and signal comparison", "Title"),
             p(f"{run.get('scenario_name') or 'Saved scenario'} | Seed {run.get('seed')} | Runs #{run['id']} and #{right['option']['run']['id']}"),
             p(f"Baseline: {controller(left)}  |  Compared: {controller(right)}"),
             p("Scenario-based simulation. Demand and road geometry are not proof of field accuracy. This pair is one traffic realization, not evidence of a general winner.", "Fine")]
    safety = [w for w in pair["warnings"] if "failed a safety check" in w]
    for warning in safety:
        story.append(Paragraph(escape(text(warning)), ParagraphStyle("Safety", parent=styles["BodySmall"], textColor=colors.HexColor("#AD2626"))))
    story += [p("Results at a glance", "Heading2"), p("Blue = baseline; green = compared. Values and changes use the saved run metrics. Each row has its own scale.", "Fine"), bars(pair),
              p("Lower wait or queue is favourable for that metric; more completed trips is favourable. Check unfinished demand, pedestrians and safety together. Wait measures stopped time for admitted vehicles, not traffic-engineering control delay or level of service.", "Fine")]
    duration = metric_value(left["metrics"], "measurement_seconds")
    warmup = metric_value(left["metrics"], "measurement_start")
    map_note = f"Measurement: {number(duration,0)} s. Hidden warm-up: {number(warmup,0)} s.\n\nOnly the selected junction is controlled by the learned model. Surrounding streets keep their recorded control.\n\nThe diagram uses the saved network, not today's installed map. Provisional geometry remains subject to field review."
    story += [Table([[junction_map(pair.get("geometry"), signals["left"]["junction_id"]), p(map_note)]], colWidths=[225, WIDTH-225], style=[("VALIGN", (0,0),(-1,-1),"TOP")]), PageBreak()]
    story += [p("How the signal changed", "Title"),
              p("Fixed-time follows its configured phase timings. RL selects services during the run; it does not necessarily produce a single optimized cycle. These are actual recorded timings, including safety interventions."),
              p(f"First {min(120,signals['end']-signals['start']):g} seconds of shared recording coverage", "Heading2"), signal_diagram(signals),
              p("N = north; E = east; S = south; W = west; P = pedestrian. Yellow = clearance; red = all-red; grey = no signal or missing recording. Directions denote served approaches, not a certification of legal turning movements.", "Fine"),
              p("Green service durations over the full shared window", "Heading2")]
    phases = list(dict.fromkeys(r["phase"] for side in ("left","right") for r in signals[side]["phases"]))
    rows = [["Service", "Baseline mean / range (s)", "Compared mean / range (s)", "Complete greens (B / C)"]]
    for phase in phases:
        readings = [next((r for r in signals[s]["phases"] if r["phase"]==phase), None) for s in ("left","right")]
        def timing(r):
            if not r or r["mean_seconds"] is None: return "No complete green observed"
            return f"{number(r['mean_seconds'])} / {number(r['min_seconds'])}-{number(r['max_seconds'])}"
        rows.append([phase_label(phase), *(timing(r) for r in readings), " / ".join(str(r["complete_count"] if r else 0) for r in readings)])
    if not phases: rows.append(["No recorded green services", "Unavailable", "Unavailable", "0 / 0"])
    story += [table(rows, [92,152,152,WIDTH-396]),
              p("Partial greens at recording boundaries and beside missing frames are excluded from means and ranges. Transition times have the recording's sampling resolution. No observed pedestrian phase does not mean pedestrians have zero delay.", "Fine"),
              p("Recorded controller settings", "Heading2")]
    rows = [["Setting", "Baseline", "Compared"]]
    for label,key in [("Controller", "controller"),("Nominal green setting (s)","green_seconds"),("Yellow clearance (s)","yellow_seconds"),("All-red clearance (s)","all_red_seconds")]:
        rows.append([label, *(str(signals[s]["settings"].get(key, "Unavailable")) for s in ("left","right"))])
    for label,key in [("RL decision interval (s)","decision_interval"),("RL minimum hold (s)","minimum_green_hold")]:
        rows.append([label, *(str(signals[s].get("control",{}).get(key) or "Not applicable") for s in ("left","right"))])
    story += [table(rows,[220,(WIDTH-220)/2,(WIDTH-220)/2]), p("Nominal green settings are not achieved RL green durations. Use the observed table above to interpret the learned model. These timings are a simulation comparison, not a field signal-installation recommendation.", "Fine"), PageBreak()]
    story += [p("Evidence and interpretation", "Title"), p(f"Generated {generated}. Original runs and research evidence were not modified.", "Fine")]
    rows = [["Metric", "Baseline", "Compared"]]
    for key in KEYS + ["avg_travel_time", "requested_vehicles", "total_vehicles_spawned", "pending_demand", "dropped_vehicles", "boundary_wait_seconds", "measurement_start", "measurement_seconds"]:
        definition=METRIC_DEFINITIONS[key]
        rows.append([f"{definition['label']} ({definition['unit']})", *(number(metric_value(pair[s]["metrics"],key),2) for s in ("left","right"))])
    story.append(table(rows,[300,(WIDTH-300)/2,(WIDTH-300)/2]))
    story.append(p("Run provenance", "Heading2"))
    for side,label in (("left","Baseline"),("right","Compared")):
        option = pair[side]["option"]
        prov = option["provenance"]
        story.append(p(f"{label} #{option['run']['id']}: {controller(pair[side])}. Demand: {prov.get('demand_source') or 'unavailable'}. Engine: {prov.get('engine_version') or 'unavailable'}. Missing signal coverage: {signals[side]['unavailable_seconds']:g} s.","Fine"))
        for name in ("network_sha256", "demand_sha256", "model_sha256"):
            if prov.get(name): story.append(p(f"{name}: {prov[name]}","Fine"))
    story.append(p("Limits and checks", "Heading2"))
    for warning in pair["warnings"]: story.append(p(warning,"Fine"))
    def footer(canvas, doc):
        canvas.setStrokeColor(GREEN);canvas.line(38,32,A4[0]-38,32)
        canvas.setFont("Helvetica",8);canvas.setFillColor(MUTED)
        canvas.drawString(38,20,"SmartFlow | Recorded simulation evidence")
        canvas.drawRightString(A4[0]-38,20,f"{doc.page}")
    SimpleDocTemplate(out,pagesize=A4,rightMargin=38,leftMargin=38,topMargin=35,bottomMargin=45,
                      title="SmartFlow traffic and signal comparison",author="SmartFlow").build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
