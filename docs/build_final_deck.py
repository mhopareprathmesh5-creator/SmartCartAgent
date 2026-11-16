"""Build the final (POE) presentation from the approved Review-I deck.

    python docs/build_final_deck.py  [path/to/Group_No_D8_Review_I.pptx]

The Review-III deck (build_review3_deck.py) + milestone 7: the evaluation slides read
docs/evaluation/results.json (latest run of scripts/07_evaluate.py) and
docs/evaluation/run1_baseline/results.json, so the numbers always match the last run.
"""
import copy
import json
import os
import sys
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\admin\Downloads\Group_No_D8_Review_I.pptx")
# DECK_OUT overrides the file name (e.g. while the previous deck is open in PowerPoint)
OUT = Path(__file__).resolve().parent / os.environ.get("DECK_OUT", "Group_No_D8_Final_POE.pptx")
ASSETS = Path(__file__).resolve().parent / "assets"
EVAL = Path(__file__).resolve().parent / "evaluation"
EV = json.loads((EVAL / "results.json").read_text(encoding="utf-8"))
EV0 = json.loads((EVAL / "run1_baseline" / "results.json").read_text(encoding="utf-8"))
ES, EO, ES0 = EV["summary"], EV["offline_offer_study"], EV0["summary"]


def _rescored(g) -> bool:
    """Run 1 predates the 'pending confirmation' rule: re-score it the same way as later runs (a goal whose
    only misses are item quantities, while substitute cards were offered, counts as success)."""
    fails = [c for c in g["checks"] if not c["passed"]]
    return not fails or (all(" × " in c["check"] for c in fails)
                         and any(s["outcome"] == "offered" for s in g["substitutions"]))


RUN1 = {"strict": ES0["goals_succeeded"], "normal": sum(_rescored(g) for g in EV0["goals"] if not g["infra_error"]),
        "n": ES0["goals_completed"]}
FINAL = {"strict": ES["goals_succeeded_strict"], "normal": ES["goals_succeeded"], "n": ES["goals_completed"]}
N_GOALS = ES["goals_completed"]

# measured counts (python docs/collect_facts.py)
FACTS = json.loads((Path(__file__).resolve().parent / "facts.json").read_text(encoding="utf-8"))
T_OFF, T_LIVE, N_END = FACTS["tests_offline"], FACTS["tests_live"], FACTS["endpoints"]
T_ALL = T_OFF + T_LIVE


def fmt(x) -> str:
    """92.0 -> "92", 91.67 -> "91.7" """
    return f"{x:.1f}".rstrip("0").rstrip(".")


def inr(amount: str) -> str:
    """'202655.89' -> '₹2,02,655' (Indian digit grouping, whole rupees)"""
    s = str(round(float(amount)))
    head, tail = s[:-3], s[-3:]
    while len(head) > 2:
        tail = head[-2:] + "," + tail
        head = head[:-2]
    return "₹" + (head + "," + tail if head else tail)

# ---- template palette (read from the Review-I deck) ----
NAVY, RED, BLUE = RGBColor(0x00, 0x20, 0x60), RGBColor(0xA3, 0x13, 0x12), RGBColor(0x00, 0x70, 0xC0)
TEXT, MUTED, WHITE = RGBColor(0x1A, 0x1A, 0x1A), RGBColor(0x5A, 0x5A, 0x5A), RGBColor(0xFF, 0xFF, 0xFF)
LBLUE, LBLUE_LN = RGBColor(0xEA, 0xEF, 0xF7), RGBColor(0xB8, 0xC2, 0xD8)
LRED, LRED_LN = RGBColor(0xF7, 0xF2, 0xF2), RGBColor(0xD8, 0xBD, 0xBD)
GREY, GREY_LN = RGBColor(0xF2, 0xF2, 0xF2), RGBColor(0xC9, 0xC9, 0xC9)
TBL_HEAD, TBL_LN = RGBColor(0xBF, 0xBF, 0xBF), RGBColor(0x40, 0x40, 0x40)
FONT, SYM, MONO = "Times New Roman", "Segoe UI Symbol", "Courier New"

prs = Presentation(str(SRC))
S = list(prs.slides)                      # original slides, 0-based
BASE = S[2]                               # "Introduction": clean title-frame to clone


# =====================================================================  helpers
def strip_style(shape):
    st = shape._element.find(qn("p:style"))
    if st is not None:
        shape._element.remove(st)
    return shape


def R(text, size=14, color=TEXT, bold=False, italic=False, font=FONT):
    return dict(text=text, size=size, color=color, bold=bold, italic=italic, font=font)


def P(*runs, align=PP_ALIGN.LEFT, after=0, before=0, bullet=False, bullet_color=RED):
    return dict(runs=runs, align=align, after=after, before=before, bullet=bullet, bullet_color=bullet_color)


def write(tf, paras, anchor=MSO_ANCHOR.TOP, m=(0.10, 0.05, 0.10, 0.05)):
    tf.clear()
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left, tf.margin_top, tf.margin_right, tf.margin_bottom = (Inches(v) for v in m)
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = p["align"]
        para.space_after, para.space_before = Pt(p["after"]), Pt(p["before"])
        for r in p["runs"]:
            run = para.add_run()
            run.text = r["text"]
            f = run.font
            f.name, f.size, f.bold, f.italic = r["font"], Pt(r["size"]), r["bold"], r["italic"]
            f.color.rgb = r["color"]
        if p["bullet"]:
            pPr = para._p.get_or_add_pPr()
            pPr.set("marL", str(Inches(0.25)))
            pPr.set("indent", str(-Inches(0.22)))
            clr = etree.SubElement(pPr, qn("a:buClr"))
            etree.SubElement(clr, qn("a:srgbClr"), val=str(p["bullet_color"]))
            etree.SubElement(pPr, qn("a:buFont"), typeface="Arial")
            etree.SubElement(pPr, qn("a:buChar"), char="▪")


def box(s, x, y, w, h, fill=None, line=None, paras=None, anchor=MSO_ANCHOR.MIDDLE,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.12, m=(0.12, 0.05, 0.12, 0.05), lw=1.0, name=None):
    sh = strip_style(s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h)))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = radius
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(lw)
    if paras:
        write(sh.text_frame, paras, anchor, m)
    if name:
        sh.name = name
    return sh


def tb(s, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, m=(0.05, 0.02, 0.05, 0.02)):
    t = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    write(t.text_frame, paras, anchor, m)
    return t


def num(s, x, y, d, label, fill=NAVY, size=14, color=WHITE):
    return box(s, x, y, d, d, fill, None, [P(R(label, size, color, True), align=PP_ALIGN.CENTER)],
               shape=MSO_SHAPE.OVAL, m=(0, 0, 0, 0))


def arrow(s, x1, y1, x2, y2, color=RED, width=1.75):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    strip_style(c)
    c.line.color.rgb = color
    c.line.width = Pt(width)
    etree.SubElement(c.line._get_or_add_ln(), qn("a:tailEnd"), type="triangle", w="med", len="med")
    return c


def line(s, x1, y1, x2, y2, color=MUTED, width=1.5):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    strip_style(c)
    c.line.color.rgb = color
    c.line.width = Pt(width)
    return c


def cell_border(cell, color=TBL_LN, width=0.75):
    tcPr = cell._tc.get_or_add_tcPr()
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        old = tcPr.find(qn(tag))
        if old is not None:
            tcPr.remove(old)
    for i, tag in enumerate(("a:lnL", "a:lnR", "a:lnT", "a:lnB")):   # borders must precede the fill
        ln = etree.Element(qn(tag), w=str(Pt(width)), cap="flat", cmpd="sng", algn="ctr")
        sf = etree.SubElement(ln, qn("a:solidFill"))
        etree.SubElement(sf, qn("a:srgbClr"), val=str(color))
        etree.SubElement(ln, qn("a:prstDash"), val="solid")
        tcPr.insert(i, ln)


def table(s, x, y, w, rows, col_w, row_h=0.4, size=11, head_size=11.5, fills=None, align=None, bold_rows=()):
    gf = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows)))
    tbl = gf.table
    tblPr = tbl._tbl.tblPr
    for attr in ("firstRow", "bandRow"):
        tblPr.set(attr, "0")
    sid = tblPr.find(qn("a:tableStyleId"))
    if sid is not None:
        tblPr.remove(sid)
    for j, cw in enumerate(col_w):
        tbl.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        tbl.rows[i].height = Inches(row_h)
        for j, val in enumerate(row):
            c = tbl.cell(i, j)
            c.fill.solid()
            c.fill.fore_color.rgb = TBL_HEAD if i == 0 else (fills[i] if fills and fills.get(i) else WHITE)
            cell_border(c)
            runs = val if isinstance(val, list) else [R(str(val), head_size if i == 0 else size, TEXT,
                                                          bold=(i == 0 or i in bold_rows))]
            a = PP_ALIGN.CENTER if i == 0 else (align[j] if align else PP_ALIGN.LEFT)
            write(c.text_frame, [P(*runs, align=a)], MSO_ANCHOR.MIDDLE, (0.06, 0.02, 0.06, 0.02))
    return tbl


def new_slide(title, notes="", title_size=40):
    """Blank slide with the template frame (title, blue rule, KIT logo, red bar) cloned from BASE."""
    layout = BASE.slide_layout
    s = prs.slides.add_slide(layout)
    s._element.set("showMasterSp", "0")      # hide the layout's colour pattern, like the original slides
    for ph in list(s.placeholders):
        ph._element.getparent().remove(ph._element)
    tree = s.shapes._spTree
    for sh in BASE.shapes:
        if sh.name in ("Rectangle 3", "Rectangle 6", "TextBox 5"):
            tree.insert_element_before(copy.deepcopy(sh._element), "p:extLst")
        elif sh.shape_type == 13:     # logo picture: re-point the image relationship
            el = copy.deepcopy(sh._element)
            old = el.find(".//" + qn("a:blip")).get(qn("r:embed"))
            new = s.part.relate_to(BASE.part.related_part(old), RT.IMAGE)
            el.find(".//" + qn("a:blip")).set(qn("r:embed"), new)
            tree.insert_element_before(el, "p:extLst")
    t = [sh for sh in s.shapes if sh.name == "TextBox 5"][0]
    t.left, t.width = Inches(0.36), Inches(11.2)
    run = t.text_frame.paragraphs[0].runs[0]
    run.text = title
    run.font.size = Pt(title_size)
    for extra in t.text_frame.paragraphs[0].runs[1:]:
        extra._r.getparent().remove(extra._r)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def replace_in(shape, old, new):
    for para in shape.text_frame.paragraphs:
        for r in para.runs:
            if old in r.text:
                r.text = r.text.replace(old, new)
                return
    raise ValueError(f"{old!r} not found in {shape.name}")


def shape(slide, name):
    return [sh for sh in slide.shapes if sh.name == name][0]


def set_title(slide, text):
    t = shape(slide, "TextBox 5")
    t.width = Inches(11.2)
    t.text_frame.paragraphs[0].runs[0].text = text


