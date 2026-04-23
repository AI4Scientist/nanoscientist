# GPT Image 2 Prompt Craft

Cross-cutting principles distilled from 56 community prompts. This is the checklist to run through before shipping any prompt back to the user.

## 1. Exact text → in quotes

GPT Image 2 renders typography well, but only when the text is marked as literal.

Weak:
> "Create a tea poster with the brand name and promo copy."

Strong:
> Create a 3:4 tea poster. Display the exact Chinese copy:
> "山川茶事" / "冷泡系列" / "新品上市" / "中杯 16 元" / "大杯 19 元"

Rules:
- Wrap every piece of displayed text in `"…"`.
- For Chinese, specify 简体 / 繁體 if it matters; keep the user's characters verbatim, never paraphrase.
- Separate distinct text blocks with `/` or newlines — GPT Image treats them as separate typographic elements.
- For fine print, label it: `Fine print: "图片仅供参考，请以门店实际售卖为准"`.
- For dense text screens (menus, exam papers, textbook pages), provide the full content OR upload a real reference image.

## 2. Aspect ratio before subject

State dimensions first so the model allocates composition correctly:
- `3:4 vertical poster for …` (tall posters, beauty, tea, skincare).
- `9:16 aspect ratio, generate a screenshot of …` (mobile app UI, livestream frames).
- `Create a single image containing a 10×10 grid of …` (when structure matters, state the grid before the content).

Default (no ratio) = square. Fine for crowd photos, headshots, character grids.

## 3. Camera & shot language unlocks photorealism

The strongest unlock for photorealism is naming the capture context, not the adjectives:

| Phrase | What it does |
|--------|--------------|
| `RAW, unprocessed, full iPhone camera quality` | Strips AI polish, adds grain and realism. |
| `amateur iPhone photo` | Casual tourist / spectator feel, soft imperfection. |
| `shot from the crowd at a distance` | Real-event perspective, not studio. |
| `close-up shot taken from a stationary 4k monitor` | Video-game UI fidelity (for gameplay screenshots). |
| `shot from slightly above, natural daylight from a window, no flash` | Notebook / product flatlay. |

Stacking more than two of these is counter-productive — pick one dominant frame.

## 4. Scene density > scene idea

Vague: "A convenience store at night."

Dense:
> …freezer stickers, promotional posters, trash cans, entrance mats, glass reflections, shared bikes on roadside, water droplets from drink bottles on ground.

Rule of thumb: **3–8 concrete nouns** named, not adjectives. Adjectives pile up into slop; nouns localise the scene to a specific place and time of day.

## 5. Style anchor — name the movement

Avoid "professional", "beautiful", "high quality". Anchor to a real aesthetic:
- `1980s propaganda poster`
- `New Chinese visual style, light-luxury and restrained`
- `Gongbi painting style`
- `national museum exhibition board`
- `Josef Albers' interaction meets data visualization`
- `Polish poster energy meets Le Corbusier`

If you cannot name the movement, you have not committed yet.

## 6. Reference-based generation

When the user uploads an image, three phrases lift fidelity:
- `maintain composition and image details consistently`
- `same pet, absolutely consistent in appearance and coloring`
- `in the original positions`

For character consistency across a grid:
> Her face shape, hairstyle, and clothing must remain highly consistent across all panels.

Use `scripts/generate.py --edit ref.png` to route to `/v1/images/edits` instead of `/v1/images/generations`.

## 7. Dense Chinese text stress test

GPT Image 2 is state-of-the-art at dense Simplified Chinese. Rules for max fidelity:
- Provide every character the user wants rendered; no ellipses.
- Use explicit layout labels: `Chinese lead lines annotating key components`, `horizontal category tabs below the search area`.
- Spell out the constraint: `All text must be in Simplified Chinese, clear, neat, and readable, without garbled characters, typos, English, or pinyin`.
- For layout-heavy outputs (exam papers, restaurant menus, textbook pages, almanacs), upload a real photo as reference — it doubles fidelity.

## 8. Negation for strong priors

The repo's strongest prompts include explicit **what-not-to-do** lines:

> Avoid: poster feel, studio portrait feel, e-commerce feel, anime feel, cosplay feel, random annotations, incorrect structures, blurry text, fake materials, excessive decoration.

> Do not default to common containers such as bottles, hourglasses, glass domes, or pocket watches.

Use negation when the model has a strong default prior you want to break (e.g., posters always getting a "framed" feel, characters always getting an anime face).

## 9. The "three glances" test

For premium narrative posters, the top community prompts specify what each glance should reveal:

> First glance: strong theme recognition and a memorable silhouette.
> Second glance: a complete narrative world.
> Third glance: depth and aftertaste on close inspection.

This tells GPT Image 2 to allocate detail across scales — macro composition, midground storytelling, micro texture.

## 10. Promotional hierarchy for commercial posters

Tea, skincare, e-commerce posters work best when the prompt explicitly lists the hierarchy:
- Product name (largest)
- Claim / tagline
- SKU / variants
- Price tiers (中杯 / 大杯, Limited-time price)
- Gift list modules (赠 X, 赠 Y)
- Fine print

Without hierarchy, GPT Image 2 treats all text as equally sized, producing flat "ad-banner" feel.

## 11. Attribution — keep source tags

Every pattern in `gallery.md` retains `Source: @handle`. When adapting a pattern, keep the attribution as a trailing line (in a comment or caption). It doubles as a debug trace — the original X/Twitter thread usually shows the exact failure modes the prompt was engineered to fix.

## 12. Safety & copyright notes

- Many community patterns explicitly invoke real people (politicians, CEOs, celebrities). OpenAI's usage policy disallows generating likenesses of non-public figures and sexual/violent content involving any real person. Flag this to the caller if a request clearly crosses.
- Brand logos (KFC, Apple, Taobao, GTA, etc.) appear across the gallery. Commercial reuse of such outputs is the caller's legal responsibility, not this skill's.
- For multimodal-safety research (jailbreak probes, vision attacks, adversarial typography), this skill is a legitimate prompt source. Preserve the `Source:` tags in any research paper supplement so attributions stay intact.
