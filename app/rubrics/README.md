# Evaluation Rubrics — Master Index

This directory contains evaluation rubrics for generated marketing images.

## How to Use

Each rubric is a checklist. Feed the rubric + the generated image to a vision model
(e.g., GPT-4o, Gemini Flash) and ask it to evaluate the image point by point.

The gate checks are PASS/FAIL — if the gate check fails, the image is an automatic
FAIL regardless of other scores. This prevents style bleed (e.g., pop-art dots in
a comic-book image).

## Rubric Files

### Style Rubrics
- [pop-art.md](pop-art.md) — Roy Lichtenstein 1960s pop art (Ben-Day dots)
- [comic-book.md](comic-book.md) — 1940s Golden-Age comic (flat solid color)
- [manga.md](manga.md) — Black-and-white manga (screentone, no color)
- [dragon-ball-z.md](dragon-ball-z.md) — DBZ / Toriyama anime (cel-shaded, spiky hair)
- [technical-blueprint.md](technical-blueprint.md) — Blueprint/drafting (white on blue)
- [8bit-video-game.md](8bit-video-game.md) — NES pixel art (visible pixels)

### Layout Rubrics
- [layouts.md](layouts.md) — Format-specific checks for all 5 layouts

## Scoring System

Each rubric has 12 items across 4 categories:
- **Style Fidelity (35%)** — 4 items, including one PASS/FAIL gate check
- **Composition (30%)** — 3 items
- **Technical Quality (20%)** — 3 items
- **Content Accuracy (15%)** — 2 items

Scoring: 0 = missing/wrong, 0.5 = partially correct, 1 = present/correct
- **PASS:** ≥ 9/12 AND gate check passed
- **REVISE:** 6-8/12 or gate passed but borderline
- **FAIL:** < 6/12 or gate check failed

## Evaluation Prompt Template

```
You are evaluating an AI-generated image against a quality rubric.

RUBRIC:
[PASTE RUBRIC HERE]

Evaluate the attached image and provide:
1. STYLE FIDELITY score (1-10) with justification
2. COMPOSITION score (1-10) with justification
3. TECHNICAL QUALITY score (1-10) with justification
4. CONTENT ACCURACY score (1-10) with justification
5. OVERALL score (1-10)
6. TOP 3 STRENGTHS
7. TOP 3 ISSUES
8. VERDICT: PASS / FAIL / REVISE
```

## Multi-Image Evaluation

For consistency checks (e.g., "same character across multiple panels"):
- Send all images to the vision model in a single request
- Add: "These [N] images should depict the same character(s). Evaluate consistency
  of appearance, costume, proportions, and facial features across all images."
- Score consistency separately: 1-10 with justification