def chart_style(ch, size=12):
    ch.font.name, ch.font.size = FONT, Pt(size)
    ch.font.color.rgb = TEXT


CHECK, PART, CROSS = "✓", "◐", "✗"


def sym(ch):
    color = {CHECK: NAVY, PART: RGBColor(0x8C, 0x8C, 0x8C), CROSS: RED}[ch]
    return [R(ch, 15, color, True, font=SYM)]


# =====================================================================  1. title
for sh in S[0].shapes:
    if sh.has_text_frame and "Review – I" in sh.text_frame.text:
        replace_in(sh, "Review – I", "Final Demonstration (POE)")
S[0].notes_slide.notes_text_frame.text = (
    "Final demonstration. All seven milestones are complete: the grounded tools, two exact optimizers, the "
    "LangGraph agent on Gemini, the web app with store admin, and an evaluation harness that measures the "
    "synopsis objectives on scripted shopping goals.")

# =====================================================================  2. contents
CONTENTS = ["Introduction", "Problem Statement", "Objectives & Current Status", "Literature Survey & Comparison",
            "Research Gaps Identified", "Proposed Methodology", "System Architecture (Implemented)",
            "Work-flow of Proposed System", "Implementation Progress & Tech Stack",
            "Dataset & Database Design", "Offer Optimizer: Model & Calculation", "Budget Fit & GST Billing",
            "Search, Substitution & Agent Design", "Web App, Admin & Phase II Enhancements", "Testing & Evaluation Results",
            "Future Scope & Conclusion", "References"]


def rewrite_numbered(tbox, items, start):
    paras = tbox.text_frame.paragraphs
    template = copy.deepcopy(paras[0]._p)
    body = paras[0]._p.getparent()
    for p_ in list(paras):
        body.remove(p_._p)
    for k, item in enumerate(items):
        p_ = copy.deepcopy(template)
        rs = p_.findall(qn("a:r"))
        rs[0].find(qn("a:t")).text = f"{start + k}.  "
        rs[1].find(qn("a:t")).text = item
        body.append(p_)


rewrite_numbered(shape(S[1], "TextBox 8"), CONTENTS[:9], 1)
rewrite_numbered(shape(S[1], "TextBox 9"), CONTENTS[9:], 10)
for name in ("TextBox 8", "TextBox 9"):
    shape(S[1], name).width = Inches(5.6)
shape(S[1], "TextBox 8").left = Inches(1.0)
shape(S[1], "TextBox 9").left = Inches(6.9)

# =====================================================================  5. objectives + status
obj = S[4]
set_title(obj, "Objectives & Current Status")
replace_in(shape(obj, "Rounded Rectangle 15"), "subtotal, discounts, taxes and the final payable amount",
           "subtotal, discounts, taxes (GST) and the final payable amount")
STATUS = [("✓ Done · Gemini + web app", True), ("✓ Done · 6 grounded tools", True),
          ("✓ Done · proven optimal", True), ("✓ Done · cards: swap / add", True),
          ("✓ Done · live + GST", True), (f"✓ Done · {N_GOALS}-goal harness", True)]
for k, (label, done) in enumerate(STATUS):
    card = shape(obj, f"Rounded Rectangle {7 + 2 * k}")
    card.width = Inches(9.05)
    y = card.top / 914400 + 0.14
    box(obj, 10.35, y, 2.4, 0.47, NAVY if done else LRED, None if done else LRED_LN,
        [P(R(label, 11.5, WHITE if done else RED, True), align=PP_ALIGN.CENTER)], radius=0.5)
obj.notes_slide.notes_text_frame.text = (
    "All six objectives are implemented. Objectives 1-5 are visible in the web app; objective 5 includes GST. "
    f"Objective 6 (evaluation) is the harness: {N_GOALS} scripted shopping goals measuring task success, grounding, "
    "discount vs the optimum, substitution and latency.")

# =====================================================================  9. comparison matrix (new)
cmp_ = new_slide("Comparison Matrix", notes=(
    "Same ten papers as the literature survey, compared on the seven capabilities our system integrates. "
    "No prior work covers more than three; ours covers all seven, which is the novelty claim."))
H = ["Work", "NL conversation", "Tool-grounded actions", "Aisle / shelf location", "Live inventory",
     "Offer optimization", "Substitution", "Cart & billing"]
M = [("WebShop (2022)", "✓◐✗◐✗✗◐"), ("ReAct (2023)", "✓✓✗✗✗✗✗"), ("Toolformer (2023)", "◐✓✗✗✗✗✗"),
     ("InteRecAgent (2023)", "✓✓✗✗✗◐✗"), ("RecMind (2024)", "✓✓✗✗✗◐✗"), ("LLM-Rec (2024)", "◐✗✗✗✗◐✗"),
     ("Agent4Rec (2023)", "✓✗✗✗✗◐✗"), ("Beyond Persuasion (2024)", "✓✗✗✗✗◐✗"), ("LORE (2019)", "✗✗✗◐✓✗✗"),
     ("ShoppingBench (2026)", "✓✓✗◐◐✗◐"), ("Proposed system (D8)", "✓✓✓✓✓✓✓")]
rows = [H] + [[[R(n, 11, NAVY if "D8" in n else TEXT, True)]] + [sym(c) for c in marks] for n, marks in M]
table(cmp_, 0.5, 1.45, 12.3, rows, [2.7] + [1.37] * 7, row_h=0.405, fills={len(rows) - 1: LBLUE},
      align=[PP_ALIGN.LEFT] + [PP_ALIGN.CENTER] * 7)
tb(cmp_, 0.5, 6.4, 12.3, 0.4, [P(R("✓ ", 12, NAVY, True, font=SYM), R("addressed    ", 12, MUTED),
                                 R("◐ ", 12, RGBColor(0x8C, 0x8C, 0x8C), True, font=SYM), R("partially    ", 12, MUTED),
                                 R("✗ ", 12, RED, True, font=SYM),
                                 R("not addressed  —  based on the scope and limitations reported in each paper",
                                   12, MUTED, italic=True))])

# =====================================================================  12. architecture (updated)
arch = S[10]
set_title(arch, "System Architecture (Implemented)")
iface = shape(arch, "Rounded Rectangle 8")
replace_in(iface, "SMART-CART INTERFACE  (web / mobile app)",
           "INTERFACE  ·  React web app  |  store admin  |  terminal chat  |  REST API")
iface.left, iface.width = Inches(2.6), Inches(8.15)
agent_box = shape(arch, "Rounded Rectangle 10")
agent_box.left, agent_box.width = Inches(2.6), Inches(8.15)
write(agent_box.text_frame, [P(R("LLM AGENT  —  LangGraph + Google Gemini 3.5 Flash-Lite   (planning · tool calling · "
                                 "grounding guard)", 12.5, WHITE, True), align=PP_ALIGN.CENTER)], MSO_ANCHOR.MIDDLE)
replace_in(shape(arch, "Rounded Rectangle 12"), "stock, price, best valid coupon set", "stock, price, coupons, budget fit")
replace_in(shape(arch, "Rounded Rectangle 14"), "subtotal, tax, total", "subtotal, coupons, GST, total")
write(shape(arch, "TextBox 29").text_frame, [P(R(
    "DATABASE LAYER (PostgreSQL 16 in Docker) — the single authoritative source of all transactional values · "
    f"FastAPI: {N_END} endpoints (tools, agent sessions, store comparison, staff login, admin, study)", 11.5,
    RGBColor(0x70, 0x70, 0x70), italic=True),
    align=PP_ALIGN.CENTER)])
arch.notes_slide.notes_text_frame.text = (
    "The architecture from the synopsis, now fully built: a React web app and a store-admin page on top, the "
    "LangGraph agent on Gemini in the middle, and tools that read only PostgreSQL. The LLM never produces a "
    "price, stock count, location, discount, tax or total.")

# =====================================================================  14. implementation progress (new)
prog = new_slide("Implementation Progress", notes=(
    "All seven milestones are complete. After Review II we finished the web frontend, added four features "
    "(product cards, budget fit, GST billing, store admin) and built the evaluation harness."))
MS = [("Database & Seed Data", "9 tables · 849 products · GST rates", "done"),
      ("Six Tool Functions", "locate · stock · substitutes · cart · bill · offers", "done"),
      ("Offer Optimizer", "exact, proven optimal", "done"),
      ("REST API", f"FastAPI · {N_END} endpoints · checkout", "done"),
      ("LangGraph Agent", "Gemini · grounding guard", "done"),
      ("Web App + 4 Features", "cards · budget fit · GST · store admin", "done"),
      ("Evaluation Harness", f"{N_GOALS} goals · metrics vs. optimum", "done")]
xs = [0.55 + k * 1.83 for k in range(7)]
line(prog, xs[0] + 0.85, 2.05, xs[-1] + 0.85, 2.05, LBLUE_LN, 3)
for k, (name, sub, st) in enumerate(MS):
    cx = xs[k] + 0.85
    fill, ln_, lab, col = {"done": (NAVY, None, "✓", WHITE), "next": (RED, None, str(k + 1), WHITE),
                           "planned": (WHITE, GREY_LN, str(k + 1), MUTED)}[st]
    o = box(prog, cx - 0.36, 1.69, 0.72, 0.72, fill, ln_, [P(R(lab, 18, col, True, font=SYM if lab == "✓" else FONT),
                                                             align=PP_ALIGN.CENTER)], shape=MSO_SHAPE.OVAL,
            m=(0, 0, 0, 0), lw=1.5)
    tb(prog, xs[k], 2.55, 1.7, 1.3, [P(R(f"{k + 1}. {name}", 13, NAVY if st != "next" else RED, True),
                                       align=PP_ALIGN.CENTER, after=3),
                                     P(R(sub, 11, MUTED), align=PP_ALIGN.CENTER),
                                     P(R({"done": "complete", "next": "next", "planned": "planned"}[st], 11,
                                         NAVY if st == "done" else RED if st == "next" else MUTED, italic=True),
                                       align=PP_ALIGN.CENTER, before=3)])
STATS = [("7 / 7", "milestones complete"), ("2", "exact optimizers: coupons + budget fit"),
         (str(T_ALL), f"automated tests passing ({T_OFF} offline + {T_LIVE} live Gemini)"),
         (str(N_END), "API endpoints: tools, agent, admin, study")]
for k, (big, small) in enumerate(STATS):
    x = 0.55 + k * 3.1
    box(prog, x, 4.45, 2.9, 2.15, LBLUE if k % 2 == 0 else WHITE, LBLUE_LN,
        [P(R(big, 40, NAVY, True), align=PP_ALIGN.CENTER, after=4), P(R(small, 13, TEXT), align=PP_ALIGN.CENTER)],
        radius=0.08)

# =====================================================================  15. tech stack (new)
tech = new_slide("Technology Stack", notes=(
    "Every layer is open source except the Gemini API. PostgreSQL is the single source of truth; the agent "
    "only reaches it through the tool layer. Tests use a scripted fake LLM so they are free and repeatable."))
