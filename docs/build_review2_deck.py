"""Build the Review-II presentation from the approved Review-I deck.

    python docs/build_review2_deck.py  [path/to/Group_No_D8_Review_I.pptx]

Keeps the college template + Phase-I content (literature survey, gaps, methodology),
updates slides to what is actually implemented, and adds the progress slides.
Every number on the new slides was measured from the running system (2026-10-12).
"""
import copy
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
OUT = Path(__file__).resolve().parent / "Group_No_D8_Review_II.pptx"

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
        replace_in(sh, "Review – I", "Review – II")
S[0].notes_slide.notes_text_frame.text = (
    "Review II: progress since the approved synopsis. We have implemented the database, the six grounded "
    "tools, the exact offer optimizer, the REST API and the LangGraph agent running on Google Gemini.")

# =====================================================================  2. contents
CONTENTS = ["Introduction", "Problem Statement", "Objectives & Current Status", "Literature Survey & Comparison",
            "Research Gaps Identified", "Proposed Methodology", "System Architecture (Implemented)",
            "Work-flow of Proposed System", "Implementation Progress & Tech Stack", "Dataset & Database Design",
            "Offer Optimizer: Model & Calculation", "Search, Substitution & Agent Design", "Testing & Results",
            "Work Remaining & Future Scope", "Conclusion", "References"]


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


rewrite_numbered(shape(S[1], "TextBox 8"), CONTENTS[:8], 1)
rewrite_numbered(shape(S[1], "TextBox 9"), CONTENTS[8:], 9)
for name in ("TextBox 8", "TextBox 9"):
    shape(S[1], name).width = Inches(5.6)
shape(S[1], "TextBox 8").left = Inches(1.0)
shape(S[1], "TextBox 9").left = Inches(6.9)

# =====================================================================  5. objectives + status
obj = S[4]
set_title(obj, "Objectives & Current Status")
replace_in(shape(obj, "Rounded Rectangle 15"), "subtotal, discounts, taxes and the final payable amount",
           "subtotal, discounts and the final payable amount")
STATUS = [("✓ Done · Gemini agent", True), ("✓ Done · 6 grounded tools", True),
          ("✓ Done · proven optimal", True), ("✓ Done · ranked, in-stock", True),
          ("✓ Done · live recompute", True), ("◔ Partly · harness next", False)]
for k, (label, done) in enumerate(STATUS):
    card = shape(obj, f"Rounded Rectangle {7 + 2 * k}")
    card.width = Inches(9.05)
    y = card.top / 914400 + 0.14
    box(obj, 10.35, y, 2.4, 0.47, NAVY if done else LRED, None if done else LRED_LN,
        [P(R(label, 11.5, WHITE if done else RED, True), align=PP_ALIGN.CENTER)], radius=0.5)
obj.notes_slide.notes_text_frame.text = (
    "Objectives 1-5 are implemented and tested. Objective 6 (evaluation) is partly done: we already measure "
    "grounding and latency in live tests; the full evaluation harness is the Phase II plan.")

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
replace_in(iface, "SMART-CART INTERFACE  (web / mobile app)", "INTERFACE  ·  terminal chat  |  REST API  |  web UI (next)")
iface.left, iface.width = Inches(3.3), Inches(6.75)
agent_box = shape(arch, "Rounded Rectangle 10")
agent_box.left, agent_box.width = Inches(2.6), Inches(8.15)
write(agent_box.text_frame, [P(R("LLM AGENT  —  LangGraph + Google Gemini 3.5 Flash-Lite   (planning · tool calling · "
                                 "grounding guard)", 12.5, WHITE, True), align=PP_ALIGN.CENTER)], MSO_ANCHOR.MIDDLE)
replace_in(shape(arch, "Rounded Rectangle 14"), "subtotal, tax, total", "subtotal, coupons, total")
write(shape(arch, "TextBox 29").text_frame, [P(R(
    "DATABASE LAYER (PostgreSQL 16 in Docker) — the single authoritative source of all transactional values · "
    "exposed through FastAPI (12 REST endpoints + /chat)", 11.5, RGBColor(0x70, 0x70, 0x70), italic=True),
    align=PP_ALIGN.CENTER)])
