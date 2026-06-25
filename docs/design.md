# UI/UX & design guide

Tailored to **React 19 + Vite + Tailwind CSS v4 + Motion** (Framer Motion, now `motion`). Verified mid-2026.

## Design systems

Choose a component layer by how much styling control vs. batteries you want, from most control to most batteries: **headless primitives** (you own all CSS) → **copy-in components** (you own pre-styled code) → **batteries-included styled libraries**.

| Library | Distribution | Styling | Best when |
|---|---|---|---|
| **Radix UI Primitives** | npm `radix-ui` | You bring Tailwind | Bespoke design system; WAI-ARIA for free, zero starting visuals. |
| **Headless UI** | npm `@headlessui/react` v2 | You bring Tailwind | Pure-Tailwind project, ~16 accessible primitives; most beginner-friendly. |
| **shadcn/ui** | CLI copy-in | Tailwind, in YOUR repo | **Default choice.** Pre-styled, accessible, fully owned/editable code; no lock-in. |
| **Tailwind Plus / Catalyst** | Paid copy-in | Tailwind, in YOUR repo | Have a license; polished app UI on Headless UI + `motion`. |
| **MUI** v9 | npm, Emotion | CSS-in-JS | Material Design fast; enterprise dashboards. |
| **Chakra UI** v3 | npm + snippets | Built-in system | Ergonomic style-props DX; lighter than v2 (no emotion/styled or framer-motion). |
| **Ant Design** v6 | npm `antd` | CSS-in-JS | Data-dense enterprise/admin; v6 natively supports React 19 (drop the v5 shim). |

**For this stack:** default to **shadcn/ui** on Radix/Base UI — Tailwind-native, copies code into your repo so you style and animate freely with Motion/GSAP. Use **Radix or Headless UI** directly when you want zero pre-styling. **Do not mix two styled systems** (MUI + Chakra, or MUI + Tailwind): duplicate theming, larger bundles, specificity fights. Reserve MUI/Chakra/Ant for shipping a complete product UI fast where Tailwind composition is secondary. Headless/copy-in options let you control the DOM for custom animation; styled libraries bake in their own transitions that fight Motion/GSAP.

### Tokens, composition & dark mode

Tailwind v4 is **CSS-first**: define tokens in a `@theme` block (no `tailwind.config.js`), and every token becomes both a utility and a runtime CSS variable.

```css
@import "tailwindcss";
@theme {
  --color-brand-500: oklch(0.62 0.19 256);  /* → bg-brand-500 + var(--color-brand-500) */
  --radius-card: 1rem;                        /* → rounded-card */
  --spacing: 0.25rem;                         /* drives the whole spacing scale */
}
```