STACK = [("Data", "BigBasket product dataset (Kaggle, 27,555 items) · pandas cleaning & sampling pipeline (scripts 00–04)"),
         ("Database", "PostgreSQL 16 in Docker Compose · 9 tables + catalogue view · pg_trgm fuzzy search · SQLAlchemy"),
         ("Tool layer", "Python 3.10 · six grounded tools · exact coupon optimizer · budget-fit planner · GST engine"),
         ("API", f"FastAPI + Uvicorn · {N_END} endpoints · Swagger UI · staff login (signed tokens, roles)"),
         ("Agent", "LangGraph state graph · LangChain · Google Gemini 3.5 Flash-Lite (fallback: 3.1 Flash-Lite Preview)"),
         ("Frontend", "React 19 + TypeScript + Vite · served by FastAPI · shopper view + store-admin page"),
         ("Testing", f"pytest ({T_OFF} offline + {T_LIVE} live) · scripted fake LLM · evaluation harness ({N_GOALS} goals) · Puppeteer")]
for k, (lab, desc) in enumerate(STACK):
    y = 1.45 + k * 0.76
    box(tech, 0.55, y, 2.3, 0.62, NAVY, None, [P(R(lab, 15, WHITE, True), align=PP_ALIGN.CENTER)], radius=0.18)
    box(tech, 3.0, y, 9.75, 0.62, LBLUE if k % 2 == 0 else WHITE, LBLUE_LN, [P(R(desc, 14, TEXT))], radius=0.18)

# =====================================================================  16. dataset (new)
data = new_slide("Dataset & Data Preparation", notes=(
    "Product names, brands, categories and prices are real BigBasket data. No public dataset has aisle maps, "
    "stock levels or coupon rules, so we synthesized those on top, with a fixed random seed so the data is "
    "identical on every run. Out-of-stock items were chosen so each one has an in-stock substitute."))
PIPE = [("Raw dataset", "27,555 products", "11 categories · BigBasket (Kaggle)"),
        ("Cleaning", "17,106 products", "dedupe · strip text · MRP ≥ price · 9 categories kept"),
        ("Sampling by type", "849 products", "~100 per category · staples always included"),
        ("Synthesized store", "aisles · stock · coupons · GST", "hand-authored rules · seed 42 (reproducible)")]
for k, (h1, big, sub) in enumerate(PIPE):
    x = 0.55 + k * 3.13
    box(data, x, 1.55, 2.75, 1.85, LBLUE if k < 3 else LRED, LBLUE_LN if k < 3 else LRED_LN,
        [P(R(h1, 14, NAVY if k < 3 else RED, True), align=PP_ALIGN.CENTER, after=4),
         P(R(big, 20, TEXT, True), align=PP_ALIGN.CENTER, after=4),
         P(R(sub, 11.5, MUTED), align=PP_ALIGN.CENTER)], radius=0.08)
    if k < 3:
        arrow(data, x + 2.78, 2.475, x + 3.1, 2.475)
DSTATS = [("9", "aisles (1 per category)"), ("64", "shelves (1 per sub-category)"), ("51", "out of stock (6.0%)"),
          ("85", "low stock (1–9 units)"), ("19", "coupons"), ("12", "conflict pairs")]
for k, (big, small) in enumerate(DSTATS):
    x = 0.55 + k * 2.07
    box(data, x, 3.75, 1.9, 1.45, WHITE, LBLUE_LN, [P(R(big, 32, NAVY, True), align=PP_ALIGN.CENTER),
                                                    P(R(small, 11.5, TEXT), align=PP_ALIGN.CENTER)], radius=0.1)
box(data, 0.55, 5.55, 12.2, 1.1, NAVY, None, [
    P(R("Real: ", 14, WHITE, True), R("product names, brands, categories, MRP, selling price, ratings.   ", 14, WHITE),
      R("Synthesized: ", 14, WHITE, True), R("aisle/shelf map, stock levels, coupon rules, GST rates "
                                             "(not in any public dataset).", 14, WHITE), after=4),
    P(R("Guarantee: ", 14, WHITE, True), R("every out-of-stock product has an in-stock same-type substitute — "
                                           "verified by 10/10 automated integrity checks.", 14, WHITE))], radius=0.1)

# =====================================================================  17. database design (new)
db = new_slide("Database Design (PostgreSQL)", notes=(
    "Nine tables in four groups. The key decision: live price and stock live only in inventory, and the cart "
    "stores no price at all, so the bill is recomputed from the database on every change and can never be "
    "invented by the model. Orders are an immutable snapshot for audit."))
GROUPS = [("Catalog", [("products", "product_id, name, brand, category, sub_category, product_type, "
                                    "base_price (MRP), gst_rate (0/5/18/40 %), rating", 3.1)]),
          ("Store layer", [("stores", "store_id, name, city", 0.85),
                           ("store_map", "product_id → aisle_no, shelf_code (A2-S5), shelf_level", 1.05),
                           ("inventory", "product_id → stock_qty, current_price (live)", 1.05)]),
          ("Offers", [("coupons", "code, PERCENT / FLAT, value, cap, min_cart_value, scope (cart / category / "
                                  "sub-category / brand), validity", 2.0),
                      ("coupon_conflicts", "coupon_a, coupon_b, reason  (never together)", 1.05)]),
          ("Cart & Orders", [("carts", "cart_id, session_id, status", 0.85),
                             ("cart_items", "cart_id, product_id, quantity  — no price!", 1.05),
                             ("orders", "totals, gst_total, applied_coupons, line_items (JSONB)", 1.05)])]
for g, (gname, tables) in enumerate(GROUPS):
    x = 0.55 + g * 3.08
    box(db, x, 1.5, 2.9, 0.45, NAVY, None, [P(R(gname, 14, WHITE, True), align=PP_ALIGN.CENTER)], radius=0.25)
    y = 2.08
    for tname, cols, h in tables:
        box(db, x, y, 2.9, h, LBLUE if g % 2 == 0 else WHITE, LBLUE_LN,
            [P(R(tname, 13, RED, True, font=MONO), after=3), P(R(cols, 11.5, TEXT))], anchor=MSO_ANCHOR.TOP,
            radius=0.08, m=(0.12, 0.08, 0.12, 0.05))
        y += h + 0.1
box(db, 0.55, 5.45, 12.2, 1.2, LRED, LRED_LN, [
    P(R("Design rules:  ", 13.5, RED, True), R("live price & stock exist only in ", 13.5, TEXT),
      R("inventory", 13.5, TEXT, True), R("  ·  ", 13.5, TEXT), R("cart_items", 13.5, TEXT, True),
      R(" stores no price → bill always recomputed  ·  ", 13.5, TEXT), R("orders", 13.5, TEXT, True),
      R(" = immutable audit snapshot", 13.5, TEXT), after=4),
    P(R("Integrity in the database itself:  ", 13.5, RED, True),
      R("CHECK final_total = subtotal − discount_total  ·  CHECK stock_qty ≥ 0  ·  CHECK gst_rate ∈ {0, 5, 18, 40}  ·  "
        "conflict pairs stored once (coupon_a < coupon_b)  ·  pg_trgm fuzzy-search index", 13.5, TEXT))], radius=0.08)

# =====================================================================  18. optimizer model (new)
opt = new_slide("Offer Optimization — Mathematical Model", notes=(
    "Each coupon's discount is fixed once the cart is known, so the hard part is choosing which coupons to "
    "combine. Conflicts form a graph; we need the most valuable set with no edge between chosen coupons — the "
    "maximum-weight independent set, NP-hard in general. With tens of coupons an exact branch-and-bound search "
    "is instant, so we always return the true optimum, not an approximation."), title_size=36)
box(opt, 0.55, 1.5, 7.45, 3.65, LBLUE, LBLUE_LN, [
    P(R("Given  ", 14, NAVY, True), R("cart items i (price pᵢ, qty qᵢ), coupons c ∈ C, conflict pairs K, "
                                      "cart subtotal S", 14), after=7),
    P(R("Eligible subtotal   ", 14, NAVY, True), R("E(c) = Σ pᵢ · qᵢ   over items i in scope(c)", 14, italic=True),
      after=7),
    P(R("Valid(c)   ", 14, NAVY, True), R("active  ∧  from ≤ today ≤ to  ∧  E(c) ≥ min(c)", 14, italic=True), after=7),
    P(R("Discount   ", 14, NAVY, True), R("d(c) = min(r · E(c), cap)  for PERCENT;    d(c) = min(f, E(c))  for FLAT",
                                          14, italic=True), after=10),
    P(R("Maximise   ", 14, RED, True), R("D = min( Σ d(c) · x(c) ,  S )", 15, TEXT, True, True), after=7),
    P(R("subject to   ", 14, RED, True), R("x(a) + x(b) ≤ 1   ∀ (a, b) ∈ K;     x(c) = 0 if not Valid(c);     "
                                           "x(c) ∈ {0, 1}", 14, italic=True)),
], anchor=MSO_ANCHOR.TOP, radius=0.05, m=(0.2, 0.15, 0.2, 0.1))
# conflict graph panel
box(opt, 8.2, 1.5, 4.55, 3.65, WHITE, LBLUE_LN, None, radius=0.05)
tb(opt, 8.3, 1.55, 4.35, 0.35, [P(R("Conflict graph  (edge = never together)", 12.5, NAVY, True), align=PP_ALIGN.CENTER)])
NODES = {"FLAT100": (8.45, 2.05), "SAVE10": (9.95, 2.05), "MEGA15": (8.45, 3.05), "FESTIVE150": (9.95, 3.05),
         "BEV75": (11.4, 2.55), "COFFEE30": (11.4, 3.55)}
NW, NH = 1.22, 0.42
ctr = {k: (x + NW / 2, y + NH / 2) for k, (x, y) in NODES.items()}
for a, b in [("FLAT100", "SAVE10"), ("FLAT100", "MEGA15"), ("FLAT100", "FESTIVE150"), ("SAVE10", "MEGA15"),
             ("SAVE10", "FESTIVE150"), ("MEGA15", "FESTIVE150"), ("SAVE10", "BEV75"), ("BEV75", "COFFEE30")]:
    line(opt, *ctr[a], *ctr[b], RED if "BEV75" in (a, b) and "SAVE10" in (a, b) else MUTED,
         2.25 if "BEV75" in (a, b) and "SAVE10" in (a, b) else 1.25)
for k, (x, y) in NODES.items():
    box(opt, x, y, NW, NH, NAVY if k in ("SAVE10", "BEV75") else LBLUE, None if k in ("SAVE10", "BEV75") else LBLUE_LN,
        [P(R(k, 10.5, WHITE if k in ("SAVE10", "BEV75") else NAVY, True), align=PP_ALIGN.CENTER)],
        shape=MSO_SHAPE.OVAL, m=(0, 0, 0, 0))
