# Cambridge B1 Landing Page — V8 Changelog

## V8 hero, mock portal and promise refinement

- Rebuilds the desktop hero as a strict split composition: text and the three benefits stay within the left content zone while the supplied instructor cut-out is clipped inside its own right-side visual zone.
- Removes the yellow-marquee/dark “Real Preparation Problems” section requested in the supplied screenshot.
- Replaces the older mock-portal introduction with “Practice The Exam Before You Face The Exam,” the product-style dashboard preview and six portal capability cards from the supplied B1 content.
- Adds a responsive WebVeda-inspired blue “The B1 Ready Promise” section using the supplied authentic commitments: Unlimited Mock Practice, Learn In Your Time and Live Feedback Every Week.
- Deliberately avoids adding WebVeda’s refund, subscription or risk-free claims because those policies were not confirmed for this B1 program.

## V7 responsive CTA and course-detail refinement

- Separates the mobile hero portrait and three preparation benefits into independent vertical zones so the text never overlaps the instructor photograph.
- Refines the desktop hero crop while preserving the instructor-right, copy-left composition.
- Replaces the floating conversion bar with the requested Recorded Lessons, Mock Tests and Weekly Feedback message and Start B1 Preparation action.
- Rebuilds the wide navy conversion banner around “Get Everything You Need for B1 — सबै एकै ठाउँमा।” with the instructor image and the three requested right-side labels.
- Adds a new responsive “Exclusive Cambridge Upskill B1 Preparation” product section with the instructor, Daily live class, four-skill coverage, 500+ questions, AI + Teacher feedback and a keyboard-accessible native accordion.
- Uses mobile-specific compositions for the navy banner and course section rather than shrinking the desktop layouts.

## V6 opening-section correction

- Corrects the desktop hero proportions and guarantees that the mobile instructor cut-out cannot appear on desktop.
- Removes the duplicated instructor from the mobile background by using a dedicated people-free dark editorial treatment behind the centered cut-out.
- Adds the requested WebVeda-style “Message From Your Instructor” section with the second supplied portrait, 7+ Years, 1,000+ Learners, B1 Specialist and Become an Arya Member CTA.
- Adds “THE COMPLETE B1 SYSTEM” immediately afterward with the requested Recorded Lessons, Real Exam Practice and Weekly Feedback content.
- Removes the later duplicate instructor block while leaving the remaining preparation, portal, pricing, FAQ and dashboard-linked content intact.

## V5 hero correction

- Rebuilt only the public header/hero presentation to follow the supplied WebVeda first-screen composition on desktop and mobile.
- Uses Inter 800 for the hero heading and Inter 400 for the supporting line, with Noto Sans Devanagari as the required glyph fallback.
- Uses one proof line, one `B1 सम्भव छ।` heading, one supporting line and one Start Preparation CTA.
- Keeps the instructor on the right on desktop and centers the supplied cut-out photograph below the CTA on mobile.
- Removes the B1/A2/A1 hero level boxes and replaces them with the three requested unboxed captions: Step-by-Step Recorded Course, Real Exam-Style Mock Tests and AI + Personal Feedback.
- Keeps the existing routes and every section below the hero unchanged.

## Scope

This update makes Cambridge Upskill/B1 the website's single public product and serves the redesigned landing page directly at `/`. The former `/cambridge-english/`, `/ielts/` and `/uk-interview/` marketing URLs redirect safely to the main homepage so old links do not break. Authentication, the student dashboard, practice and mock-test engines, payment verification, admin, database models, migrations, APIs and configuration files were not intentionally changed.

## Files changed

