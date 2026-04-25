# Logo & Favicon Prompts

Two assets to produce:

1. **Wordmark** (`CorpusScan`) — typography-only, doesn't really need an image generator. Spec is below.
2. **Icon mark / favicon** — small symbol used as the favicon, app icon, and (optionally) paired with the wordmark in the navbar. Image-generator prompts are below.

Brand context: editorial, restrained, financial. Think Financial Times, Bloomberg Terminal, Stripe. Not consumer SaaS.

Brand colors (use these exact hex values — do not let the model invent colors):
- `#111827` primary (near-black)
- `#374151` secondary (slate)
- `#06B6D4` accent (cyan)
- `#F9FAFB` background (off-white)
- `#8B5CF6` accent 2 (violet — almost never; absent from logo entirely)

---

## 1. Wordmark spec

The wordmark is just typography — generate it in Figma / Tailwind, not via image AI.

```
Text:    CorpusScan
Font:    Inter
Weight:  600 (Semibold)
Color:   #111827
Spacing: tracking-tight (-0.01em)
Case:    Mixed-case as written, single word, no space
```

Optional: the "S" in "Scan" can be `#06B6D4` accent for a subtle two-tone version. Use sparingly — the all-`#111827` version is the default.

---

## 2. Icon mark / favicon — concept

The mark is a stylized **`C`** that doubles as a scanned document edge. Read in two ways at once:

- A bold geometric **C** (for CorpusScan)
- The **left edge of a document** with a horizontal scan line passing through it

Single mark, single color foreground on transparent background. Works at 16×16 (favicon), 32×32 (browser tab), 512×512 (app icon).

---

## 3. Image-generator prompt — primary version

> Use this for Midjourney, DALL-E 3, Ideogram, or Stable Diffusion. Generate 4–8 variations and pick the one that holds up at 16×16.

```
A minimalist app icon for a fintech tool called CorpusScan.

Concept: a bold geometric letter "C" rendered as the left edge of a
stylized document. A single thin horizontal accent line passes
across the middle of the C, suggesting a scan line reading the
document.

Style:
- Flat vector, no gradients, no drop shadows, no 3D, no bevel
- Geometric, precise, monoline construction
- Editorial and restrained — Financial Times, Bloomberg Terminal, Stripe energy
- NOT consumer-app, NOT playful, NOT cartoonish

Composition:
- Centered subject on a square canvas
- Generous negative space around the mark (15-20% padding)
- Subject occupies roughly 60% of the canvas
- Strong silhouette readable at 16x16 pixels

Colors (strict — use only these):
- Foreground "C": #111827 (near-black)
- Accent scan line: #06B6D4 (cyan)
- Background: transparent (or solid #F9FAFB if transparent unavailable)

Output: square, vector-feeling, suitable for export to SVG.
Aspect ratio: 1:1
```

### Negative prompt (for SD-style tools)

```
gradient, drop shadow, 3d, bevel, glow, glossy, metallic, sparkle,
emoji, mascot, character, face, eyes, illustration of a person,
photorealistic, busy, ornate, decorative flourish, multiple colors,
rainbow, neon
```

---

## 4. Alternative concept prompts

If the primary concept doesn't land, try one of these. Keep all the style / color / composition rules from the primary prompt.

### Option B — Stacked text lines

```
Concept: three horizontal bars of decreasing length stacked
vertically (suggesting lines of text in a document), with a single
thin cyan vertical scan line crossing them on the right side.
```

### Option C — Monogram CS

```
Concept: a tight ligature of the letters "C" and "S" interlocking.
The C is solid #111827. The negative space inside the S is filled
with a cyan #06B6D4 horizontal bar suggesting a scan line.
Geometric grotesk construction, similar to Inter or Söhne.
```

### Option D — Document corner with scan beam

```
Concept: the top-left corner of a document, with a folded triangle
detail in the upper right corner of the icon. A single horizontal
cyan line crosses the document near its midline.
```

---

## 5. Favicon export checklist

Once the icon SVG is finalized:

- [ ] Export `favicon.svg` (the master)
- [ ] Export `favicon.ico` containing 16×16, 32×32, 48×48
- [ ] Export `apple-touch-icon.png` at 180×180
- [ ] Export `icon-192.png` and `icon-512.png` for `manifest.webmanifest`
- [ ] Drop into `/frontend/public/`
- [ ] Add to `index.html`:
  ```html
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  <link rel="icon" type="image/x-icon" href="/favicon.ico" />
  <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
  ```

---

## 6. Quality bar

A good CorpusScan favicon should:

- Be recognizable at **16×16** (squint test in the browser tab)
- Use **at most two colors** (`#111827` + `#06B6D4`)
- Have **zero ornamental detail** — every line earns its place
- Look at home next to icons for **Linear, Notion, Stripe, Vercel** — not next to icons for consumer apps
- Hold up on both light and dark browser themes (the `#111827` mark on transparent works for light; consider a `#F9FAFB` inverse variant for dark mode if needed)