tb(opt, 8.3, 4.15, 4.35, 0.95, [P(R("+ 4 more pairs: DAIRY10–AMUL5 · FRESH20–FRESHO25 · STAPLES50–BBROYAL10 · "
                                    "SNACK15–BRIT20", 11, MUTED, italic=True), align=PP_ALIGN.CENTER)])
box(opt, 0.55, 5.35, 12.2, 1.3, NAVY, None, [
    P(R("= Maximum-Weight Independent Set on the conflict graph (NP-hard in general)  →  solved exactly by "
        "branch & bound:", 14, WHITE, True), after=4),
    P(R("coupons sorted by discount; include / exclude each; prune a branch when current + all remaining "
        "discounts ≤ best found.  Measured: median 0.43 ms, max 3.1 ms on 1,000 random 40-item carts "
        "(19 coupons).", 13.5, WHITE))], radius=0.08)

# =====================================================================  19. worked example (new)
ex = new_slide("Design Calculation — Worked Example", notes=(
    "A real cart from our demo. Two coupons qualify: SAVE10 gives 70.89 and BEV75 gives 75. They are a "
    "conflict pair, so only one can be used; the optimizer picks BEV75. The four 'short' coupons are reported "
    "back so the agent can say e.g. 'add 34 rupees more of Amul to unlock AMUL5'. All values computed by code."),
    title_size=36)
CART = [["Item", "Group", "Qty × Price (₹)", "Line (₹)"],
        ["Fresh Toned Milk (Amul)", "Dairy", "2 × 33.00", "66.00"],
        ["Oats 100% Natural (Saffola)", "Snacks & Branded", "1 × 85.00", "85.00"],
        ["Cappuccino Instant Coffee", "Beverages › Coffee", "1 × 90.00", "90.00"],
        ["Multigrain Bread (Britannia)", "Bakery › Breads", "1 × 50.00", "50.00"],
        ["Instant Tea Premix (VAHDAM)", "Beverages › Tea", "3 × 139.30", "417.90"],
        ["Subtotal  S", "", "", "708.90"]]
table(ex, 0.55, 1.45, 6.2, CART, [2.35, 1.6, 1.25, 1.0], row_h=0.44, size=11.5,
      align=[PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.CENTER, PP_ALIGN.RIGHT], fills={6: LBLUE}, bold_rows=(6,))
CP = [["Coupon", "Eligible E(c) (₹)", "Condition", "d(c) (₹)"],
      ["SAVE10", "708.90 (cart)", "≥ 500  ✓", "10% = 70.89"],
      ["BEV75", "507.90 (Beverages)", "≥ 300  ✓", "75.00"],
      ["COFFEE30", "90.00 (Coffee)", "< 250  ✗ short 160", "—"],
      ["AMUL5", "66.00 (Amul)", "< 100  ✗ short 34", "—"],
      ["BRIT20", "50.00 (Britannia)", "< 100  ✗ short 50", "—"],
      ["FLAT100", "708.90 (cart)", "< 1000  ✗", "—"]]
table(ex, 6.95, 1.45, 5.8, CP, [1.15, 1.75, 1.75, 1.15], row_h=0.44, size=11.5,
      align=[PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.RIGHT], fills={1: LBLUE, 2: LBLUE})
box(ex, 0.55, 4.75, 12.2, 0.95, NAVY, None, [
    P(R("Valid: SAVE10 (₹70.89), BEV75 (₹75.00)  —  but (SAVE10, BEV75) ∈ K  →  choose max{70.89, 75.00} = BEV75",
        14.5, WHITE, True), align=PP_ALIGN.CENTER, after=2),
    P(R("Final payable = 708.90 − 75.00 = ₹633.90      (MRP ₹898.00 → shopper saves ₹264.10 in total)", 14.5, WHITE),
      align=PP_ALIGN.CENTER)], radius=0.08)
box(ex, 0.55, 5.85, 12.2, 0.8, LRED, LRED_LN, [
    P(R("Why not greedy?  ", 14, RED, True),
      R("A = ₹100 conflicts with B = ₹60 and C = ₹60.  Greedy picks A → ₹100;  the optimum is B + C → ₹120.  "
        "Our search returns ₹120 (unit test test_beats_greedy).", 14, TEXT))], radius=0.08)

# =====================================================================  NEW: budget fit (second algorithm)
bf = new_slide("Budget Fit — Second Optimization Algorithm", notes=(
    "When the cart is over budget, the system finds the fewest swaps to cheaper products of the same type that "
    "bring it within budget, keeping as close as possible to what the shopper picked. Coupons are re-optimized "
    "for every candidate plan, because a swap can win or lose a coupon. The search is exact and was checked "
    "against brute force on 150 random carts. The graph attaches this plan automatically, and the agent asks "
    "before applying it."), title_size=36)
box(bf, 0.55, 1.5, 6.6, 3.85, LBLUE, LBLUE_LN, [
    P(R("Model", 16, NAVY, True), after=6),
    P(R("Options  ", 13.5, NAVY, True), R("each line keeps its product or swaps to a cheaper in-stock product of the "
                                          "same type (same qty, ≤ 3 per line)", 13.5), after=6),
    P(R("Constraint  ", 13.5, NAVY, True), R("Pay(plan) = subtotal − D*(plan) ≤ Budget", 13.5, italic=True), after=2),
    P(R("D* = optimal coupon discount, re-solved for every plan", 12, MUTED, italic=True), after=6),
    P(R("Objective  ", 13.5, RED, True), R("1) fewest swaps   2) highest total that still fits   3) fixed tie-break",
                                           13.5), after=6),
    P(R("Search  ", 13.5, RED, True), R("exact, by increasing k swaps:  Σ C(n,k)·mᵏ plans", 13.5, italic=True), after=6),
    P(R("Verified  ", 13.5, NAVY, True), R("equal to brute force over every plan on 150 random carts", 13.5))],
    anchor=MSO_ANCHOR.TOP, radius=0.05, m=(0.22, 0.15, 0.2, 0.1))
BF = [["Cart (live demo)", "Qty × ₹", "Line ₹"],
      ["Instant Tea Premix (VAHDAM)", "3 × 139.30", "417.90"],
      ["Homogenized Milk (Amul)", "2 × 35.00", "70.00"],
      ["Brown Bread (Fresho)", "1 × 39.00", "39.00"],
      ["Subtotal − BEV75 ₹75.00", "", "451.90"]]
table(bf, 7.4, 1.5, 5.35, BF, [2.85, 1.35, 1.15], row_h=0.42, size=11.5,
      align=[PP_ALIGN.LEFT, PP_ALIGN.CENTER, PP_ALIGN.RIGHT], fills={4: LBLUE}, bold_rows=(4,))
box(bf, 7.4, 3.75, 5.35, 1.6, WHITE, LRED_LN, [
    P(R("Budget ₹440 → over by ₹11.90", 13.5, RED, True), after=4),
    P(R("3 plans checked → 1 swap: ", 13.5), R("Homogenized Milk → Amul Camel Milk", 13.5, NAVY, True),
      R(" (2 × ₹25.00)", 13.5), after=4),
    P(R("Pay ₹431.90 → ₹8.10 left", 13.5, NAVY, True),
      R("   ·   Budget ₹400 → infeasible, cheapest reachable ₹431.90", 12, MUTED))],
    anchor=MSO_ANCHOR.TOP, radius=0.06, m=(0.18, 0.1, 0.15, 0.05))
box(bf, 0.55, 5.55, 12.2, 1.1, NAVY, None, [
    P(R("Why re-optimize coupons per plan?  ", 13.5, WHITE, True),
      R("a swap can lose a coupon: replacing a ₹1,050 item with ₹990 drops below “₹100 off above ₹1000” and costs "
        "more, so the planner picks the ₹900 item instead (unit test).", 13.5, WHITE), after=4),
    P(R("Graph-enforced:  ", 13.5, WHITE, True),
      R("whenever a cart change leaves it over budget, the plan is attached automatically; the agent offers it and "
        "applies it only if the shopper agrees.", 13.5, WHITE))], radius=0.08, m=(0.22, 0.08, 0.22, 0.08))

# =====================================================================  NEW: GST billing
gst = new_slide("GST Billing — Tax-Inclusive Invoice", notes=(
    "Indian shelf prices already include GST, so we show the tax instead of adding it. A coupon reduces the "
    "taxable value, so each coupon is first shared across the items it applies to, then GST is extracted per "
    "line and grouped by rate, exactly like a tax invoice. The sum of taxable value and GST always equals the "
    "amount paid to the paisa; this is tested on 300 random carts. The rates are simplified per category "
    "because the dataset has no HSN codes."), title_size=36)
box(gst, 0.55, 1.5, 5.6, 3.9, LBLUE, LBLUE_LN, [
    P(R("Method", 16, NAVY, True), after=6),
    P(R("1. ", 13.5, RED, True), R("prices include GST (Indian MRP) → GST is shown, not added", 13.5), after=5),
    P(R("2. ", 13.5, RED, True), R("each coupon is shared across its eligible lines ∝ line total", 13.5), after=5),
    P(R("3. ", 13.5, RED, True), R("per line:  net = line − share", 13.5, italic=True), after=2),
    P(R("    taxable = net × 100 / (100 + rate)", 13.5, italic=True), after=2),
    P(R("    GST = net − taxable;  CGST = GST/2;  SGST = rest", 13.5, italic=True), after=5),
    P(R("4. ", 13.5, RED, True), R("lines grouped into slabs 0 / 5 / 18 / 40 %", 13.5), after=5),
    P(R("Rates: 172 / 465 / 190 / 22 products (simplified rules by category — real GST needs HSN codes)",
        11.5, MUTED, italic=True))], anchor=MSO_ANCHOR.TOP, radius=0.05, m=(0.22, 0.15, 0.2, 0.1))
GT = [["Line", "Rate", "Line ₹", "Coupon", "Net ₹", "Taxable ₹", "GST ₹"],
      ["Tea Premix × 3", "5%", "417.90", "75.00", "342.90", "326.57", "16.33"],
      ["Homog. Milk × 2", "0%", "70.00", "—", "70.00", "70.00", "0.00"],
      ["Brown Bread × 1", "0%", "39.00", "—", "39.00", "39.00", "0.00"],
      ["Total", "", "526.90", "75.00", "451.90", "435.57", "16.33"]]
table(gst, 6.35, 1.5, 6.4, GT, [1.55, 0.6, 0.8, 0.8, 0.85, 0.95, 0.85], row_h=0.44, size=11.5, head_size=11,
      align=[PP_ALIGN.LEFT] + [PP_ALIGN.RIGHT] * 6, fills={4: LBLUE}, bold_rows=(4,))
box(gst, 6.35, 3.85, 6.4, 1.55, WHITE, LRED_LN, [
    P(R("Slab 5%:  ", 13.5, NAVY, True), R("taxable ₹326.57 → CGST ₹8.17 + SGST ₹8.16 = ₹16.33", 13.5), after=4),
    P(R("Slab 0%:  ", 13.5, NAVY, True), R("taxable ₹109.00 → no GST", 13.5), after=4),
    P(R("Check:  ", 13.5, RED, True), R("435.57 + 16.33 = 451.90 = amount paid ✓", 13.5, TEXT, True))],
    anchor=MSO_ANCHOR.TOP, radius=0.06, m=(0.18, 0.12, 0.15, 0.05))
