---
name: create-xlsx
description: Create or edit an Excel .xlsx spreadsheet with multiple sheets, cells, formulas, number formats, styling, and charts. Use when asked to build a spreadsheet, export tabular data to Excel, generate a report workbook, or produce a .xlsx file.
license: MIT
metadata:
  version: "1.0"
  author: lca
---

# Create a spreadsheet (.xlsx) with openpyxl

Generate `.xlsx` by writing and running a Python script with **openpyxl**
(install: `uv add openpyxl`).

## Pattern

```python
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.chart import BarChart, Reference

wb = Workbook()                                    # or load_workbook("existing.xlsx")
ws = wb.active
ws.title = "Sales"

ws.append(["Month", "Revenue"])                    # header row
for cell in ws[1]:                                 # style the header
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="4472C4")
    cell.alignment = Alignment(horizontal="center")

rows = [("Jan", 12000), ("Feb", 15000), ("Mar", 17500)]
for month, rev in rows:
    ws.append([month, rev])

ws["B5"] = "=SUM(B2:B4)"                            # formula
for row in ws["B2:B5"]:
    for c in row:
        c.number_format = "#,##0"                  # thousands separator
ws.column_dimensions["A"].width = 14

chart = BarChart()
data = Reference(ws, min_col=2, min_row=1, max_row=4)
cats = Reference(ws, min_col=1, min_row=2, max_row=4)
chart.add_data(data, titles_from_data=True)
chart.set_categories(cats)
ws.add_chart(chart, "D2")

wb.create_sheet("Notes")                           # a second sheet
wb.save("sales.xlsx")
```

## Idioms

- `ws.append(list)` adds a row; address cells as `ws["A1"]` or `ws.cell(row, column)`.
- Write formulas as strings starting with `=`; openpyxl stores them (Excel
  evaluates on open).
- `number_format`, `Font`, `PatternFill`, `Alignment` from `openpyxl.styles`.
- To edit an existing workbook: `load_workbook(path)`, mutate, `save()`. Use
  `load_workbook(path, data_only=True)` to read computed values instead of formulas.

## Validate

- The script runs and the `.xlsx` exists; re-open with `load_workbook(path)` and
  assert sheet names / a known cell value.