arch.notes_slide.notes_text_frame.text = (
    "This is the architecture from the synopsis, now as built. The agent is LangGraph with Gemini; the four "
    "tool groups read only PostgreSQL. The LLM never produces a price, stock count, location, discount or total.")

# =====================================================================  14. implementation progress (new)
prog = new_slide("Implementation Progress", notes=(
    "Five of seven milestones are complete. Each was built and tested before the next: data first, then the "
    "tools without any LLM, then the optimizer, the API, and finally the agent. Next is the web interface, then "
    "the evaluation harness."))
MS = [("Database & Seed Data", "9 tables · 849 products", "done"),
      ("Six Tool Functions", "locate · stock · substitutes · cart · bill · offers", "done"),
      ("Offer Optimizer", "exact, proven optimal", "done"),
      ("REST API", "FastAPI · 12 endpoints · checkout", "done"),
      ("LangGraph Agent", "Gemini · grounding guard", "done"),
      ("Web Frontend", "chat + live cart & bill", "next"),
      ("Evaluation Harness", "metrics vs. optimum", "planned")]
xs = [0.55 + k * 1.83 for k in range(7)]
line(prog, xs[0] + 0.85, 2.05, xs[-1] + 0.85, 2.05, LBLUE_LN, 3)
for k, (name, sub, st) in enumerate(MS):
    cx = xs[k] + 0.85
    fill, ln_, lab, col = {"done": (NAVY, None, "✓", WHITE), "next": (RED, None, "6", WHITE),
                           "planned": (WHITE, GREY_LN, "7", MUTED)}[st]
    o = box(prog, cx - 0.36, 1.69, 0.72, 0.72, fill, ln_, [P(R(lab, 18, col, True, font=SYM if lab == "✓" else FONT),
                                                             align=PP_ALIGN.CENTER)], shape=MSO_SHAPE.OVAL,
            m=(0, 0, 0, 0), lw=1.5)
    tb(prog, xs[k], 2.55, 1.7, 1.3, [P(R(f"{k + 1}. {name}", 13, NAVY if st != "next" else RED, True),
                                       align=PP_ALIGN.CENTER, after=3),
                                     P(R(sub, 11, MUTED), align=PP_ALIGN.CENTER),
                                     P(R({"done": "complete", "next": "next", "planned": "planned"}[st], 11,
                                         NAVY if st == "done" else RED if st == "next" else MUTED, italic=True),
                                       align=PP_ALIGN.CENTER, before=3)])
STATS = [("5 / 7", "milestones complete"), ("849", "real products in the simulated store"),
         ("72", "automated tests passing (69 offline + 3 live Gemini)"), ("0.43 ms", "median optimizer time per cart")]
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
         ("Tool layer", "Python 3.10 · six grounded tool functions · exact branch-and-bound offer optimizer"),
         ("API", "FastAPI + Uvicorn · 12 REST endpoints + /chat · Swagger UI · money sent as exact decimal strings"),
         ("Agent", "LangGraph state graph · LangChain · Google Gemini 3.5 Flash-Lite (fallback: 3.1 Flash-Lite Preview)"),
         ("Testing", "pytest (69 offline + 3 live) · FastAPI TestClient · scripted fake LLM for deterministic agent tests")]
for k, (lab, desc) in enumerate(STACK):
    y = 1.5 + k * 0.88
    box(tech, 0.55, y, 2.3, 0.7, NAVY, None, [P(R(lab, 15, WHITE, True), align=PP_ALIGN.CENTER)], radius=0.18)
    box(tech, 3.0, y, 9.75, 0.7, LBLUE if k % 2 == 0 else WHITE, LBLUE_LN, [P(R(desc, 14, TEXT))], radius=0.18)

# =====================================================================  16. dataset (new)
data = new_slide("Dataset & Data Preparation", notes=(
    "Product names, brands, categories and prices are real BigBasket data. No public dataset has aisle maps, "
    "stock levels or coupon rules, so we synthesized those on top, with a fixed random seed so the data is "
    "identical on every run. Out-of-stock items were chosen so each one has an in-stock substitute."))