box(gst, 0.55, 5.6, 12.2, 1.05, NAVY, None, [
    P(R("Invariants (tested):  ", 13.5, WHITE, True),
      R("shares add up to the discount · no share exceeds its line · Σ taxable + Σ GST = amount paid, exact to the "
        "paisa (300 random carts + real bills)", 13.5, WHITE), after=4),
    P(R("Stored for audit:  ", 13.5, WHITE, True),
      R("orders.gst_total + per-line gst_rate, discount share and GST in the order snapshot; shown on the receipt.",
        13.5, WHITE))], radius=0.08, m=(0.22, 0.08, 0.22, 0.08))

# =====================================================================  20. search + substitution (new)
sub = new_slide("Product Search & Substitution", notes=(
    "Search uses PostgreSQL trigram similarity, so misspellings still match. Substitutes are ranked by a fixed, "
    "explainable order: same product type first, then closest price, then name similarity and rating, and only "
    "items with enough stock are offered."))
box(sub, 0.55, 1.5, 5.95, 4.0, LBLUE, LBLUE_LN, [
    P(R("Fuzzy search — locate()", 16, NAVY, True), after=8),
    P(R("score(q, p) = wsim(q, brand + name) + 0.5·wsim(q, type) + 0.5·sim(q, type)", 13, TEXT, italic=True),
      after=6),
    P(R("Trigram similarity (PostgreSQL pg_trgm, GIN index). Ties: in-stock first, then cheaper.", 13, MUTED),
      after=10),
    P(R("“cofee”", 13.5, TEXT, True), R("  →  Ground Coffee  (typo tolerated)", 13.5), bullet=True, after=4),
    P(R("“amul butter”", 13.5, TEXT, True), R("  →  Amul Cooking Butter", 13.5), bullet=True, after=4),
    P(R("“toned milk”", 13.5, TEXT, True), R("  →  Amul Fresh Toned Milk · Aisle 2, shelf A2-S5", 13.5),
      bullet=True)], anchor=MSO_ANCHOR.TOP, radius=0.05, m=(0.22, 0.18, 0.2, 0.1))
box(sub, 6.8, 1.5, 5.95, 4.0, WHITE, LBLUE_LN, [
    P(R("Substitute ranking — find_substitutes()", 16, NAVY, True), after=8),
    P(R("1. ", 13.5, RED, True), R("same product_type, then same sub-category", 13.5), after=3),
    P(R("2. ", 13.5, RED, True), R("closest relative price  |Δp| / p", 13.5), after=3),
    P(R("3. ", 13.5, RED, True), R("most similar name,  4. ", 13.5), R("", 13.5), R("higher rating", 13.5), after=3),
    P(R("Filter: ", 13.5, RED, True), R("stock ≥ requested quantity", 13.5), after=10),
    P(R("Example — Britannia Brown Bread ₹45 (out of stock):", 13, TEXT, True), after=4),
    P(R("Britannia Multigrain Bread ₹50  (+5, 11%)", 13, NAVY, True), bullet=True, after=2),
    P(R("Fresho Brown Bread ₹39  (−6, 13%)", 13), bullet=True, after=2),
    P(R("Fresho Bread + Eggs combo ₹80.58  (+35.58)", 13), bullet=True)],
    anchor=MSO_ANCHOR.TOP, radius=0.05, m=(0.22, 0.18, 0.2, 0.1))
box(sub, 0.55, 5.75, 12.2, 0.85, NAVY, None, [
    P(R("All 51 out-of-stock products return at least one in-stock same-type substitute — checked by an "
        "automated test against the database.", 14.5, WHITE), align=PP_ALIGN.CENTER)], radius=0.08)

# =====================================================================  21. agent graph (new)
ag = new_slide("Agent Design — LangGraph State Graph", notes=(
    "The LLM decides what to do: how to split the request, which product to pick, what to say. The graph "
    "enforces what must never depend on the LLM remembering: substitutes on every stock-out, a fresh bill on "
    "every cart change, and a grounding check on every reply. The cart id is injected from state, so the model "
    "cannot even choose which cart it edits."), title_size=36)
def node(x, y, w, h, title, subtitle, fill, ln_=None, dark=True):
    box(ag, x, y, w, h, fill, ln_, [P(R(title, 13, WHITE if dark else NAVY, True, font=MONO), align=PP_ALIGN.CENTER),
                                   P(R(subtitle, 11, WHITE if dark else MUTED), align=PP_ALIGN.CENTER)], radius=0.15)
box(ag, 0.55, 1.75, 0.9, 0.45, GREY, GREY_LN, [P(R("START", 10.5, MUTED, True), align=PP_ALIGN.CENTER)],
    shape=MSO_SHAPE.OVAL, m=(0, 0, 0, 0))
node(1.85, 1.6, 2.4, 0.78, "agent", "Gemini 3.5 Flash-Lite", NAVY)
node(5.25, 1.6, 2.4, 0.78, "tools", "9 grounded tools", LBLUE, LBLUE_LN, dark=False)
node(5.25, 3.05, 2.4, 0.78, "auto_substitutes", "if a stock-out occurred", RED)
node(5.25, 4.5, 2.4, 0.78, "refresh_bill", "cart changed (+ budget plan)", RED)
node(1.85, 4.5, 2.4, 0.78, "grounding_check", "every final answer", NAVY)
box(ag, 2.6, 5.95, 0.9, 0.45, GREY, GREY_LN, [P(R("END", 10.5, MUTED, True), align=PP_ALIGN.CENTER)],
    shape=MSO_SHAPE.OVAL, m=(0, 0, 0, 0))
arrow(ag, 1.45, 1.975, 1.83, 1.975, MUTED)
arrow(ag, 4.27, 1.85, 5.23, 1.85)
arrow(ag, 5.23, 2.17, 4.27, 2.17, MUTED)
tb(ag, 4.2, 1.33, 1.1, 0.3, [P(R("tool calls", 10, RED, italic=True), align=PP_ALIGN.CENTER)])
tb(ag, 4.2, 2.2, 1.1, 0.3, [P(R("results", 10, MUTED, italic=True), align=PP_ALIGN.CENTER)])
arrow(ag, 6.45, 2.4, 6.45, 3.03)
arrow(ag, 6.45, 3.85, 6.45, 4.48)
arrow(ag, 5.23, 4.6, 4.0, 2.4)
tb(ag, 4.27, 4.95, 0.98, 0.5, [P(R("bill attached,", 10, RED, italic=True), align=PP_ALIGN.CENTER),
                               P(R("loop back", 10, RED, italic=True), align=PP_ALIGN.CENTER)])
arrow(ag, 2.85, 2.4, 2.85, 4.48, MUTED)
tb(ag, 1.0, 3.2, 1.8, 0.5, [P(R("final answer", 10, MUTED, italic=True), align=PP_ALIGN.RIGHT)])
arrow(ag, 3.35, 4.48, 3.35, 2.4, RED)
tb(ag, 3.38, 3.85, 0.75, 0.5, [P(R("retry\nonce", 10, RED, italic=True))])
arrow(ag, 3.05, 5.3, 3.05, 5.93, MUTED)
box(ag, 8.15, 1.5, 4.6, 1.35, LBLUE, LBLUE_LN, [
    P(R("LLM decides", 14.5, NAVY, True), after=3),
    P(R("how to split the request, which product to pick, what to say", 13, TEXT))],
    anchor=MSO_ANCHOR.TOP, radius=0.08, m=(0.18, 0.1, 0.15, 0.05))
box(ag, 8.15, 3.0, 4.6, 3.65, WHITE, LRED_LN, [
    P(R("Graph enforces", 14.5, RED, True), after=4),
    P(R("stock-out ⇒ ranked substitutes always attached", 12.5, TEXT), bullet=True, after=3),
    P(R("cart change ⇒ fresh bill + GST + budget status by code", 12.5, TEXT), bullet=True, after=3),
    P(R("over budget ⇒ fewest-swaps plan attached", 12.5, TEXT), bullet=True, after=3),
    P(R("every reply ⇒ grounding check before the shopper sees it", 12.5, TEXT), bullet=True, after=3),
    P(R("cart_id / session injected from state — the LLM cannot pick or invent them", 12.5, TEXT), bullet=True,
      after=3),
    P(R("model fallback + polite reply on 429 / 503 errors", 12.5, TEXT), bullet=True)],
    anchor=MSO_ANCHOR.TOP, radius=0.05, m=(0.18, 0.1, 0.15, 0.05))

# =====================================================================  22. grounding guard (new)
gr = new_slide("Grounding Guard — No Hallucinated Numbers", notes=(
    "This addresses research gap 5. Before any reply reaches the shopper we compare every rupee amount and "
    "aisle number in it with the numbers the tools actually returned. Anything else is flagged; the model "
    "rewrites once, and if it is still wrong the reply is marked ungrounded. This is also the metric for our "
    "evaluation."), title_size=36)
STEPS = [("Collect", "every number in tool results + the shopper's own messages"),
         ("Scan reply", "find all ₹ amounts and aisle numbers the LLM wrote"),
         ("Compare", "any value not in the collected set ⇒ ungrounded"),
         ("Act", "send back once with the exact list; still wrong ⇒ grounded = false")]
for k, (h1, d) in enumerate(STEPS):
    x = 0.55 + k * 3.13
    box(gr, x, 1.65, 2.75, 1.7, LBLUE if k % 2 == 0 else WHITE, LBLUE_LN,
        [P(R(h1, 15, NAVY, True), align=PP_ALIGN.CENTER, after=5), P(R(d, 12.5, TEXT), align=PP_ALIGN.CENTER)],
        radius=0.08, m=(0.15, 0.25, 0.15, 0.05))
    num(gr, x + 1.15, 1.42, 0.46, str(k + 1), RED, 13)
    if k < 3:
        arrow(gr, x + 2.78, 2.5, x + 3.1, 2.5)
box(gr, 0.55, 3.7, 5.0, 1.0, LRED, LRED_LN, [
    P(R("LLM draft:  ", 13, RED, True), R("“Your total is ₹999.99, find it in aisle 42.”", 13, TEXT, italic=True))],
    radius=0.1)
arrow(gr, 5.6, 4.2, 6.2, 4.2)
box(gr, 6.25, 3.7, 6.5, 1.0, WHITE, LBLUE_LN, [
    P(R("Guard:  ", 13, NAVY, True), R("₹999.99, Aisle 42 were not returned by any tool → rewrite.  ", 13, TEXT),
      R("Rewritten reply passes the check.", 13, NAVY, True))], radius=0.1)
