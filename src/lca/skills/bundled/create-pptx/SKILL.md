---
name: create-pptx
description: Create a PowerPoint .pptx presentation with title and content slides, bullet lists, tables, images, and speaker notes. Use when asked to make slides, build a deck or presentation, or generate a .pptx file.
license: MIT
metadata:
  version: "1.0"
  author: lca
---

# Create a presentation (.pptx) with python-pptx

Generate `.pptx` by writing and running a Python script with **python-pptx**
(install: `uv add python-pptx`; import name is `pptx`).

## Pattern

```python
from pptx import Presentation
from pptx.util import Inches, Pt

prs = Presentation()                               # blank 4:3; use a template path to theme

# Title slide (layout 0)
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = "Project Kickoff"
slide.placeholders[1].text = "Team Sync · 2026"

# Title + content slide (layout 1) with a bulleted body
slide = prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text = "Goals"
body = slide.placeholders[1].text_frame
body.text = "Ship the MVP"                          # first bullet
for line, level in [("Validate with users", 1), ("Iterate weekly", 1)]:
    p = body.add_paragraph()
    p.text, p.level = line, level

# A text box with custom size/position
box = slide.shapes.add_textbox(Inches(1), Inches(5), Inches(8), Inches(1)).text_frame
box.text = "Confidential"
box.paragraphs[0].runs[0].font.size = Pt(12)

# slide.shapes.add_picture("logo.png", Inches(8), Inches(0.3), height=Inches(0.8))
# slide.notes_slide.notes_text_frame.text = "Speaker notes here"
prs.save("kickoff.pptx")
```

## Idioms

- Common layouts: `0` = title, `1` = title+content, `5` = title only, `6` = blank.
- The body placeholder is a `text_frame`; its `.text` sets the first bullet, then
  `add_paragraph()` + `.level` (0-based) adds nested bullets.
- Sizes/positions use `Inches`/`Pt` from `pptx.util` — EMU under the hood.
- Add a table with `slide.shapes.add_table(rows, cols, x, y, w, h).table`.

## Validate

- The script runs and the `.pptx` exists; `len(Presentation(path).slides)` matches
  the number of slides you added.
