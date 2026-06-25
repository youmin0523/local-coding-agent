---
name: secure-fastapi-endpoint
description: Write a secure FastAPI endpoint with Pydantic v2 validation, no hardcoded secrets, parameterized queries, and proper auth/error handling. Use when the user asks to add or review an API route/endpoint, handle a request body, accept user input, or build a FastAPI handler that touches the database or secrets.
license: MIT
metadata:
  version: "1.0"
  author: lca
---

# Secure FastAPI endpoint

Apply these defaults to every route; they map to the OWASP API Top 10.

## Checklist (do all)

1. **Validate input with a Pydantic v2 model** — never read raw dicts. Constrain
   types/lengths/ranges (`Field(max_length=...)`, `EmailStr`). Reject unknown
   fields with `model_config = ConfigDict(extra="forbid")`.
2. **No hardcoded secrets** — read keys/passwords from settings/env
   (`pydantic-settings` `BaseSettings`), never literals in code. (Run the
   `secret_scan` tool to confirm.)
3. **Parameterized queries only** — SQLAlchemy ORM/Core or bound params. Never
   f-string/format user input into SQL (SQL injection).
4. **Authn/Authz** — depend on an auth dependency; check the caller *owns* the
   resource (object-level authz) to prevent IDOR — `403` if not, don't leak it.
5. **Least data out** — a response model that excludes internal fields
   (`response_model=PublicUser`); never return password hashes/tokens.
6. **Explicit errors** — raise `HTTPException(status_code, detail)`; don't leak
   stack traces or DB errors to the client.
7. **Async + session hygiene** — `async def`, inject an `AsyncSession` via a
   dependency that closes it; `await db.commit()`.

## Shape

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/items", tags=["items"])

class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)

class ItemOut(BaseModel):
    id: int
    name: str

@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),     # authn
) -> Item:
    item = Item(name=payload.name, owner_id=user.id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item

@router.get("/{item_id}", response_model=ItemOut)
async def read_item(item_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(current_user)) -> Item:
    item = await db.scalar(select(Item).where(Item.id == item_id))
    if item is None or item.owner_id != user.id:   # object-level authz (no IDOR)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    return item
```

## Validate

- `secret_scan` reports no hardcoded secrets.
- No user input is string-concatenated into SQL/shell.
- Cross-tenant access returns 404/403, never another user's row.
- `pytest` covers an authorized 200 and an unauthorized 403/404.