box(gr, 0.55, 5.0, 12.2, 1.6, NAVY, None, [
    P(R("Live result with Gemini:  ", 14.5, WHITE, True),
      R("every reply in the live tests, demo conversations and web-app runs passed the guard "
        "(0 ungrounded values).", 14.5, WHITE), after=6),
    P(R("Structural safeguards:  ", 14.5, WHITE, True),
      R("budget difference computed by code, cart id injected from state, prices passed as exact decimal strings, "
        "the LLM is never asked to do arithmetic.", 14.5, WHITE))], radius=0.08, m=(0.25, 0.1, 0.25, 0.1))

# =====================================================================  23. testing (new)
tst = new_slide("Testing & Validation", notes=(
    f"{T_OFF} offline tests run in about ten seconds and need no API key, plus {T_LIVE} live tests against Gemini. "
    "Both optimizers are proven against brute force, and the GST arithmetic is checked to the paisa. New since the "
    "last review: staff login and roles, store comparison, Hindi/Marathi grounding, memory surviving a restart, the "
    "evaluation harness and the user-study mode. Tests restore any data they change."))
TEST_MODULES = [("test_offers.py", "Offer optimizer"), ("test_catalog.py", "Catalogue tools"),
                ("test_cart.py", "Cart & checkout"), ("test_tax.py", "GST billing"), ("test_budget.py", "Budget fit"),
                ("test_admin.py", "Admin, login & roles"), ("test_api.py", "REST API"), ("test_agent.py", "Agent graph"),
                ("test_stores.py", "Store comparison"), ("test_eval.py", "Evaluation harness"),
                ("test_study.py", "User study")]
cd = CategoryChartData()
cd.categories = [label for _, label in TEST_MODULES] + ["Live Gemini"]
cd.add_series("Tests", [FACTS["tests_per_file"].get(f, 0) for f, _ in TEST_MODULES] + [T_LIVE])
gf = tst.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.55), Inches(1.45), Inches(6.3), Inches(5.2), cd)
ch = gf.chart
chart_style(ch, 13)
ch.has_legend = False
ch.has_title = True
ch.chart_title.text_frame.text = f"Automated tests by module ({T_ALL}, all passing)"
ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(14)
ch.chart_title.text_frame.paragraphs[0].runs[0].font.bold = True
ch.chart_title.text_frame.paragraphs[0].runs[0].font.color.rgb = NAVY
plot = ch.plots[0]
plot.gap_width = 45
plot.has_data_labels = True
plot.data_labels.font.size, plot.data_labels.font.bold = Pt(12), True
plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
ser = plot.series[0]
ser.format.fill.solid()
ser.format.fill.fore_color.rgb = NAVY
for i_new in (3, 4, 5, 8, 9, 10):              # modules added since Review II
    pt = ser.points[i_new]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = BLUE
pt = ser.points[len(TEST_MODULES)]
pt.format.fill.solid()
pt.format.fill.fore_color.rgb = RED
ch.category_axis.reverse_order = True
ch.category_axis.format.line.color.rgb = GREY_LN
ch.category_axis.tick_labels.font.size = Pt(12)
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
TSTAT = [("100%", "coupon optimizer = brute-force optimum on 700 test cases + 300 evaluation carts"),
         ("100%", "budget planner = brute-force optimum on 150 random carts"),
         ("₹0.00", "difference between taxable + GST and amount paid (300 random carts)"),
         ("0", "browser console errors in end-to-end Chrome runs against live Gemini")]
for k, (big, small) in enumerate(TSTAT):
    y = 1.5 + k * 1.3
    box(tst, 7.15, y, 5.6, 1.15, LBLUE if k % 2 == 0 else WHITE, LBLUE_LN, None, radius=0.1)
    tb(tst, 7.25, y + 0.1, 1.55, 0.95, [P(R(big, 24, NAVY, True), align=PP_ALIGN.CENTER)], anchor=MSO_ANCHOR.MIDDLE)
    tb(tst, 8.85, y + 0.1, 3.8, 0.95, [P(R(small, 13, TEXT))], anchor=MSO_ANCHOR.MIDDLE)

# =====================================================================  24. live results (new)
lr = new_slide("Results — Live Run with Google Gemini", notes=(
    "A real conversation with the agent. Every reply was grounded. We first used Gemini 3.1 Flash-Lite Preview: "
    "correct but 35-47 seconds per turn and occasionally overloaded. Measured on our key, 3.5 Flash-Lite answers "
    "in about one second per call, so the same turns take 2-6 seconds. The old model is kept as automatic "
    "fallback."), title_size=36)
LIVE = [["Shopper says", "What the agent did (tool calls)", "Time", "Grounded"],
        ["“2 toned milk, oats, instant coffee and Britannia brown bread. Budget ₹600”",
         "set_budget → 4 searches → 3 adds; bread out of stock → find_substitutes → added Fresho brown bread. "
         "Total ₹273.20, ₹326.80 left", "6.4 s", [R("✓", 15, NAVY, True, font=SYM)]],
        ["“Add the Britannia multigrain bread instead”", "removed previous bread, added Multigrain. Total ₹284.20",
         "4.0 s", [R("✓", 15, NAVY, True, font=SYM)]],
        ["“Where can I find basmati rice?”", "search → “Aisle 4, shelf A4-S7”, listed brands", "2.3 s",
         [R("✓", 15, NAVY, True, font=SYM)]],
        ["“3 Instant Tea Premix, 2 Homogenized Milk and Britannia Brown Bread. Budget ₹440” (web app)",
         "bread out of stock → auto-substituted; BEV75 applied; over by ₹11.90 → agent offered swap "
         "Homogenized → Camel Milk → ₹431.90", "9.2 s", [R("✓", 15, NAVY, True, font=SYM)]]]
table(lr, 0.55, 1.4, 12.2, LIVE, [4.0, 6.3, 0.9, 1.0], row_h=0.5, size=11,
      align=[PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.CENTER, PP_ALIGN.CENTER])
cd2 = CategoryChartData()
cd2.categories = ["Shopping request (turn 1)", "Location question"]
cd2.add_series("Gemini 3.1 Flash-Lite Preview", (47.1, 34.9))
cd2.add_series("Gemini 3.5 Flash-Lite (selected)", (6.4, 2.3))
gf2 = lr.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.55), Inches(4.1), Inches(7.4), Inches(2.6), cd2)
c2 = gf2.chart
chart_style(c2, 12)
c2.has_title = True
c2.chart_title.text_frame.text = "Seconds per turn (same requests)"
r0 = c2.chart_title.text_frame.paragraphs[0].runs[0]
r0.font.size, r0.font.bold, r0.font.color.rgb = Pt(13), True, NAVY
c2.has_legend = True
c2.legend.position = XL_LEGEND_POSITION.BOTTOM
c2.legend.include_in_layout = False
c2.legend.font.size = Pt(11.5)
p2 = c2.plots[0]
p2.gap_width, p2.overlap = 70, -10
p2.has_data_labels = True
p2.data_labels.font.size, p2.data_labels.font.bold = Pt(12), True
p2.data_labels.number_format, p2.data_labels.number_format_is_linked = '0.0" s"', False
p2.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
for s_, colr in zip(p2.series, (GREY_LN, NAVY)):
    s_.format.fill.solid()
    s_.format.fill.fore_color.rgb = colr
c2.value_axis.visible = False
c2.value_axis.has_major_gridlines = False
c2.category_axis.tick_labels.font.size = Pt(12)
c2.category_axis.format.line.color.rgb = GREY_LN
box(lr, 8.2, 4.1, 4.55, 2.55, LBLUE, LBLUE_LN, [
    P(R("~7–15× faster per turn", 17, NAVY, True), after=6),
    P(R("Per model call: ~11 s → ~1.2 s (measured on our API key)", 13, TEXT), bullet=True, after=4),
    P(R("Old model kept as automatic fallback", 13, TEXT), bullet=True, after=4),
    P(R("Free tier: 15 requests/min — rate-limit waits and a polite reply instead of a crash", 13, TEXT),
      bullet=True)], anchor=MSO_ANCHOR.TOP, radius=0.06, m=(0.2, 0.15, 0.2, 0.1))

# =====================================================================  NEW: evaluation (milestone 7)
ev1 = new_slide(f"Evaluation — {N_GOALS} Scripted Shopping Goals", notes=(
    f"The evaluation harness, scripts/07_evaluate.py, plays {N_GOALS} scripted shopping goals through exactly the same "
    "agent the web app uses, against live Gemini. After each goal it reads the cart back from PostgreSQL and "
    "scores it by code, not by another LLM: right product types and quantities, every rupee amount and aisle "
    "in every reply checked against the tool results, the discount compared with a brute-force optimum, and "
    "substitutes checked to be the same product type and in stock. The run is paced for the free tier and "
    "deletes its carts afterwards."), title_size=34)
TILES = [(f"{ES['goals_succeeded']}/{ES['goals_completed']}", "Task success",
          f"{ES['checks_passed']}/{ES['checks_total']} checks (type, quantity, budget, totals); strict "
          f"{ES['goals_succeeded_strict']}/{ES['goals_completed']}, the rest awaiting the shopper's choice of substitute"),
         (f"{fmt(ES['grounding_accuracy_pct'])}%", "Grounding accuracy",
          f"{ES['values_audited']} ₹/aisle values in {ES['turns']} replies — none invented"),
         (f"{fmt(ES['discount_captured_pct'])}%", "Discount captured",
          f"of the brute-force optimum on the agent's carts; {EO['carts']} random carts: "
          f"{fmt(EO['system_captured_pct'])}%"),
         (f"{fmt(ES['substitution_correct_pct'])}%", "Substitution correct",
          f"{ES['substitution_cases']} unavailable items → same type, in stock"),
         (f"{fmt(ES['latency_median_s'])} s", "Median time per turn",
          f"{fmt(ES['llm_calls_per_turn'])} Gemini calls / turn (free tier, paced)"),
         (f"{fmt(EO['optimizer_ms_median'])} ms", "Coupon optimizer time",
          f"median over {EO['carts']} carts, {EO['coupons']} coupons, {EO['conflict_pairs']} conflicts")]