PIPE = [("Raw dataset", "27,555 products", "11 categories · BigBasket (Kaggle)"),
        ("Cleaning", "17,106 products", "dedupe · strip text · MRP ≥ price · 9 categories kept"),
        ("Sampling by type", "849 products", "~100 per category · staples always included"),
        ("Synthesized store", "aisles · stock · coupons", "hand-authored rules · seed 42 (reproducible)")]
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
      R("Synthesized: ", 14, WHITE, True), R("aisle/shelf map, stock levels, coupon rules (not in any public dataset).",
                                             14, WHITE), after=4),
    P(R("Guarantee: ", 14, WHITE, True), R("every out-of-stock product has an in-stock same-type substitute — "
                                           "verified by 10/10 automated integrity checks.", 14, WHITE))], radius=0.1)

# =====================================================================  17. database design (new)
db = new_slide("Database Design (PostgreSQL)", notes=(
    "Nine tables in four groups. The key decision: live price and stock live only in inventory, and the cart "
    "stores no price at all, so the bill is recomputed from the database on every change and can never be "
    "invented by the model. Orders are an immutable snapshot for audit."))
GROUPS = [("Catalog", [("products", "product_id, name, brand, category, sub_category, product_type, "
                                    "base_price (MRP), rating", 3.1)]),
          ("Store layer", [("stores", "store_id, name, city", 0.85),
                           ("store_map", "product_id → aisle_no, shelf_code (A2-S5), shelf_level", 1.05),
                           ("inventory", "product_id → stock_qty, current_price (live)", 1.05)]),
          ("Offers", [("coupons", "code, PERCENT / FLAT, value, cap, min_cart_value, scope (cart / category / "
                                  "sub-category / brand), validity", 2.0),
                      ("coupon_conflicts", "coupon_a, coupon_b, reason  (never together)", 1.05)]),
          ("Cart & Orders", [("carts", "cart_id, session_id, status", 0.85),
                             ("cart_items", "cart_id, product_id, quantity  — no price!", 1.05),
                             ("orders", "totals, applied_coupons, line_items (JSONB)", 1.05)])]
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
      R("CHECK final_total = subtotal − discount_total  ·  CHECK stock_qty ≥ 0  ·  conflict pairs stored once "
        "(coupon_a < coupon_b)  ·  pg_trgm index for fuzzy search", 13.5, TEXT))], radius=0.08)

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
node(5.25, 1.6, 2.4, 0.78, "tools", "7 grounded tools", LBLUE, LBLUE_LN, dark=False)
node(5.25, 3.05, 2.4, 0.78, "auto_substitutes", "if a stock-out occurred", RED)
node(5.25, 4.5, 2.4, 0.78, "refresh_bill", "if the cart changed", RED)
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
    P(R("Graph enforces", 14.5, RED, True), after=5),
    P(R("stock-out ⇒ ranked substitutes always attached", 13, TEXT), bullet=True, after=4),
    P(R("cart change ⇒ fresh bill + budget status computed by code", 13, TEXT), bullet=True, after=4),
    P(R("every reply ⇒ grounding check before the shopper sees it", 13, TEXT), bullet=True, after=4),
    P(R("cart_id / session injected from state — the LLM cannot pick or invent them", 13, TEXT), bullet=True,
      after=4),
    P(R("model fallback + polite reply on 429 / 503 errors", 13, TEXT), bullet=True)],
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
      R("every reply in the live tests and the 3-turn demo conversation passed the guard (0 ungrounded values).",
        14.5, WHITE), after=6),
    P(R("Structural safeguards:  ", 14.5, WHITE, True),
      R("budget difference computed by code, cart id injected from state, prices passed as exact decimal strings, "
        "the LLM is never asked to do arithmetic.", 14.5, WHITE))], radius=0.08, m=(0.25, 0.1, 0.25, 0.1))

# =====================================================================  23. testing (new)
tst = new_slide("Testing & Validation", notes=(
    "69 offline tests run in about three seconds and need no API key. The most important result: on 700 cases "
    "the optimizer's answer equals the brute-force optimum over every possible coupon subset. Tests that change "
    "prices or stock restore them, and we verified the data is identical to a fresh seed afterwards."))
