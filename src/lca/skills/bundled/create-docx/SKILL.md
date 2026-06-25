---
name: create-docx
description: Create or edit a Microsoft Word .docx document with headings, paragraphs, styled runs, tables, lists, and images. Use when asked to write or generate a Word document, a report, a letter, meeting minutes, or any .docx file.
license: MIT
metadata:
  version: "1.0"
  author: lca
---

# Create a Word document (.docx) with python-docx

Generate `.docx` by writing and running a Python script with **python-docx**
(install: `uv add python-docx`; import name is `docx`).

## Pattern

```python
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()                                  # or Document("existing.docx") to edit

doc.add_heading("Quarterly Report", level=0)      # title
doc.add_heading("Summary", level=1)
p = doc.add_paragraph("Revenue grew ")
p.add_run("18%").bold = True                       # styled run inside a paragraph
p.add_run(" quarter over quarter.")

doc.add_paragraph("First item", style="List Bullet")
doc.add_paragraph("Step one", style="List Number")

table = doc.add_table(rows=1, cols=2)
table.style = "Light Grid Accent 1"
hdr = table.rows[0].cells
hdr[0].text, hdr[1].text = "Metric", "Value"
for name, value in [("Revenue", "$1.2M"), ("Users", "8,400")]:
    cells = table.add_row().cells
    cells[0].text, cells[1].text = name, value

# doc.add_picture("chart.png", width=Inches(5))
doc.save("report.docx")
```

## Idioms

- A paragraph is a list of **runs**; set bold/italic/size on a run, not the
  paragraph. Use `run.font.size = Pt(12)`.
- Use built-in styles by name (`"Heading 1"`, `"List Bullet"`, `"Title"`) instead
  of manual formatting where possible.
- To edit an existing file, open it with `Document(path)`, mutate, and `save()`.
- Page breaks: `doc.add_page_break()`. Alignment via
  `paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER`.

## Validate

- The script runs without error and the `.docx` file exists and is non-empty.
- Re-open it with `Document(path)` and assert expected headings/rows are present.