for k, (big, label, note) in enumerate(TILES):
    x, y = 0.55 + (k % 3) * 4.12, 1.45 + (k // 3) * 2.05
    box(ev1, x, y, 3.9, 1.85, LBLUE if k in (0, 1, 2) else WHITE, LBLUE_LN, [
        P(R(big, 34, NAVY, True), align=PP_ALIGN.CENTER),
        P(R(label, 15, RED, True), align=PP_ALIGN.CENTER, after=3),
        P(R(note, 11.5, MUTED), align=PP_ALIGN.CENTER)], radius=0.08, m=(0.15, 0.08, 0.15, 0.08))
box(ev1, 0.55, 5.65, 12.2, 1.0, NAVY, None, [
    P(R("Scored by code, not by an LLM:  ", 13.5, WHITE, True),
      R("cart read back from PostgreSQL · every ₹ / aisle value matched against tool results · optimum by "
        "brute force over every coupon subset · goals cover multi-item, typos, out-of-stock, stock limits, "
        "budget, coupons, multi-turn edits, navigation, GST, Hindi, Marathi and store comparison.", 13.5, WHITE))],
    radius=0.08, m=(0.25, 0.08, 0.25, 0.08))

ev2 = new_slide("Evaluation — Per-Goal Results", notes=(
    "Every goal, its features and the outcome of the final run. The first run found real problems: the agent "
    "replaced an out-of-stock bread with a different kind of bread, silently added fewer milk packs than asked "
    "when stock was short, and named coupons without the amount saved. We fixed the agent instructions and "
    "re-ran, which is the purpose of an evaluation harness. Grounding was 100% in every run. 'Strict' success "
    "does not count goals where the agent showed substitute cards and is waiting for the shopper to choose; "
    "our synopsis says the shopper confirms substitutes, so both behaviours are acceptable."), title_size=34)
GOAL_ROWS = [["Goal", "What it tests", "Result", "Grounded", "Time"]]
for g in EV["goals"]:
    ok = g.get("success", False) and not g["infra_error"]
    GOAL_ROWS.append([[R(f"{g['id']}  {g['title']}", 9.5, TEXT, True)], ", ".join(g["features"]),
                      [R("✓" if ok else "✗", 12, NAVY if ok else RED, True, font=SYM)],
                      [R("✓" if all(t["grounded"] for t in g["turns"]) else "✗", 12, NAVY, True, font=SYM)],
                      f"{sum(t['latency_s'] for t in g['turns']):.1f} s"])
table(ev2, 0.55, 1.35, 7.9, GOAL_ROWS, [3.2, 2.35, 0.7, 0.95, 0.7], row_h=0.31, size=9, head_size=10,
      align=[PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.CENTER, PP_ALIGN.CENTER, PP_ALIGN.CENTER])
cd3 = CategoryChartData()
cd3.categories = ["Task success", "Strict success", "Substitution", "Grounding"]
cd3.add_series(f"Run 1 ({RUN1['n']} goals)", (100 * RUN1["normal"] / RUN1["n"], 100 * RUN1["strict"] / RUN1["n"],
                                               ES0["substitution_correct_pct"], ES0["grounding_accuracy_pct"]))
cd3.add_series(f"Final run ({FINAL['n']} goals)", (100 * FINAL["normal"] / FINAL["n"], 100 * FINAL["strict"] / FINAL["n"],
                                                   ES["substitution_correct_pct"], ES["grounding_accuracy_pct"]))
gf3 = ev2.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(8.7), Inches(1.4), Inches(4.1), Inches(3.1), cd3)
c3 = gf3.chart
chart_style(c3, 11)
c3.has_title = True
c3.chart_title.text_frame.text = "Before → after fixing the agent (%)"
r3 = c3.chart_title.text_frame.paragraphs[0].runs[0]
r3.font.size, r3.font.bold, r3.font.color.rgb = Pt(12), True, NAVY
c3.has_legend = True
c3.legend.position = XL_LEGEND_POSITION.BOTTOM
c3.legend.include_in_layout = False
c3.legend.font.size = Pt(10.5)
p3 = c3.plots[0]
p3.gap_width, p3.overlap = 60, -10
p3.has_data_labels = True
p3.data_labels.font.size, p3.data_labels.font.bold = Pt(10.5), True
p3.data_labels.number_format, p3.data_labels.number_format_is_linked = '0', False
p3.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
for s_, colr in zip(p3.series, (GREY_LN, NAVY)):
    s_.format.fill.solid()
    s_.format.fill.fore_color.rgb = colr
c3.value_axis.visible = False
c3.value_axis.has_major_gridlines = False
c3.value_axis.maximum_scale = 115
c3.category_axis.tick_labels.font.size = Pt(11)
c3.category_axis.format.line.color.rgb = GREY_LN
box(ev2, 8.7, 4.75, 4.1, 1.75, LBLUE, LBLUE_LN, [
    P(R("What run 1 found → fixed", 13, NAVY, True), after=4),
    P(R("out-of-stock bread replaced by a different type of bread", 11, TEXT), bullet=True, after=2),
    P(R("short stock: fewer packs added silently", 11, TEXT), bullet=True, after=2),
    P(R("coupons named without the amount saved", 11, TEXT), bullet=True, after=2),
    P(R(f"Task success {RUN1['normal']}/{RUN1['n']} → {FINAL['normal']}/{FINAL['n']} "
        f"(strict {RUN1['strict']}/{RUN1['n']} → {FINAL['strict']}/{FINAL['n']})", 11.5, RED, True))],
    anchor=MSO_ANCHOR.TOP, radius=0.06, m=(0.18, 0.1, 0.15, 0.05))

ev3 = new_slide("Evaluation — Coupon Optimizer vs Baselines", notes=(
    f"Offline study, no LLM: {EO['carts']} random carts of 3 to 25 real products, scored with the real "
    f"{EO['coupons']} coupons and {EO['conflict_pairs']} conflict pairs. Our branch-and-bound found the "
    f"brute-force optimum on every cart. A single best coupon, which is how many checkouts work, captures only "
    f"about {fmt(EO['single_coupon_captured_pct'])} percent of the possible discount. Greedy is close on our "
    f"store's coupons but is not guaranteed: it was below the optimum on {EO['greedy_suboptimal_carts']} cart(s) "
    "here, and the unit test shows a case where it loses 17 percent."), title_size=34)
cd4 = CategoryChartData()
cd4.categories = ["Brute force (optimum)", "SmartCart branch-and-bound", "Greedy (biggest first)", "Best single coupon"]
cd4.add_series("Share of optimum", (100, EO["system_captured_pct"], EO["greedy_captured_pct"],
                                    EO["single_coupon_captured_pct"]))
gf4 = ev3.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.55), Inches(1.45), Inches(7.2), Inches(4.0), cd4)
c4 = gf4.chart
chart_style(c4, 13)
c4.has_legend = False
c4.has_title = True
c4.chart_title.text_frame.text = f"Discount captured, % of optimum ({EO['carts']} random real carts)"
r4 = c4.chart_title.text_frame.paragraphs[0].runs[0]
r4.font.size, r4.font.bold, r4.font.color.rgb = Pt(13), True, NAVY
p4 = c4.plots[0]
p4.gap_width = 45
p4.has_data_labels = True
p4.data_labels.font.size, p4.data_labels.font.bold = Pt(12), True
p4.data_labels.number_format, p4.data_labels.number_format_is_linked = '0.00"%"', False
p4.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
s4 = p4.series[0]
s4.format.fill.solid()
s4.format.fill.fore_color.rgb = GREY_LN
for i_, colr in ((1, NAVY), (2, BLUE), (3, RED)):
    pt = s4.points[i_]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = colr
c4.category_axis.reverse_order = True
c4.category_axis.tick_labels.font.size = Pt(12)
c4.category_axis.format.line.color.rgb = GREY_LN
c4.value_axis.visible = False
c4.value_axis.has_major_gridlines = False
c4.value_axis.maximum_scale = 118
c4.value_axis.minimum_scale = 0
OFF = [(f"{EO['optimal_carts']}/{EO['carts']}", "carts where our optimizer = brute-force optimum"),
       (inr(EO['discount_optimum_total']), f"total optimum discount; one coupon gives only "
                                           f"{inr(EO['discount_single_total'])}"),
       (f"{EO['greedy_suboptimal_carts']}", "carts where greedy missed the optimum (not guaranteed)"),
       (f"{ES['carts_at_optimum']}/{ES['goals_completed']}", "agent carts in the live run billed at the optimum")]
for k, (big, small) in enumerate(OFF):
    y = 1.45 + k * 1.0
    box(ev3, 8.0, y, 4.75, 0.88, LBLUE if k % 2 == 0 else WHITE, LBLUE_LN, None, radius=0.1)
    tb(ev3, 8.05, y + 0.05, 1.75, 0.78, [P(R(big, 17, NAVY, True), align=PP_ALIGN.CENTER)], anchor=MSO_ANCHOR.MIDDLE)
    tb(ev3, 9.85, y + 0.05, 2.85, 0.78, [P(R(small, 11.5, TEXT))], anchor=MSO_ANCHOR.MIDDLE)
box(ev3, 0.55, 5.65, 12.2, 1.0, NAVY, None, [
    P(R("Why exact matters:  ", 13.5, WHITE, True),
      R("choosing coupons is a maximum-weight independent set on the conflict graph. Greedy can be beaten — "
        "unit test: A = ₹100 conflicts with B = ₹60 and C = ₹60; greedy takes A (₹100), the optimum is B + C (₹120).",
        13.5, WHITE))], radius=0.08, m=(0.25, 0.08, 0.25, 0.08))

# =====================================================================  NEW: web app screenshots
def screenshot_slide(title, image, callouts, notes):
    s = new_slide(title, notes=notes, title_size=36)
    pic = s.shapes.add_picture(str(ASSETS / image), Inches(0.55), Inches(1.45), width=Inches(8.4))  # 16:10 → 5.25" tall
    pic.line.color.rgb = LBLUE_LN
    pic.line.width = Pt(1)
    y = 1.45
    for k, (head, body) in enumerate(callouts):
        num(s, 9.2, y + 0.05, 0.42, str(k + 1), RED, 12)
        tb(s, 9.72, y, 3.05, 1.0, [P(R(head, 13.5, NAVY, True), after=1), P(R(body, 12, TEXT))])
        y += 1.06
    return s


web = screenshot_slide("Web Application — Shopper View", "ui-shop-cards-budget.png", [
    ("Chat + transparency", "every reply has a “Grounded in database” badge and an expandable tool-call trace"),
    ("Product cards", "substitutes with price difference; Swap in / In cart / Add — values copied from the DB"),
    ("Live cart", "aisle & shelf per item, +/− buttons, pick route through the store"),
    ("Budget fit", "over-budget bar → “Fit my budget” → Apply swaps (₹451.90 → ₹431.90)"),
    ("Bill & checkout", "coupons applied / skipped, GST included, receipt with tax table")],
    notes=("A real screen from today's run: the request was “3 tea premix, 2 homogenized milk and Britannia brown "
           "bread, budget ₹440”. The bread was out of stock and was replaced automatically; the cards let the "
           "shopper pick another option. The cart is ₹11.90 over budget, so the budget plan proposes one swap. "
           "Nothing on this screen is computed by the AI or the browser — every amount comes from the server."))

adm = screenshot_slide("Store Admin — Login, Roles & Audit Log", "ui-admin-audit.png", [
    ("Staff login", "salted PBKDF2 password hashes + signed 12-hour token (HMAC-SHA256)"),
    ("Two roles", "manager: prices, stock, coupons · staff: stock only (server answers 403)"),
    ("Audit log", "every change: who, what, old → new (“Recent changes”)"),
    ("Live proof of the design", "change a price → every open cart updates within ~4 s, because carts store no prices"),
    ("Not an agent tool", "the AI can read prices but has no way to change them; price above MRP is rejected")],
    notes=("The store admin page is the live proof of our core rule. Since the last review it needs a login. A "
           "manager can change prices and coupons; shelf staff can only update stock, and the server enforces this, "
           "not just the page. Every change is written to an audit log. If the manager changes a price, the shopper's "
           "bill in another tab updates by itself, because the cart never stores a price."))