cd = CategoryChartData()
cd.categories = ["Offer optimizer", "Catalogue tools", "Cart & checkout", "REST API", "Agent graph", "Live Gemini"]
cd.add_series("Tests", (16, 17, 15, 10, 11, 3))
gf = tst.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.55), Inches(1.45), Inches(6.3), Inches(5.2), cd)
ch = gf.chart
chart_style(ch, 13)
ch.has_legend = False
ch.has_title = True
ch.chart_title.text_frame.text = "Automated tests by module (72, all passing)"
ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(14)
ch.chart_title.text_frame.paragraphs[0].runs[0].font.bold = True
ch.chart_title.text_frame.paragraphs[0].runs[0].font.color.rgb = NAVY
plot = ch.plots[0]
plot.gap_width = 55
plot.has_data_labels = True
plot.data_labels.font.size, plot.data_labels.font.bold = Pt(13), True
plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
ser = plot.series[0]
ser.format.fill.solid()
ser.format.fill.fore_color.rgb = NAVY
pt = ser.points[5]
pt.format.fill.solid()
pt.format.fill.fore_color.rgb = RED
ch.category_axis.reverse_order = True
ch.category_axis.format.line.color.rgb = GREY_LN
ch.category_axis.tick_labels.font.size = Pt(13)
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
TSTAT = [("100%", "optimizer = brute-force optimum on 700 cases (500 random + 200 real carts)"),
         ("10 / 10", "database integrity checks pass"),
         ("✓", "bill follows a live price change (nothing cached)"),
         ("0", "leftover carts / orders after the full suite; inventory restored exactly")]
for k, (big, small) in enumerate(TSTAT):
    y = 1.5 + k * 1.3
    box(tst, 7.15, y, 5.6, 1.15, LBLUE if k % 2 == 0 else WHITE, LBLUE_LN, None, radius=0.1)
    tb(tst, 7.25, y + 0.1, 1.55, 0.95, [P(R(big, 26, NAVY, True, font=SYM if big == "✓" else FONT),
                                          align=PP_ALIGN.CENTER)], anchor=MSO_ANCHOR.MIDDLE)
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
         [R("✓", 15, NAVY, True, font=SYM)]]]
table(lr, 0.55, 1.45, 12.2, LIVE, [4.0, 6.3, 0.9, 1.0], row_h=0.55, size=11.5,
      align=[PP_ALIGN.LEFT, PP_ALIGN.LEFT, PP_ALIGN.CENTER, PP_ALIGN.CENTER])
cd2 = CategoryChartData()
cd2.categories = ["Shopping request (turn 1)", "Location question"]
cd2.add_series("Gemini 3.1 Flash-Lite Preview", (47.1, 34.9))
cd2.add_series("Gemini 3.5 Flash-Lite (selected)", (6.4, 2.3))
gf2 = lr.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.55), Inches(3.85), Inches(7.4), Inches(2.85), cd2)
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
box(lr, 8.2, 3.85, 4.55, 2.8, LBLUE, LBLUE_LN, [
    P(R("~7–15× faster per turn", 17, NAVY, True), after=6),
    P(R("Per model call: ~11 s → ~1.2 s (measured on our API key)", 13, TEXT), bullet=True, after=4),
    P(R("Old model kept as automatic fallback", 13, TEXT), bullet=True, after=4),
    P(R("Free tier: 15 requests/min — rate-limit waits and a polite reply instead of a crash", 13, TEXT),
      bullet=True)], anchor=MSO_ANCHOR.TOP, radius=0.06, m=(0.2, 0.15, 0.2, 0.1))

# =====================================================================  25. sample output (new)
so = new_slide("Sample Output", notes=(
    "Left: an actual agent reply from the live run, with locations and totals that all came from the database. "
    "Right: the bill produced by the tool layer for the demo cart, showing the optimizer choosing BEV75 over "
    "the conflicting SAVE10 and hinting which coupon is almost unlocked."))
