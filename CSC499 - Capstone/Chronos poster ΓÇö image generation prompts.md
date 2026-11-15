# Chronos — image-generation prompts

**Read this first.** Image models cannot render legible body text at A1, and they cannot
produce a scannable QR code. Everything they generate is a *picture of letters*, not type.
So use them for the **visual layer only** — background motif, hero graphic, logo mark — and
keep all real text in the vector PDF. The finished `Chronos D-Day Poster A1.pdf` already has
the type, tables, charts and QR slot; these prompts are for decoration you can place behind
or beside that content.

---

## Prompt A — background motif (the one to use)

> A minimal abstract background for an academic research poster, portrait A1 proportions.
> A faint weekly timetable grid — five vertical day columns crossed by nine horizontal hour
> rows — drawn in very light grey hairlines on a clean white background. A small number of
> grid cells are filled as soft rounded rectangles in muted indigo (#4F46E5) and teal
> (#0891B2), scattered asymmetrically and concentrated toward the upper right, like a
> partially solved schedule. Large areas of empty white space, especially the left two
> thirds. Extremely subtle, low contrast, nothing above 12% opacity. Flat vector style, no
> gradients, no shadows, no texture, no 3D. Swiss international typographic design
> sensibility. No text, no letters, no numbers, no icons, no logos, no people.

**Negative prompt:** `text, letters, numbers, words, typography, watermark, logo, icons,
people, hands, calendar illustration, clipart, 3D render, drop shadow, gradient mesh,
busy pattern, dark background, saturated colour, photo`

**Settings:** aspect ratio 2:3 (or 59:84 if supported) · highest resolution available ·
upscale to at least 7000 × 9900 px before placing at A1.

**How to use it:** place at 8–12% opacity behind the poster, or crop a band of it for the
header strip only. Do not let it run under the charts or the tables.

---

## Prompt B — hero graphic (optional, for the top-right of the header)

> An abstract illustration of constraint satisfaction, flat vector, white background.
> A dense field of small pale grey dots arranged in a regular 3D-looking lattice, most of
> them faded to near-invisible, with a single connected path of about eight solid indigo
> (#4F46E5) dots threading through the lattice and joined by thin straight lines. The
> impression is one valid solution found inside an enormous space of possibilities.
> Generous white space. Flat, geometric, no gradients, no shadows, no perspective tricks.
> Clean academic conference aesthetic. No text, no labels, no arrows.

**Negative prompt:** `text, letters, numbers, labels, arrows, logo, watermark, 3D render,
neon, glow, dark background, photo, people`

**Settings:** aspect ratio 1:1 · transparent background if supported, otherwise pure white.

---

## Prompt C — project mark (doubles as the sticker artwork later)

> A minimal flat vector logo mark for a university timetabling system called Chronos.
> A square badge with generously rounded corners. Inside, a simple 3 × 3 grid of squares
> where one square is filled solid indigo (#4F46E5) and the rest are thin indigo outlines —
> suggesting a single class placed in a schedule. Perfectly symmetrical, geometric,
> monoline, two colours only (indigo on white). No text, no lettering, no gradients,
> no shadows, no mascot. Designed to stay legible at 2 cm.

**Negative prompt:** `text, letters, wordmark, gradient, shadow, 3D, bevel, mascot,
character, photo, realistic, complex detail`

**Settings:** aspect ratio 1:1 · request SVG if the tool offers it, otherwise ≥2000 px PNG
on transparent background.

---

## If you want a full-poster layout mockup instead

Useful only as a *design reference* to look at — never as the printed artefact, because
every word in it will be gibberish.

> A clean academic research poster layout, portrait A1, white background, three-column grid.
> A tall header band with a very large serif title and a thin horizontal rule beneath it.
> Three columns of content blocks separated by generous white gutters: body text blocks,
> two simple data tables with light grey header rows, a line chart, a horizontal bar chart,
> a boxed flow diagram of three stacked rounded rectangles joined by downward arrows, and
> four statistic tiles with very large numerals. A footer band with a square QR code at the
> far right. Restrained palette — black text, one indigo accent (#4F46E5), one teal accent
> (#0891B2), light grey rules. Swiss international style, lots of air, no decoration.

**Negative prompt:** `photo, 3D, gradient, dark background, neon, busy, cluttered,
saturated colour, drop shadow, stock photography, people`
