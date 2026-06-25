---
name: write-markdown
description: Write a clean, well-structured Markdown (.md) file or produce a single copy-pasteable Markdown answer. Use when asked to create a README/notes/doc in markdown, write a .md file, or give the answer "as markdown I can copy at once".
license: MIT
metadata:
  version: "1.0"
  author: lca
---

# Write Markdown (.md)

Produce GitHub-Flavored Markdown that renders cleanly and is easy to copy whole.

## Structure

- One `#` H1 title; sections with `##`/`###` in order (don't skip levels).
- Short paragraphs; blank line between blocks. Wrap prose ~80-100 cols.
- Lists: `-` for bullets, `1.` for ordered, `- [ ]`/`- [x]` for task lists.
- **Code** in fenced blocks with a language tag for highlighting:
  <pre>```python
  print("hello")
  ```</pre>
- Tables with a header separator row; links as `[text](url)`; block quotes `>`.
- Inline code with backticks for file names, commands, identifiers.

## Saving to a file

Write the content to a `.md` file with the `write_file` tool (UTF-8). Suggested
names: `README.md`, `NOTES.md`, `<topic>.md`. Verify it reads back.

## "Give it as markdown I can copy at once"

When the user wants a single copyable block, return the **entire answer as one
self-contained fenced markdown block** so a one-shot copy captures everything:

<pre>```markdown
# Title

## Section
- point one
- point two

```python
code here
```
```</pre>

- Keep it self-contained (no "see above"); inline what's needed.
- From the CLI the user can also run `lca ask "..." --copy` to copy the answer to
  the clipboard, or `--md out.md` to save it straight to a file.

## Validate

- Renders correctly (headings nest, code fences are closed, tables aligned).
- If saved, the `.md` file exists and re-reads identically.
- If a single copy block was requested, the whole answer is inside one fence.