box(so, 0.55, 1.45, 6.6, 5.2, WHITE, LBLUE_LN, None, radius=0.04)
tb(so, 0.7, 1.52, 6.3, 0.35, [P(R("Live agent conversation (scripts/06_chat.py)", 13, NAVY, True))])
box(so, 2.2, 1.95, 4.8, 0.85, NAVY, None, [
    P(R("I need 2 toned milk, oats, instant coffee and Britannia brown bread. Budget 600 rupees.", 12, WHITE))],
    radius=0.2)
box(so, 0.75, 2.95, 5.6, 2.95, LBLUE, LBLUE_LN, [
    P(R("Added:", 13.5, NAVY, True), after=2),
    P(R("2 × Fresh Toned Milk – Aisle 2, A2-S5", 13.5), bullet=True, after=1),
    P(R("1 × Oats 100% Natural – Aisle 5, A5-S9", 13.5), bullet=True, after=1),
    P(R("1 × Grand Coffee – Aisle 6, A6-S1", 13.5), bullet=True, after=6),
    P(R("Britannia brown bread was out of stock, so I replaced it with ", 13.5),
      R("Brown Bread – Safe, Preservative Free", 13.5, TEXT, True), R(" (Aisle 2, A2-S2).", 13.5), after=6),
    P(R("Your final total is ", 13.5), R("₹273.20", 13.5, TEXT, True),
      R(", well within your budget of ₹600.00 (remaining ₹326.80).", 13.5))],
    anchor=MSO_ANCHOR.TOP, radius=0.08, m=(0.15, 0.12, 0.15, 0.05))
box(so, 0.75, 6.05, 6.25, 0.45, LRED, LRED_LN, [
    P(R("grounding: OK — every ₹ amount / aisle came from the database", 11.5, RED, True), align=PP_ALIGN.CENTER)],
    radius=0.4)
BILL = [("2 × Fresh Toned Milk", "66.00"), ("1 × Oats - 100% Natural", "85.00"), ("1 × Cappuccino Coffee", "90.00"),
        ("1 × Multigrain Bread", "50.00"), ("3 × Tea Premix", "417.90")]
paras = [P(R("Running bill (scripts/05_demo_tools.py)", 13, NAVY, True, font=FONT), after=8)]
paras += [P(R(f"{n:<24}₹{v:>8}", 12, TEXT, font=MONO)) for n, v in BILL]
paras += [P(R("-" * 33, 12, MUTED, font=MONO)),
          P(R(f"{'Subtotal':<24}₹{'708.90':>8}", 12, TEXT, True, font=MONO)),
          P(R(f"{'  (MRP ₹898.00)':<33}", 11, MUTED, font=MONO)),
          P(R(f"{'BEV75':<23}-₹{'75.00':>8}", 12, NAVY, True, font=MONO)),
          P(R("SAVE10 skipped: conflicts", 11, MUTED, font=MONO)),
          P(R("with BEV75, which saves more", 11, MUTED, font=MONO)),
          P(R("-" * 33, 12, MUTED, font=MONO)),
          P(R(f"{'TOTAL':<24}₹{'633.90':>8}", 13, RED, True, font=MONO), after=8),
          P(R("Almost unlocked: AMUL5 – add ₹34", 11, MUTED, italic=True, font=MONO))]
box(so, 7.4, 1.45, 5.35, 5.2, GREY, GREY_LN, paras, anchor=MSO_ANCHOR.TOP, radius=0.04, m=(0.3, 0.15, 0.2, 0.1))

# =====================================================================  26. work remaining (new)
wr = new_slide("Work Remaining (Phase II Plan)", notes=(
    "The backend and agent are complete. Phase II adds the web interface for shoppers and a scripted evaluation "
    "that measures exactly the objectives from the synopsis: grounding accuracy, discount captured compared with "
    "the optimum, task success and time per turn."))