- `website/views.py` — serves the Cambridge/B1 experience at `/`, redirects former public product URLs to it and removes retired product URLs from the sitemap.
- `website/tests.py` — verifies the root homepage, bilingual source content, WhatsApp control, removed disclaimer, canonical URL, safe legacy redirects and Cambridge-only sitemap.
- `templates/website/cambridge_b1_landing.html` — expanded bilingual homepage using the complete preparation, package, audience, portal and FAQ content; removes the requested disclaimer wording and adds the floating WhatsApp CTA.
- `static/css/cambridge-b1-webveda.css` — precision visual pass based on measured WebVeda proportions: approximately 76px desktop hero type, 56px section type, 1,090px content width, controlled section spacing, large rounded media surfaces and deliberate mobile scaling.
- `static/js/cambridge-b1-webveda.js` — upgraded motion system with staged hero entry, scroll progress, reveal choreography, working parallax, gentle media drift, active navigation, count-up animation, magnetic CTA and accessible animated FAQ behavior.
- `static/images/public/cambridge-b1/b1-hero-studio-v2.webp` — optimized cinematic hero artwork created from the supplied instructor photograph, with dark editorial negative space for readable copy.
- `static/images/public/cambridge-b1/b1-coach-seated.webp` — optimized transparent WebP made from the supplied `IMG_2340.PNG`.
- `static/images/public/cambridge-b1/b1-coach-portrait.webp` — optimized WebP made from the supplied WhatsApp portrait.
- `CAMBRIDGE_B1_LANDING_CHANGELOG.md` — this file.

## Content and UX

- Re-art-directs the mobile first viewport instead of merely stacking desktop content: centered bilingual headline, one dominant CTA, a purpose-built instructor composition and a three-benefit level strip inspired by the supplied WebVeda mobile references.
- Keeps Login visible beside a compact square menu on mobile and matches the reference's clean white 70–72px navigation proportion.
- Reduces mobile section padding, improves Devanagari line-height, centers key narrative headings and keeps body copy at readable 15–18px sizes.
- Adds a large mid-page conversion banner with instructor imagery, floating skill labels, Start Preparation and WhatsApp actions.
- Adds a responsive sticky conversion bar that appears only after the hero and disappears before the final CTA; the WhatsApp button moves above it automatically.
- Converts pricing and audience blocks into touch-friendly horizontal snap rails on mobile, with the recommended Complete plan shown first.
- Re-composes the portal preview into a compact two-column mobile product view and reduces excessive card height throughout the page.
- Uses the current Cambridge/B1 source content and current prices: NPR 2,999, NPR 4,999 and NPR 1,999 portal-only.
- Keeps Speaking B1 dominant, with Reading A2, Listening A2 and Writing A1 clearly shown.
- Corrects the earlier scale mismatch by matching WebVeda's measured type hierarchy and narrower editorial content width instead of using oversized 100px+ headings throughout.
- Restores the detailed Nepali/English source content: daily two-hour live learning, speaking practice, recorded lessons, notes/templates, 500+ complete-plan questions, feedback, caregiver audience, portal access policy, estimated levels, previous scores and progress tracking.
- Adds the preparation loop, authentic student pain points, product-style mock portal, instructor story, active-practice comparison, eight-step student journey, audience section, learning-area showcase, detailed pricing, seven FAQs and final CTA.
- Adds a right-side WhatsApp button with the configured site WhatsApp URL and a compact icon-only mobile treatment.
- Removes the requested long Cambridge independence/disclaimer text from visible content, FAQ data and structured metadata without changing any functional route.
- Uses existing named Django routes for login, signup, dashboard, mock tests, learning and payments.
- Removes the three-product chooser from the public entry experience without deleting program data or changing dashboard behavior.
- Adds page-specific SEO, canonical, Open Graph/X metadata, Course schema and FAQ schema.
- Uses Inter for the hero, Radio Canada Big for the remaining editorial system, Noto Sans Devanagari for Nepali glyphs and responsive `clamp()` typography.
- Includes keyboard focus, accessible navigation/accordion states, fixed image dimensions, lazy loading below the fold and `prefers-reduced-motion` support.

## Validation completed

- Django system check: passed.
- Website test suite: 5 tests passed.
- JavaScript syntax check: passed.
- CSS parse audit: no parse errors.
- Rendered HTML audit: no duplicate IDs, empty links, missing fragment targets or missing `aria-controls` targets.
- Static asset discovery: all new CSS, JavaScript and images found.
- Safe installer tested from the previous V3 landing-page state with an exact output comparison.

## Database

**NO SQL PATCH REQUIRED.**

No model or migration file was changed for this landing-page redesign.
