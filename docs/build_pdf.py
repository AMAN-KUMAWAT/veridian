"""Convert docs/manual.md into a styled PDF using fpdf2 (pure-python, no system deps)."""
import re
from fpdf import FPDF

SRC = "/app/docs/manual.md"
OUT = "/app/Veridian_Guide.pdf"

NAVY = (15, 44, 76)
TEAL = (14, 165, 160)
INK = (31, 41, 55)
GREY = (110, 120, 130)


def clean(t: str) -> str:
    repl = {"—": "-", "–": "-", "·": "-", "’": "'", "‘": "'", "“": '"', "”": '"',
            "→": "->", "×": "x", "≥": ">=", "⚠": "!", "…": "..."}
    for k, v in repl.items():
        t = t.replace(k, v)
    return t.encode("latin-1", "replace").decode("latin-1")


class PDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 8, "Veridian - Owner's Manual", align="L")
        self.cell(0, 8, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*GREY)
        self.cell(0, 8, "Confidential - contains configuration references. Do not share publicly.", align="C")


pdf = PDF()
pdf.set_auto_page_break(auto=True, margin=16)
pdf.add_page()

# Cover block
pdf.set_fill_color(*NAVY)
pdf.rect(0, 0, 210, 55, style="F")
pdf.set_xy(15, 16)
pdf.set_font("Helvetica", "B", 26)
pdf.set_text_color(255, 255, 255)
pdf.cell(0, 12, "Veridian", new_x="LMARGIN", new_y="NEXT")
pdf.set_x(15)
pdf.set_font("Helvetica", "", 11)
pdf.set_text_color(230, 247, 245)
pdf.cell(0, 8, "Real-Time Risk Intelligence for Smarter Reinsurance")
pdf.ln(30)

lines = open(SRC, encoding="utf-8").read().splitlines()
in_code = False
for raw in lines:
    line = clean(raw.rstrip())
    if line.strip() == "---":
        pdf.ln(1)
        pdf.set_draw_color(220, 224, 228)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(3)
        continue
    if line.startswith("```"):
        in_code = not in_code
        continue
    if in_code:
        pdf.set_font("Courier", "", 8.5)
        pdf.set_text_color(*INK)
        pdf.multi_cell(0, 4.6, "  " + line)
        continue
    if line.startswith("# "):
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(*NAVY)
        pdf.multi_cell(0, 9, line[2:])
        pdf.ln(1)
    elif line.startswith("## "):
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*TEAL)
        pdf.multi_cell(0, 7, line[3:])
        pdf.ln(0.5)
    elif line.startswith("### "):
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*NAVY)
        pdf.multi_cell(0, 6, line[4:])
    elif re.match(r"^\s*-\s+", line):
        indent = (len(line) - len(line.lstrip())) 
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*INK)
        text = re.sub(r"^\s*-\s+", "", line)
        pdf.set_x(15 + (6 if indent >= 2 else 0))
        pdf.multi_cell(0, 5.4, chr(149) + " " + text)
    elif line.strip() == "":
        pdf.ln(2)
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*INK)
        pdf.multi_cell(0, 5.4, line)

pdf.output(OUT)
print("WROTE", OUT)