PLAN = [("6", "Web Frontend", "next", ["React chat panel (POST /chat)", "live cart & running bill",
                                        "tool-call trace", "grounding badge per reply"]),
        ("7", "Evaluation Harness", "planned", ["scripted shopping goals", "grounding accuracy (% clean replies)",
                                                "discount captured vs. optimum", "task success & latency per turn"]),
        ("+", "Enhancements", "planned", ["persistent chat memory (PostgreSQL checkpointer)",
                                          "billing-enabled API key (higher rate limits)",
                                          "shopping-list / barcode input"])]
for k, (n_, title, st, items) in enumerate(PLAN):
    x = 0.55 + k * 4.12
    box(wr, x, 1.75, 3.88, 3.85, LBLUE if k != 1 else WHITE, LBLUE_LN,
        [P(R(title, 18, NAVY, True), after=3), P(R("next" if st == "next" else "planned", 13,
                                                   RED if st == "next" else MUTED, italic=True), after=12)]
        + [P(R(i, 15, TEXT), bullet=True, after=10) for i in items],
        anchor=MSO_ANCHOR.TOP, radius=0.06, m=(0.25, 0.45, 0.2, 0.1))
    num(wr, x + 0.25, 1.48, 0.56, n_, RED if st == "next" else NAVY, 16)
box(wr, 0.55, 5.85, 12.2, 0.75, NAVY, None, [
    P(R("Everything the frontend needs already exists: ", 14, WHITE, True),
      R("POST /chat returns the reply, tool calls, grounding result and the live bill.", 14, WHITE),
      align=PP_ALIGN.CENTER)], radius=0.1)

# =====================================================================  28. conclusion (new)
con = new_slide("Conclusion", notes=(
    "Summary: the grounded backend, the exact optimizer and the agent are working end to end with Gemini, and "
    "every claim here is backed by an automated test or a live run. Phase II is the interface and the "
    "quantitative evaluation."))
CON = ["Built the complete tool-grounded backend: PostgreSQL store model (849 real products, aisle map, live stock, "
       "19 coupons) and six tested tool functions.",
       "Formulated offer selection as a maximum-weight independent set and solved it exactly — matched the "
       "brute-force optimum on 700 / 700 test cases in under 4 ms.",
       "LangGraph agent on Google Gemini plans multi-step shopping; the graph enforces substitution, bill refresh "
       "and a grounding check on every reply.",
       "Live runs: correct multi-item carts, automatic out-of-stock substitution, all replies grounded, "
       "2–6 s per turn.",
       "Next (Phase II): web interface and quantitative evaluation against the synopsis objectives."]
box(con, 0.55, 1.5, 8.0, 5.15, WHITE, LBLUE_LN, [P(R(t, 15, TEXT), bullet=True, after=11) for t in CON],
    anchor=MSO_ANCHOR.TOP, radius=0.04, m=(0.25, 0.25, 0.25, 0.1))
for k, (big, small) in enumerate([("5 / 7", "milestones complete"), ("72", "automated tests passing"),
                                  ("0", "ungrounded values in live runs")]):
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

# =====================================================================  thank you (new)
ty = new_slide("Thank You", notes="Invite questions. Offer a live demo: python scripts/06_chat.py --trace")
tb(ty, 0.55, 2.3, 12.2, 1.2, [P(R("Thank You", 54, NAVY, True), align=PP_ALIGN.CENTER)])
tb(ty, 0.55, 3.55, 12.2, 0.6, [P(R("Questions & live demo", 24, RED, True), align=PP_ALIGN.CENTER)])
tb(ty, 0.55, 4.5, 12.2, 1.2, [
    P(R("Group D8  ·  Mayur Khamamkar  ·  Prathmesh Mhopare  ·  Aniket Mane  ·  Harshvardhan Magdum", 15, TEXT),
      align=PP_ALIGN.CENTER, after=4),
    P(R("Guide: Prof. Vrishali Prabhu", 15, MUTED, italic=True), align=PP_ALIGN.CENTER)])
set_title(ty, "")

# =====================================================================  order + drop "Expected Outcomes"
ORDER = [S[0], S[1], S[2], S[3], S[4], S[5], S[6], S[7], cmp_, S[8], S[9], S[10], S[11],
         prog, tech, data, db, opt, ex, sub, ag, gr, tst, lr, so, wr, S[13], con, ref, ty]
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
