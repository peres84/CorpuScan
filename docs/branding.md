# CorpusScan — Branding

Brand voice and visual tokens. Frontend respects these strictly. Generated motion graphics (Hera Agent output) also use these colors.

---

## Voice

- **Editorial, not marketing.** Sentences, not slogans.
- **Restrained.** No emojis. No exclamation points. No "Wow", "Magic", "AI-powered".
- **Confident and concrete.** Talk about reports, scenes, narration, signal — not abstract benefits.
- **Short.** A CFO has 90 seconds. Match that energy.

### Examples

| Good                                                  | Bad                                            |
| ----------------------------------------------------- | ---------------------------------------------- |
| Turn quarterly reports into 2-minute video briefings. | Revolutionize your reporting workflow with AI! |
| Extracting key facts                                  | AI is finding insights for you...              |
| For investor relations, finance, and strategy teams.  | Built for the modern enterprise!               |

---

## Color tokens

| Role        | Token        | Hex       | Where it appears                                              |
| ----------- | ------------ | --------- | ------------------------------------------------------------- |
| Primary     | `primary`    | `#111827` | Headlines, body text, dark surfaces                           |
| Secondary   | `secondary`  | `#374151` | Sub-headings, muted text, secondary buttons                   |
| Accent      | `accent`     | `#06B6D4` | CTAs, links, progress bars, active states (cyan)              |
| Accent 2    | `accent2`    | `#8B5CF6` | Highlights only — **sparingly**, never as primary CTA (violet)|
| Background  | `background` | `#F9FAFB` | Page background                                               |
| Surface     | `surface`    | `#FFFFFF` | Cards, modals, navbar                                         |
| Text        | `text`       | `#111827` | Default text color (same as primary)                          |

### Tailwind config

```ts
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        primary:    "#111827",
        secondary:  "#374151",
        accent:     "#06B6D4",
        accent2:    "#8B5CF6",
        background: "#F9FAFB",
        surface:    "#FFFFFF",
      },
    },
  },
};
```

### Usage rules

- Primary CTA buttons: **always** `accent` background with white text.
- Secondary CTA: outline (`border border-gray-300`, primary text).
- `accent2` (violet) is only for highlights — a single chart accent, a hover sparkle, a notification dot. Never as a button background. Never side-by-side with `accent` in the same component.
- Errors: `bg-red-50 / border-red-200 / text-red-900`. Don't add brand red.

---

## Typography

| Use                        | Font            | Loaded from         |
| -------------------------- | --------------- | ------------------- |
| Display, headings, body    | **Inter**       | Google Fonts        |
| Numerics, data, code       | **JetBrains Mono** | Google Fonts     |

### Weights used

400 (body) · 500 (UI) · 600 (subhead) · 700 (display)

### Scale (Tailwind classes)

| Element           | Class                       |
| ----------------- | --------------------------- |
| Hero headline     | `text-5xl md:text-6xl font-bold` |
| Section heading   | `text-3xl font-semibold`    |
| Card heading      | `text-2xl font-semibold`    |
| Body              | `text-base text-secondary`  |
| Eyebrow           | `text-xs uppercase tracking-wider font-semibold text-accent` |
| Numerics          | `font-mono`                 |

---

## Spacing & shapes

- Generous whitespace — sections `py-16` to `py-24`, cards `p-6` to `p-8`
- Border radius: `rounded-lg` (8px) default · `rounded-2xl` (16px) for hero / large cards · `rounded-full` for pills and progress bars
- Shadows: `shadow-sm` only — no heavy drop shadows
- Borders: `border border-gray-200` for low-emphasis dividers

---

## Logo

Text-only wordmark: **CorpusScan**, `font-semibold`, primary color. No icon mark for MVP.

---

## Motion graphics palette (Hera output)

The Hera Agent must use these exact hex values in its generated animation specs:

```
text:        #111827
secondary:   #374151
accent:      #06B6D4
background:  #F9FAFB
```

- Solid backgrounds only — no gradients
- One key fact per sentence — don't visualize every word
- Allowed primitives: kinetic typography, number count-ups, simple bar / line charts, callout boxes
- Animation register: editorial. Think FT Alphaville cards, not TikTok captions.