- Use `@theme` for tokens that should **generate utilities**; plain `:root` for vars used only in custom CSS. Reference framework vars with `@theme inline { --font-sans: var(--font-inter); }`.
- **Compose without class soup** with the de-facto `cn()` helper (`clsx` joins conditionals, `tailwind-merge` resolves conflicts like `px-2 px-4 → px-4`):

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export const cn = (...i: ClassValue[]) => twMerge(clsx(i));
```

Every component exposing `className` merges it last: `cn("base styles", className)`. Extract a React component (not `@apply`) to reuse long utility lists.
- **Dark mode** follows the OS by default (`dark:bg-gray-800`, zero JS). For a user toggle, `@custom-variant dark (&:where(.dark, .dark *));` — `:where()` keeps zero specificity so overrides stay predictable; set the class inline in `<head>` to avoid FOUC.

## UI/UX principles

Great UI looks **systematic**, not creative — constrained scales plus deliberate hierarchy.

- **Hierarchy by visual importance, not HTML tag.** Three independent levers: size (type scale), weight (`font-normal` 400 body, `font-semibold/bold` for emphasis), color (primary dark, secondary `text-gray-500`, tertiary lighter). **Design in grayscale first**; if hierarchy reads without color it is genuine.
- **Spacing on the 8pt grid.** Pick from a constrained scale (8/16/24/32/48/64; 4px for tight) — never random px. Tailwind tokens: `2`=8px, `4`=16px, `6`=24px, `8`=32px, `12`=48px. **Proximity rule:** spacing *inside* a group < spacing *between* groups. Prefer `gap-*`/`space-y-*` over margins. Start with too much whitespace, then remove.
- **Type:** ≤ 2 families, a modular scale (`text-xs`…`text-4xl` = 12…36px). Body ~16px, `leading-relaxed` for paragraphs, `leading-tight` for headings, `max-w-prose` for ~45–75 char measure.
- **Color 60-30-10:** ~60% neutral surfaces, ~30% secondary, ~10% accent reserved for CTAs. Define once as `@theme` OKLCH tokens; build full 50→950 ramps. Add color *after* grayscale hierarchy works.
- **Gestalt:** group related items with shared spacing, share a few alignment edges, unify with a card (common region), repeat treatment for same-kind items (similarity). Misalignment reads as broken.
- **Consistency:** centralize decisions in tokens + a small set of components (`<Button variant>`, `<Card>`); reuse, never re-style. Standardize radius/shadow.
- **Whitespace** is an active tool — generous padding signals quality and improves scannability; crowding cheapens.
- **Responsive, mobile-first:** unprefixed = all sizes, a prefix = that breakpoint *and up* (`sm` 640 / `md` 768 / `lg` 1024 / `xl` 1280 / `2xl` 1536). Read `md:` as "at the md breakpoint." Use built-in **container queries** (`@container` + `@lg:`) for reusable components that respond to their slot, not the viewport.
- **Empty / loading / error states are part of the UI.** Loading: skeletons (`animate-pulse`) mirroring final layout to avoid shift. Empty: short message + one clear CTA. Error: plain language + a retry path, never a raw stack trace.

## Accessibility

Baseline target is **WCAG 2.2 Level AA** (current; EU EAA enforced since 28 Jun 2025). 2.2 is backwards-compatible with 2.0/2.1; only **4.1.1 Parsing is removed**. Automated tools catch ~30–40% — pair with manual keyboard + screen-reader passes.

- **New AA criteria that hit React UIs:** targets **≥ 24×24 CSS px** (Tailwind `min-h-6 min-w-6`; 44px comfortable) (2.5.8); keyboard focus must stay at least partially visible under sticky headers — use `scroll-margin-top` (2.4.11); every drag interaction needs a single-pointer alternative (2.5.7); login must allow password managers, paste, and passkeys (3.3.8).
- **Semantic HTML first, ARIA second.** "No ARIA is better than bad ARIA." Use `<button type="button">` for actions, `<a href>` for navigation — a clickable `<div onClick>` is the most common React a11y bug. Generate ARIA-relationship IDs with React 19 `useId()`. Never put `aria-hidden`/`role="presentation"` on a focusable element. Follow APG patterns (Dialog, Tabs, Combobox, Menu).
- **Keyboard & focus:** `tabIndex` only `0` or `-1`, never positive. On SPA route change, move focus to the new `<h1 tabindex={-1}>` (browsers don't reset focus). Skip link → `<main id="main" tabindex="-1">`. Prefer native `<dialog>.showModal()` for free focus trap + Esc + inert background; restore focus to the trigger on close.
- **Visible focus & contrast:** never `outline: none` without a replacement. Use `:focus-visible` (`focus-visible:outline-2 focus-visible:outline-offset-2`). **Prefer `outline` over `ring`** — box-shadow rings vanish in Windows High Contrast / forced-colors; add a `forced-colors:` fallback if you use `ring-*`. Text contrast **≥ 4.5:1** (large ≥ 3:1), non-text/UI/focus **≥ 3:1**, and color is never the only signal (pair red errors with text/icon).
- **Forms:** every input gets a visible `<label htmlFor={id}>` (placeholders are not labels); group radios in `<fieldset><legend>`. On error: `aria-invalid="true"` (use `undefined`, not `false`, when valid), `aria-describedby={errorId}` with the error ID listed *before* helper text, announce via `role="alert"`/`aria-live`, and move focus to the first invalid field. Use correct `type` + `autocomplete` tokens.
- **Verify:** `eslint-plugin-jsx-a11y` in lint, `axe-core`/Lighthouse in CI, `vitest-axe`/`jest-axe` per component; test at 200%/400% zoom and forced-colors.

## Tailwind & motion

Motion (formerly Framer Motion) is the package `motion`; import from `motion/react` (v12). `npm install motion`.

- **Animate to clarify state and guide attention, not to decorate.** Keep durations short (~150–300ms), ease naturally.
- **Variants** name states and orchestrate parent→child sequencing (`staggerChildren`, `when: "beforeChildren"`); a parent's `animate` label propagates to children. Use `whileHover`/`whileTap`/`whileInView` for gestures and scroll reveals. Animate tokens directly: `animate={{ backgroundColor: "var(--color-brand-500)" }}`.
- **AnimatePresence** animates elements out as they leave the tree — children need stable unique `key`s (IDs, not indices); `mode="wait"` sequences exit before enter, `popLayout` reflows siblings immediately.
- **Layout animations:** add `layout` to auto-animate layout changes (FLIP); a matching `layoutId` creates shared-element transitions; wrap independently-rendering siblings in `LayoutGroup`.
- **Reduced motion is non-negotiable.** Wrap the app once in `<MotionConfig reducedMotion="user">` — it auto-disables transform/layout animations while preserving opacity. Branch heavy effects with `useReducedMotion()`. Gate CSS animation with Tailwind `motion-safe:`/`motion-reduce:` (or `@media (prefers-reduced-motion: reduce)`); for GSAP use `gsap.matchMedia()` with `"(prefers-reduced-motion: reduce)"` and clean up on unmount. Avoid parallax, autoplay carousels, and flashing > 3×/sec.

**Putting it together:** define tokens in `@theme` → build components that take `className` and merge via `cn()` → author mobile-first with `dark:` and `@container` → animate with `motion/react` → gate everything behind `MotionConfig reducedMotion="user"`.