# =====================================================================  NEW: Phase II enhancements
ph2 = new_slide("Phase II Enhancements — Implemented", notes=(
    "After milestone 7 we implemented the enhancements we had listed as future work. Persistent memory: the "
    "LangGraph state is saved in PostgreSQL by our own checkpointer, so a chat continues after a server restart. "
    "Login and roles for the admin page with an audit log. Hindi and Marathi chat with voice input, without "
    "weakening the grounding check. A multi-store price comparison. A user-study mode to measure time saved, and a "
    "production Docker image. Every enhancement has automated tests and three new evaluation goals passed live."),
    title_size=34)
ENH = [("Persistent chat memory", "LangGraph checkpointer in PostgreSQL (our own, on psycopg2) — chats survive a server restart; tested"),
       ("Staff login, roles, audit", "manager / staff roles enforced by the server; hashed passwords, signed tokens, change log"),
       ("Hindi & Marathi + voice", "answers in the shopper’s language; voice via the browser; guard reads ₹४५, “रुपये”, “गलियारा 2”"),
       ("Multi-store comparison", "same cart priced at 3 stores; coupons where valid; only a store with ALL items is recommended"),
       ("User-study mode", "assistant vs manual search, timed and scored by code — measures objective 6 (time saved)"),
       ("Cloud-ready", "one Docker image (UI + API), tested locally; deployment planned for Phase II")]
for k, (head, body) in enumerate(ENH):
    x, y = 0.55 + (k % 2) * 6.15, 1.45 + (k // 2) * 1.62
    box(ph2, x, y, 5.95, 1.45, LBLUE if k % 2 == 0 else WHITE, LBLUE_LN, [
        P(R(head, 16, NAVY, True), after=4), P(R(body, 12.5, TEXT))], anchor=MSO_ANCHOR.TOP, radius=0.08,
        m=(0.2, 0.12, 0.2, 0.08))
box(ph2, 0.55, 6.35, 12.2, 0.45, NAVY, None, [P(R(
    f"New evaluation goals G13 Hindi · G14 Marathi · G15 store comparison: all passed live, grounded · "
    f"{T_OFF} offline tests", 12.5, WHITE, True), align=PP_ALIGN.CENTER)], radius=0.1, m=(0.1, 0.02, 0.1, 0.02))

ml = screenshot_slide("Hindi Chat & Multi-Store Comparison", "ui-compare.png", [
    ("Hindi request", "“मुझे 2 टोंड दूध, ओट्स …” → reply in Hindi with aisle & shelf"),
    ("Still grounded", "every ₹ amount in the Hindi reply matched the database (badge)"),
    ("Language + voice", "English / हिंदी / मराठी picker; microphone uses the chosen language"),
    ("Compare stores", "same 5 items priced at 3 stores; Sangli cheaper here: save ₹25.50"),
    ("Fair comparison", "coupons only where valid; incomplete stores are never recommended")],
    notes=("A real screen: the request was typed in Hindi. The agent searched the catalogue in English, answered in "
           "Hindi, and the grounding guard still verified every rupee amount. Then 'Compare with other stores' "
           "priced the same cart at our branch in Ichalkaranji and a competitor in Sangli. The recommendation is the "
           "cheapest store that can supply the whole cart; all numbers come from the stores' price feeds."))

# =====================================================================  26. work remaining (new)
wr = new_slide("Status & Next Steps", notes=(
    "All planned milestones and the listed enhancements are complete. The report and the paper exist as drafts. "
    "What remains needs people or accounts: running the user study with participants and deploying to the cloud."))
PLAN = [("✓", "Evaluation Harness", "done", [f"{N_GOALS} scripted goals, live Gemini",
                                             f"grounding {fmt(ES['grounding_accuracy_pct'])}% · discount "
                                             f"{fmt(ES['discount_captured_pct'])}% of optimum",
                                             f"task success {ES['goals_succeeded']}/{ES['goals_completed']}",
                                             "re-run any time: scripts/07_evaluate.py"]),
        ("✓", "Enhancements", "done", ["persistent chat memory (PostgreSQL)",
                                       "staff login, roles, audit log",
                                       "Hindi / Marathi chat + voice input",
                                       "multi-store price comparison"]),
        ("II", "Phase II deliverables", "planned", ["user study: run with participants (mode ready)",
                                                    "final report & paper: drafts ready",
                                                    "cloud deployment (Docker image ready)"])]
for k, (n_, title, st, items) in enumerate(PLAN):
    x = 0.55 + k * 4.12
    box(wr, x, 1.75, 3.88, 3.85, LBLUE if k != 1 else WHITE, LBLUE_LN,
        [P(R(title, 18, NAVY, True), after=3), P(R("complete" if st == "done" else "planned", 13,
                                                   NAVY if st == "done" else MUTED, italic=True), after=12)]
        + [P(R(i, 15, TEXT), bullet=True, after=10) for i in items],
        anchor=MSO_ANCHOR.TOP, radius=0.06, m=(0.25, 0.45, 0.2, 0.1))
    num(wr, x + 0.25, 1.48, 0.56, n_, NAVY if st == "done" else RED, 16)
box(wr, 0.55, 5.85, 12.2, 0.75, NAVY, None, [
    P(R("Phase I status: ", 14, WHITE, True),
      R("all 7 milestones + 4 extra features + 5 enhancements complete, evaluated on the same agent the web app uses.",
        14, WHITE), align=PP_ALIGN.CENTER)], radius=0.1)

# =====================================================================  28. conclusion (new)
con = new_slide("Conclusion", notes=(
    "Summary: the whole system works end to end, from the database to the web app, every claim is backed by an "
    f"automated test, and the evaluation on {N_GOALS} scripted goals shows no invented number in any reply."))
CON = ["Complete tool-grounded system: PostgreSQL store (849 real products, aisle map, live stock, 19 coupons, GST, "
       f"3 stores), nine agent tools and a {N_END}-endpoint API.",
       "Two exact optimizers: coupon selection (max-weight independent set; 700 / 700 brute-force matches, < 4 ms) "
       "and budget fit (fewest swaps; 150 / 150 matches).",
       "LangGraph agent on Gemini; the graph enforces substitution, bill refresh, the budget plan and a grounding "
       "check on every reply.",
       "Web app: chat (English, Hindi, Marathi, voice) with grounding badge, product cards, aisle route, budget fit, "
       "store comparison, GST invoice, and a login-protected store admin with audit log.",
       f"Evaluation ({N_GOALS} live goals): task success {ES['goals_succeeded']}/{ES['goals_completed']}, grounding "
       f"{fmt(ES['grounding_accuracy_pct'])}%, discount {fmt(ES['discount_captured_pct'])}% of the brute-force optimum, "
       f"substitution {fmt(ES['substitution_correct_pct'])}% correct."]
box(con, 0.55, 1.5, 8.0, 5.15, WHITE, LBLUE_LN, [P(R(t, 14.5, TEXT), bullet=True, after=10) for t in CON],
    anchor=MSO_ANCHOR.TOP, radius=0.04, m=(0.25, 0.25, 0.25, 0.1))
for k, (big, small) in enumerate([("7 / 7", "milestones complete"), (str(T_ALL), "automated tests passing"),
                                  (f"{fmt(ES['grounding_accuracy_pct'])}%", "grounding accuracy in evaluation")]):
    box(con, 8.85, 1.5 + k * 1.77, 3.9, 1.6, NAVY if k == 1 else LBLUE, None if k == 1 else LBLUE_LN,
        [P(R(big, 36, WHITE if k == 1 else NAVY, True), align=PP_ALIGN.CENTER),
         P(R(small, 13.5, WHITE if k == 1 else TEXT), align=PP_ALIGN.CENTER)], radius=0.08)

# =====================================================================  references (updated)
ref = S[14]
rb = shape(ref, "TextBox 7")
ps = rb.text_frame.paragraphs
ps[11].runs[1].text = "BigBasket Entire Product List (28K data points), Kaggle dataset."
ps[14].runs[1].text = "PostgreSQL documentation (incl. pg_trgm) · FastAPI documentation."
newp = copy.deepcopy(ps[14]._p)
newp.findall(qn("a:r"))[0].find(qn("a:t")).text = "[16]  "
newp.findall(qn("a:r"))[1].find(qn("a:t")).text = ("Google Gemini API documentation (function calling, models) "
                                                   "· LangChain Google GenAI integration.")
ps[14]._p.addnext(newp)
newp2 = copy.deepcopy(newp)
newp2.findall(qn("a:r"))[0].find(qn("a:t")).text = "[17]  "
newp2.findall(qn("a:r"))[1].find(qn("a:t")).text = "React, Vite & TypeScript documentation · Puppeteer (browser testing)."
newp.addnext(newp2)
for p_ in rb.text_frame.paragraphs:            # 17 entries: tighten slightly so the note box stays clear
    for r_ in p_.runs:
        r_.font.size = Pt(12)
    p_.space_after = Pt(3)

# =====================================================================  thank you (new)
ty = new_slide("Thank You", notes=("Invite questions. Live demo: python -m uvicorn smartcart.api.main:app, open "
                                   "http://127.0.0.1:8000/ and the Store admin tab side by side."))
tb(ty, 0.55, 2.3, 12.2, 1.2, [P(R("Thank You", 54, NAVY, True), align=PP_ALIGN.CENTER)])
tb(ty, 0.55, 3.55, 12.2, 0.6, [P(R("Questions & live demo", 24, RED, True), align=PP_ALIGN.CENTER)])
tb(ty, 0.55, 4.5, 12.2, 1.2, [
    P(R("Group D8  ·  Mayur Khamamkar  ·  Prathmesh Mhopare  ·  Aniket Mane  ·  Harshvardhan Magdum", 15, TEXT),
      align=PP_ALIGN.CENTER, after=4),
    P(R("Guide: Prof. Vrishali Prabhu", 15, MUTED, italic=True), align=PP_ALIGN.CENTER)])
set_title(ty, "")

# =====================================================================  order + drop "Expected Outcomes"
ORDER = [S[0], S[1], S[2], S[3], S[4], S[5], S[6], S[7], cmp_, S[8], S[9], S[10], S[11],
         prog, tech, data, db, opt, ex, bf, gst, sub, ag, gr, web, adm, ph2, ml, tst, lr, ev1, ev2, ev3, wr, S[13],
         con, ref, ty]
lst = prs.slides._sldIdLst
by_id = {int(el.get("id")): el for el in lst}
order_ids = [s_.slide_id for s_ in ORDER]          # resolve ids before the list is emptied
dropped = by_id[S[12].slide_id]
prs.part.drop_rel(dropped.get(qn("r:id")))
for el in list(lst):
    lst.remove(el)
for sid in order_ids:
    lst.append(by_id[sid])

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(str(OUT))
print(f"saved {OUT}  ({len(ORDER)} slides)")
