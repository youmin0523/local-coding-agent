---
name: create-diagram
description: Create a flowchart, sequence, class, ER, state, or Gantt diagram as Mermaid (embeddable in Markdown) or Graphviz DOT, and optionally render it to SVG/PNG. Use when asked to draw or visualize a diagram, flowchart, architecture, sequence/ER/class/state diagram, or mention mermaid/graphviz.
license: MIT
metadata:
  version: "1.0"
  author: lca
---

# Create a diagram (Mermaid / Graphviz)

Default to **Mermaid**: it embeds directly in Markdown and renders on GitHub,
GitLab, VS Code, Obsidian, and Notion — no build step. Put it in a fenced block:

<pre>```mermaid
flowchart TD
    A[Start] --> B{Authed?}
    B -- yes --> C[Dashboard]
    B -- no --> D[Login]
    D --> B
```</pre>

## Pick the diagram type

```mermaid
%% flowchart: TD (top-down) or LR (left-right)
flowchart LR
  U[User] --> API[FastAPI] --> DB[(PostgreSQL)]
```
```mermaid
sequenceDiagram
  participant U as User
  participant S as Server
  U->>S: POST /login
  S-->>U: 200 + token
```
```mermaid
erDiagram
  CUSTOMER ||--o{ ORDER : places
  ORDER ||--|{ ORDER_ITEM : contains
```
```mermaid
classDiagram
  class Order { +int id; +total() }
  Customer "1" --> "*" Order
```
```mermaid
stateDiagram-v2
  [*] --> Idle
  Idle --> Running : start
  Running --> [*] : done
```
```mermaid
gantt
  title Plan
  section Build
  Design :a1, 2026-01-01, 7d
  Code   :after a1, 14d
```

## Syntax tips

- Node shapes: `[rect]`, `(round)`, `([stadium])`, `{rhombus}`, `[(database)]`.
- Edges: `-->`, `---`, `-- label -->`, `-.->` (dotted), `==>` (thick).
- Quote labels with spaces/special chars: `A["Place order"]`. `subgraph name ... end`
  groups nodes. Keep one statement per line.

## Render to an image (optional)

- **Mermaid CLI**: `npx -y @mermaid-js/mermaid-cli -i diagram.mmd -o diagram.svg`
  (or `.png`). Preview/export at https://mermaid.live.
- **Graphviz** when you need fine layout control: write DOT and run
  `dot -Tsvg graph.dot -o graph.svg`.

```dot
digraph G { rankdir=LR; User -> API -> DB; }
```

## Validate

- The Mermaid block parses (paste into mermaid.live or render with mmdc).
- Node/edge labels with spaces are quoted; every `subgraph` has an `end`.
- The diagram matches the described relationships/flow.
