# Video sources catalog

The app does **not** host or scrape surgical videos. It generates **outbound search links** to 46 platforms where surgeons already find operative content.

## How links are built

For each selected term and each applicable source:

1. Pick display text in the active UI language (`term_translations` or fallback).
2. Append locale-specific suffixes (`surgery`, `chirurgie`, `operative video`, …).
3. URL-encode into the source's `base_url` template (`{query}` placeholder).
4. Filter sources by `language` (`en`, `ro`, or `multi`).

API-tier sources: **YouTube** and **Vimeo** work without API keys by default (Piped/Invidious + public Vimeo search/oEmbed); optional `YOUTUBE_API_KEY` / `VIMEO_TOKEN` improve reliability. **PubMed** uses NCBI E-utilities (no key; set `NCBI_CONTACT_EMAIL`). Results are cached in `video_results` and shown with thumbnails; YouTube/Vimeo support in-page embed playback.

## Tier 1 — Inline results (Phase 2)

| Source | Discovery | Playback | Keys |
|--------|-----------|----------|------|
| YouTube | Piped/Invidious (default) or Data API v3 | `youtube-nocookie.com/embed` | Optional `YOUTUBE_API_KEY` |
| PubMed / PMC | E-utilities esearch + esummary | Article link | `NCBI_CONTACT_EMAIL` |
| Vimeo | Public search + oEmbed (default) or Vimeo API | Vimeo embed | Optional `VIMEO_TOKEN` |

## Tier 2 — English platforms (search links)

| Source | Specialty focus |
|--------|-----------------|
| CSurgeries | Multi-specialty, peer-reviewed |
| JOMI | Incision-to-closure operative videos |
| MEDtube | Large clinical video community |
| GIBLIB | Academic lectures and cases |
| WebSurg (IRCAD) | Laparoscopic / robotic MIS |
| SCORE Portal | Resident education (auth) |
| Incision / Touch Surgery | Training modules |
| Google Video | Broad fallback |
| MMCTS / EACTS | Cardiothoracic |
| CTSNet | Thoracic |
| Annals CTS | Cardiothoracic cases |
| SAGES | GI / endoscopic |
| AAOS Video Theater | Orthopaedics (auth for some) |
| AO Surgery Reference | Trauma / ortho |
| Orthobullets | Orthopaedic education |
| EyeRounds / EyeTube | Ophthalmology |
| AANS | Neurosurgery |
| SVS | Vascular |
| EAU | Urology |
| ASMBS | Bariatric |
| SSAT | GI surgery |
| AHPBA | HPB |
| ACS Multimedia | General surgery |
| Toronto Video Atlas | Multi-specialty atlas |
| NEJM / Lancet / BMJ | Academic multimedia |
| Cleveland Clinic / Mayo / Hopkins / Stanford YouTube | Institutional channels |
| NHS e-LfH | UK e-learning |

## Tier 3 — Romanian platforms

| Source | Notes |
|--------|-------|
| YouTube (RO) | Adds `chirurgie` / `operatie` query hints |
| icd10.ro | Terminology reference (not video) |
| MedHug | Romanian code lookup |
| Spital Pelican | Hospital education site search |
| SANADOR | YouTube channel search |
| SNCh | National surgical society |
| MEDSkill Center | Surgical skills courses |
| rezidentiat-medicina.ro | Resident preparation |
| Vimeo (RO) | Site-restricted search |

## Tier 4 — Research references

| Source | Notes |
|--------|-------|
| AVOS (BIDMC) | ~2,000 annotated open-surgery YouTube IDs |
| Surch corpus | Robotic prostatectomy research videos |

## Ethics

- Links open in a new tab (`rel="noopener"`).
- Sources marked `requires_auth=1` show a login warning.
- No endorsement — users must verify clinical appropriateness.
- Respect each platform's Terms of Service; do not automate scraping of gated content.

## Adding a source

Edit `scripts/seed_video_sources.py` and re-run:

```bash
python scripts/seed_video_sources.py
```

Each tuple: `(name, slug, tier, language, specialty, base_url, requires_auth, notes)`.
