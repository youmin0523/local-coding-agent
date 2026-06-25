---
name: normalized-postgres-schema
description: Design a normalized (1NF-3NF) PostgreSQL schema with SQLAlchemy 2.0 async models and an Alembic migration. Use when the user asks to design a database schema, model tables/entities, fix a denormalized or duplicated-data schema, or set up SQLAlchemy + PostgreSQL persistence.
license: MIT
metadata:
  version: "1.0"
  author: lca
---

# Normalized PostgreSQL schema (3NF) with SQLAlchemy 2.0 async

Design relational schemas that reach **Third Normal Form** unless a measured
reason says otherwise, then express them as typed SQLAlchemy 2.0 models.

## Procedure

1. **List entities and their real-world keys.** One table per entity; pick a
   primary key (prefer a surrogate `id` plus a UNIQUE natural key).
2. **1NF** — no repeating groups or multi-value columns. A column holding a list
   (e.g. `tags = "a,b,c"`) becomes its own row-per-value child table.
3. **2NF** — every non-key column depends on the *whole* primary key. On a
   composite-key table, move columns that depend on only part of the key out to
   the table whose key that part is. (Most single-`id` tables are 2NF already.)
4. **3NF** — no transitive dependencies: a non-key column must not depend on
   another non-key column. If `order.customer_city` is determined by
   `order.customer_id`, move city to a `customer` table and reference it.
5. **Relationships** — model many-to-many with a join table (its own PK or the
   composite of both FKs); add `ON DELETE` rules deliberately.
6. **Constraints carry the invariants** — `NOT NULL`, `UNIQUE`, `CHECK`, and
   `FOREIGN KEY` in the schema, not only in app code. Index every FK.

## SQLAlchemy 2.0 (async) shape

```python
from datetime import datetime
from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase): ...

class Customer(Base):
    __tablename__ = "customer"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)            # natural key
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")

class Order(Base):
    __tablename__ = "order"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    customer: Mapped[Customer] = relationship(back_populates="orders")
    # NOTE: never store customer_email/customer_city here — that's the 3NF violation.
```

- Use `async_sessionmaker(engine, expire_on_commit=False)` and eager-load
  relationships with `selectinload()` to avoid `MissingGreenlet` (see the
  error-fix recipes).
- Generate the migration with Alembic, then **read it** before applying:
  `alembic revision --autogenerate -m "..."` → review → `alembic upgrade head`.

## Justified denormalization

Denormalize only with a reason: a cache/JSON column for read performance, or a
column a normal form can't express (e.g. an embedding vector). Document why in a
comment so reviewers see it was a choice, not an accident.

## Validate

- No column repeats data derivable from another table (3NF check).
- Every FK is indexed and has an `ON DELETE` policy.
- The migration round-trips: `upgrade head` then `downgrade -1` cleanly.
