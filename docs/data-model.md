# Data model & normalization (1NF–3NF)

lca's persistence is intentionally small and **normalized to 3NF**. This documents the
schema, the per-table normal-form analysis, and the backend normalization rules the
agent should follow when designing schemas for the user's PostgreSQL services.

## lca's own schema (SQLite, regenerable)

### Code index (`code_index.sqlite`)
```
files(path PK, mtime, size)
chunks(id PK, path, start_line, end_line, text, vec)
chunks_fts(text)            -- FTS5 keyword index, keyed by chunks.rowid
```
- **files** — every non-key attribute (mtime, size) depends on the whole key (`path`). 1NF/2NF/3NF ✓.
- **chunks** — surrogate single-column PK (`id`) ⇒ no partial dependency (2NF ✓). No non-key
  attribute determines another non-key attribute ⇒ no transitive dependency (3NF ✓). File-level
  attributes (mtime/size) are **not** duplicated here — they live in `files`, so the file→metadata
  dependency is already separated. `path` is a deliberate reference to `files.path` (a chunk belongs
  to a file); the duplication of `path` across a file's chunks is a foreign-key reference, **not** a
  redundancy violation.
- **vec** stores the embedding as a JSON array. Strict 1NF prizes atomic columns, but an embedding
  is an opaque, indivisible value (you never query an individual dimension relationally) — storing it
  as one blob/array is the standard, accepted pattern (sqlite-vec/pgvector do the same).

### Experience memory (`experience.sqlite`)
```
memories(id PK, kind, title, content, source, vec, created_at, UNIQUE(kind, title))
```
- Single-column surrogate PK; `(kind, title)` is a candidate key (UNIQUE). No non-key attribute
  determines another ⇒ 3NF ✓ (modulo the same justified `vec` exception).

**Conclusion:** all lca tables satisfy 1NF, 2NF and 3NF. The only non-atomic columns are embedding
vectors, an intentional and conventional exception.

## Normalization rules for the backends (PostgreSQL + SQLAlchemy 2.0)

Apply these when generating or reviewing schemas:

- **1NF** — atomic columns, no repeating groups or arrays-as-columns. A "tags" or "items" list
  becomes its own row set in a child table (or a junction table for many-to-many).
- **2NF** — no non-key attribute depends on only *part* of a composite key. With surrogate
  single-column PKs (the norm), 2NF is automatic; it bites mainly on association tables with
  composite natural keys — move attributes that depend on one key column into that column's table.
- **3NF** — no transitive dependencies (non-key → non-key). The classic smell: storing
  `customer_name`/`customer_email` on every `order` row. Extract `customers` and reference it by
  `customer_id` (FK). Likewise pull derived/lookup data (city→region, product→category) into their
  own tables.
- **Integrity** — declare `FOREIGN KEY ... REFERENCES` with sensible `ON DELETE`, add `UNIQUE`
  constraints for candidate keys, and prefer surrogate keys (`UUID`/`BIGSERIAL`) with natural keys
  enforced via `UNIQUE`.
- **Pragmatic denormalization** — only for measured read-path needs (reporting/materialized views,
  cached aggregates), kept consistent by triggers/jobs, and documented as a deliberate exception.

In SQLAlchemy 2.0: typed `Mapped[...]`/`mapped_column`, `ForeignKey(...)` + `relationship(...)`,
keep ORM models separate from Pydantic v2 schemas (matches the user's AeroInspect/kd-shutter layout).
