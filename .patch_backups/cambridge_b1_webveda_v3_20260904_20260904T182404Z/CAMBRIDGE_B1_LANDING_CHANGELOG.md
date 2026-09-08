# Cambridge B1 Landing Page — Changelog

## Scope

This update makes Cambridge Upskill/B1 the website's single public product and serves the redesigned landing page directly at `/`. The former `/cambridge-english/`, `/ielts/` and `/uk-interview/` marketing URLs redirect safely to the main homepage so old links do not break. Authentication, the student dashboard, practice and mock-test engines, payment verification, admin, database models, migrations, APIs and configuration files were not intentionally changed.

## Files changed

- `website/views.py` — serves the Cambridge/B1 experience at `/`, redirects former public product URLs to it and removes retired product URLs from the sitemap.
- `website/tests.py` — verifies the new root homepage, canonical URL, safe legacy redirects and Cambridge-only sitemap.
- `templates/website/cambridge_b1_landing.html` — rebuilt bilingual, semantic Cambridge/B1 homepage with a photographic hero and editorial section flow.
- `static/css/cambridge-b1-webveda.css` — completely replaced with the corrective high-fidelity visual system: full-bleed hero, WebVeda-scale type, fewer card surfaces, stronger spatial rhythm, responsive layouts, microinteractions and reduced-motion support.
- `static/js/cambridge-b1-webveda.js` — isolated menu, reveal, sticky-story, parallax, magnetic-button and accessible FAQ behavior.
- `static/images/public/cambridge-b1/b1-hero-studio-v2.webp` — optimized cinematic hero artwork created from the supplied instructor photograph, with dark editorial negative space for readable copy.
- `static/images/public/cambridge-b1/b1-coach-seated.webp` — optimized transparent WebP made from the supplied `IMG_2340.PNG`.
- `static/images/public/cambridge-b1/b1-coach-portrait.webp` — optimized WebP made from the supplied WhatsApp portrait.
- `CAMBRIDGE_B1_LANDING_CHANGELOG.md` — this file.

## Content and UX

- Uses the current Cambridge/B1 source content and current prices: NPR 2,999, NPR 4,999 and NPR 1,999 portal-only.
- Keeps Speaking B1 dominant, with Reading A2, Listening A2 and Writing A1 clearly shown.
- Corrects the earlier small-card/SaaS appearance with one dominant photographic first screen, oversized type, an asymmetric Speaking composition, border-led preparation steps, a large instructor story and a realistic product showcase.
- Adds the preparation loop, authentic student pain points, product-style mock portal, instructor story, active-practice comparison, student journey, truthful trust messaging, pricing, FAQs and final CTA.
- Uses existing named Django routes for login, signup, dashboard, mock tests, learning and payments.
- Removes the three-product chooser from the public entry experience without deleting program data or changing dashboard behavior.
- Adds page-specific SEO, canonical, Open Graph/X metadata, Course schema and FAQ schema.
- Uses Radio Canada Big with Noto Sans Devanagari and responsive `clamp()` typography.
- Includes keyboard focus, accessible navigation/accordion states, fixed image dimensions, lazy loading below the fold and `prefers-reduced-motion` support.

## Validation completed

- Django system check: passed.
- Website test suite: 5 tests passed.
- JavaScript syntax check: passed.
- CSS parse audit: no parse errors.
- Rendered HTML audit: no duplicate IDs, empty links, missing fragment targets or missing `aria-controls` targets.
- Static asset discovery: all new CSS, JavaScript and images found.

## Database

**NO SQL PATCH REQUIRED.**

No model or migration file was changed for this landing-page redesign.
