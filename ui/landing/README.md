# Landing — `scutum.dev`

Static marketing site served by nginx (see `Dockerfile` + `nginx.conf`).
Single-file HTML by design — no build step, no Vite, no React on the public
surface. The chat product (`chat.scutum.dev`) is the dynamic surface; the
marketing site stays simple so it ships in 24KB total and renders without
JavaScript for the parts that matter (everything except the menu toggle and
the copy-to-clipboard buttons).

## Layout

```
index.html              # the landing page (this file is what nginx serves at /)
llms.txt                # crawler-facing description of what Scutum is
sitemap.xml             # surface map for Google + Bing
robots.txt              # AI-bot signals (search=yes, ai-input=yes, ai-train=no)
nginx.conf              # routing for / + /docs/ + /try/ + /v1/ + /release/
Dockerfile              # builds the OCI image deployed on the OCI free-tier VM

scutum-mark.svg         # logo (favicon + apple-touch-icon)
scutum-wordmark.svg     # logo wordmark
og-image.png            # 1200×630 OpenGraph card

privacy/, terms/, dpa/  # legal subroutes (separate index.html each)
changelog/              # latest customer-visible changelog
try/                    # /try signup form (Cloudflare Turnstile + the
                        # trial-signup admin-api endpoint)
release/                # versioned mirror of install.sh + scutum CLI +
                        # docker-compose.yaml + license public key
                        # (the repo is private; raw.githubusercontent.com
                        # 404s for unauth, so we serve from here)
```

## Editing copy

All page text lives in `index.html` between the `<!-- ===== SECTION ===== -->`
banner comments. Sections in document order:

1. `<!-- ===== TOP NAV ===== -->`
2. `<!-- ===== HERO ===== -->`
3. `<!-- ===== TRUST STRIP ===== -->`
4. `<!-- ===== THREE FEATURE BLOCKS ===== -->`
5. `<!-- ===== CODE PROOF ===== -->`
6. `<!-- ===== LIVE DEMO ===== -->`
7. `<!-- ===== WHY SELF-HOSTED ===== -->`
8. `<!-- ===== CAPABILITIES ===== -->`
9. `<!-- ===== PRICING ===== -->`
10. `<!-- ===== FINAL CTA ===== -->`
11. `<!-- ===== FOOTER ===== -->`

To add a new section: copy the structure of an existing one (each lives
inside `<section><div class="container">…</div></section>`), update the
`id` if you want a deep-link anchor, and add the same `id` to `sitemap.xml`
if it should be indexed as its own URL.

## Design system

All design tokens are CSS variables in the `:root { ... }` block at the top
of `index.html` `<style>`. To change the palette, typography, or spacing
scale, edit those variables only; the components below all reference them
by name.

Token groups:

- **Colors** — `--bg-{primary,secondary,tertiary}`, `--border`,
  `--text-{primary,secondary,tertiary}`, `--accent`, `--accent-hover`,
  `--success`.
- **Fonts** — `--font-sans` (Inter), `--font-mono` (JetBrains Mono).
- **Layout** — `--content-max` (1280px), `--bleed-max` (1440px),
  `--pad-x-{mobile,tablet,desk}`, `--section-y-{mobile,desk}`.

Reusable component classes:

- `.btn` + `.btn-primary` / `.btn-secondary`
- `.card` (dark surface, hairline border, 16px radius, 32px padding)
- `.terminal` (monospaced shell with `.prompt` and `.copy` button) —
  add a `data-copy="..."` attribute to wire up clipboard
- `.container` (centered, max-width, responsive horizontal padding)
- Heading classes follow `h1` / `h2` / `h3`; helper utility classes:
  `.body-lg`, `.body`, `.small`, `.label`, `.muted`, `.subtle`

## SEO metadata

Single source of truth lives in the `<head>` of `index.html`. To change
title / description / OG card on the landing surface, edit the existing
`<meta>` tags. The Schema.org Organization JSON-LD is in a `<script
type="application/ld+json">` block in `<head>`; keep `name`, `url`,
`logo`, `description`, and the `sameAs` array consistent with what the
footer displays.

For the chat product (`chat.scutum.dev`), SEO and the SoftwareApplication
JSON-LD live in `ui/chat/app/layout.tsx` — that's a separate Next.js
deploy, edited and shipped via `.github/workflows/deploy-chat.yml`.

## Placeholder assets to replace before production

These are referenced by the new landing but don't exist yet on the volume:

| File | Purpose | Spec |
|---|---|---|
| `og-chat.jpg` | OpenGraph card for chat.scutum.dev — used by Twitter/Slack/LinkedIn previews | 1200×630, dark theme, Scutum Research wordmark + a tiny "AI search where the answer is software" tagline |
| `demo-sprint-planner.mp4` | Hero video in the "See Scutum running. Live." section. Looped, autoplay, muted, `<= 8MB` for fast first-paint | ~10–15s screen-grab of asking chat.scutum.dev for the sprint-planner artifact, sliders moving the chart in real time, 1080p H.264 |
| `demo-sprint-planner-poster.jpg` | Poster shown before the video plays / on browsers that block autoplay | First frame of `demo-sprint-planner.mp4`, 1100×620 |

Until those land, the video falls back to an empty space (browser shows
poster `:not-found` quietly), and OG cards on chat.scutum.dev show no
image. Both are graceful degradations — no broken page.

`og-image.png` is the existing OG card for the gateway landing and stays
as-is.

## Local preview

```bash
cd ui/landing
python3 -m http.server 8000      # or any static server
open http://localhost:8000/
```

The terminal copy-button only works over `https://` or on `localhost`
(browser security policy on `navigator.clipboard.writeText`); fallback
is `document.execCommand('copy')` via a hidden textarea.

## Deploy path

The landing site is part of the `landing-ui` docker-compose service and
deploys to the OCI free-tier ARM VM via `scripts/deploy-oci.sh`. Static
content is bundled into the image (not a volume mount), so the OCI VM
serves whatever was built into the most recent `landing-ui` image.

## Search Console submission

After production deploy, register **both** properties separately in
Google Search Console (and Bing Webmaster Tools):

1. `https://scutum.dev/`  (DNS-verified or HTML-tag-verified)
2. `https://chat.scutum.dev/`  (separate property — different subdomain
   means different ownership boundary)

Submit the sitemap (`https://scutum.dev/sitemap.xml`) on the parent
property; it includes both surfaces.

## Constraints baked into the current design

The page deliberately omits things the brief said not to add: no
testimonials (no real customers yet), no metric counters, no GitHub
link, no MIT/license claims, no light-mode toggle, no animations beyond
hover states and the single hero radial. Don't add them back without an
explicit ask.
