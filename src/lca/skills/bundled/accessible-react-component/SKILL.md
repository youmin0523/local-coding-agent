---
name: accessible-react-component
description: Build an accessible, typed React 19 + Tailwind component using hooks correctly. Use when the user asks to create or refactor a React component, a custom hook, a form, a modal/dialog, or any UI that must be keyboard- and screen-reader-accessible.
license: MIT
metadata:
  version: "1.0"
  author: lca
---

# Accessible React 19 + Tailwind component

## Hook rules (non-negotiable)

- Call hooks at the **top level**, unconditionally, in the same order every
  render — never inside `if`/loops/callbacks (prevents "Rendered more hooks…").
- Give every `useEffect` a correct dependency array; clean up subscriptions in
  the returned function. Avoid stale closures by depending on the values used.
- Lift shared logic into a **custom hook** (`useX`) that itself only calls hooks
  at the top level and returns a stable value/handle.
- Prefer derived state over redundant `useState`; reach for `useMemo`/
  `useCallback` only when a measured re-render cost justifies it.

## Accessibility (WCAG 2.2 AA essentials)

- **Semantic HTML first** — `<button>`, `<nav>`, `<label htmlFor>`; add ARIA
  only when no native element fits (and prefer none over wrong ARIA).
- Every interactive control is **keyboard reachable** and shows a visible focus
  ring (don't remove outlines without a replacement). Manage focus on
  open/close for dialogs; trap focus in modals; restore it on close.
- Inputs have associated `<label>`s; errors use `aria-describedby` and
  `aria-invalid`.
- Color contrast ≥ 4.5:1 for text. Don't rely on color alone to convey meaning.
- Respect `prefers-reduced-motion` for animations.

## Shape

```tsx
import { useId, useState } from "react";

interface CounterProps {
  label: string;
  initial?: number;
}

export function Counter({ label, initial = 0 }: CounterProps) {
  const [count, setCount] = useState(initial);
  const id = useId();
  return (
    <div className="flex items-center gap-3">
      <span id={id} className="text-sm font-medium">{label}: {count}</span>
      <button
        type="button"
        aria-labelledby={id}
        onClick={() => setCount((c) => c + 1)}
        className="rounded-md px-3 py-1.5 bg-blue-600 text-white
                   hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2"
      >
        Increment
      </button>
    </div>
  );
}
```

- Use the functional updater (`setCount(c => c + 1)`) so rapid clicks don't drop
  updates (stale-state pitfall).
- Compose Tailwind classes with `cn()`/`clsx` + `tailwind-merge`; avoid class
  soup by extracting variants. For unstyled-but-accessible primitives (dialog,
  popover, menu) build on Radix UI / shadcn/ui rather than hand-rolling ARIA.

## Validate

- Component is typed (props interface, no `any`).
- Keyboard-only: every action reachable; focus visible; modal focus trapped.
- If a dev server is running, use `browser_check` to assert it renders and
  `browser_screenshot` to eyeball layout.
