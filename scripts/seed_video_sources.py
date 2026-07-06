#!/usr/bin/env python3
"""Seed 40+ surgical video source platforms with search URL templates."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import db_session, init_db, log_import

VIDEO_SOURCES = [
    # Tier 1 — API
    ("YouTube", "youtube", "api", "multi", None,
     "https://www.youtube.com/results?search_query={query}", 0,
     "Primary video index; Phase 2 uses YouTube Data API v3 when key is set."),
    ("PubMed / PMC", "pubmed", "api", "en", None,
     "https://pubmed.ncbi.nlm.nih.gov/?term={query}+surgery+video", 0,
     "Articles with surgical video supplements."),
    ("Vimeo", "vimeo", "api", "multi", None,
     "https://vimeo.com/search?q={query}", 0,
     "Academic and institutional surgical channels."),
    # Tier 2 — General EN
    ("CSurgeries", "csurgeries", "search_link", "en", None,
     "https://csurgeries.com/video/?s={query}", 0, "Peer-reviewed surgical videos."),
    ("JOMI", "jomi", "search_link", "en", None,
     "https://jomi.com/?s={query}", 0, "Journal of Medical Insight operative videos."),
    ("MEDtube", "medtube", "search_link", "en", None,
     "https://medtube.net/search?q={query}", 0, "Clinical video community."),
    ("GIBLIB", "giblib", "search_link", "en", None,
     "https://www.giblib.com/search?q={query}", 0, "Academic surgical lectures and cases."),
    ("WebSurg (IRCAD)", "websurg", "search_link", "en", "laparoscopic",
     "https://www.websurg.com/search?q={query}", 0, "Minimally invasive surgery library."),
    ("SCORE Portal", "score", "search_link", "en", "general",
     "https://portal.surgicalcore.org/search.aspx?q={query}&f_type=Videos", 1,
     "Resident education; subscription may be required."),
    ("Incision / Touch Surgery", "incision", "search_link", "en", None,
     "https://www.incision.care/search?query={query}", 0, "Surgical training platform."),
    ("Google Video", "google_video", "search_link", "multi", None,
     "https://www.google.com/search?tbm=vid&q={query}", 0, "Broad video search fallback."),
    # Specialty societies EN
    ("MMCTS / EACTS", "mmcts", "search_link", "en", "cardiothoracic",
     "https://mmcts.org/?s={query}", 0, "Cardiothoracic surgical tutorials."),
    ("CTSNet", "ctsnet", "search_link", "en", "cardiothoracic",
     "https://www.ctsnet.org/search?search={query}", 0, "Thoracic surgery videos."),
    ("Annals CTS", "annals_cts", "search_link", "en", "cardiothoracic",
     "https://www.annalscts.com/search?q={query}", 0, "Cardiothoracic case videos."),
    ("SAGES", "sages", "search_link", "en", "gi",
     "https://www.sages.org/?s={query}", 0, "GI and endoscopic surgery."),
    ("AAOS Video Theater", "aaos", "search_link", "en", "orthopaedic",
     "https://www.aaos.org/search/?searchText={query}", 1, "Orthopaedic videos; member access for some."),
    ("AO Surgery Reference", "ao_foundation", "search_link", "en", "orthopaedic",
     "https://surgeryreference.aofoundation.org/search?q={query}", 0, "Trauma and orthopaedic techniques."),
    ("Orthobullets", "orthobullets", "search_link", "en", "orthopaedic",
     "https://www.orthobullets.com/search?q={query}", 0, "Orthopaedic education."),
    ("EyeRounds / EyeTube", "eyerounds", "search_link", "en", "ophthalmology",
     "https://webeye.ophth.uiowa.edu/eyeforum/?s={query}", 0, "Ophthalmic surgery videos."),
    ("AANS", "aans", "search_link", "en", "neurosurgery",
     "https://www.aans.org/search?q={query}", 0, "Neurosurgery resources."),
    ("SVS", "svs", "search_link", "en", "vascular",
     "https://vascular.org/search?q={query}", 0, "Vascular surgery society."),
    ("EAU", "eau", "search_link", "en", "urology",
     "https://uroweb.org/search?q={query}", 0, "Urology education."),
    ("ASMBS", "asmbs", "search_link", "en", "bariatric",
     "https://asmbs.org/?s={query}", 0, "Bariatric surgery."),
    ("SSAT", "ssat", "search_link", "en", "gi",
     "https://www.ssat.com/?s={query}", 0, "GI surgery society."),
    ("AHPBA", "ahpba", "search_link", "en", "hpb",
     "https://www.ahpba.org/?s={query}", 0, "Hepatopancreatobiliary surgery."),
    ("ACS Multimedia", "acs", "search_link", "en", "general",
     "https://www.facs.org/search?q={query}", 0, "American College of Surgeons."),
    ("Toronto Video Atlas", "tvasurg", "search_link", "en", None,
     "https://tvasurg.ca/?s={query}", 0, "3D-enhanced surgical atlas."),
    ("NEJM Multimedia", "nejm", "search_link", "en", None,
     "https://www.nejm.org/search?q={query}", 0, "Academic case multimedia."),
    ("The Lancet", "lancet", "search_link", "en", None,
     "https://www.thelancet.com/action/doSearch?AllField={query}", 0, "Academic publications."),
    ("BMJ", "bmj", "search_link", "en", None,
     "https://www.bmj.com/search?q={query}", 0, "BMJ surgical content."),
    # Institutional YouTube templates
    ("Cleveland Clinic (YouTube)", "cleveland_clinic", "search_link", "en", None,
     "https://www.youtube.com/results?search_query={query}+site%3Ayoutube.com%2Fc%2FClevelandClinic+surgery", 0, None),
    ("Mayo Clinic (YouTube)", "mayo_clinic", "search_link", "en", None,
     "https://www.youtube.com/results?search_query={query}+site%3Ayoutube.com%2Fuser%2FMayoClinic", 0, None),
    ("Johns Hopkins (YouTube)", "hopkins", "search_link", "en", None,
     "https://www.youtube.com/results?search_query={query}+site%3Ayoutube.com%2Fuser%2FJohnsHopkinsMedicine+surgery", 0, None),
    ("Stanford Medicine (YouTube)", "stanford", "search_link", "en", None,
     "https://www.youtube.com/results?search_query={query}+site%3Ayoutube.com%2Fc%2FStanfordHealth+surgery", 0, None),
    ("NHS e-LfH", "nhs_elfh", "search_link", "en", None,
     "https://www.e-lfh.org.uk/search/?q={query}", 0, "UK healthcare e-learning."),
    # Romanian sources
    ("YouTube (RO)", "youtube_ro", "search_link", "ro", None,
     "https://www.youtube.com/results?search_query={query}", 0,
     "Romanian surgery video search; query suffix added automatically."),
    ("icd10.ro", "icd10_ro", "search_link", "ro", None,
     "https://www.icd10.ro/cauta.php?q={query}", 0, "Romanian ICD terminology reference."),
    ("MedHug", "medhug", "search_link", "ro", None,
     "https://medhug.ro/medical-codes?q={query}", 0, "Romanian medical code lookup."),
    ("Spital Pelican", "pelican", "search_link", "ro", None,
     "https://www.google.com/search?q=site%3Aspitalpelican.ro+{query}+video", 0, "Romanian hospital education."),
    ("SANADOR", "sanador", "search_link", "ro", None,
     "https://www.youtube.com/results?search_query={query}+SANADOR+chirurgie", 0, "Romanian private hospital channel."),
    ("SNCh", "snch", "search_link", "ro", None,
     "https://www.google.com/search?q=site%3Asnch.ro+{query}", 0, "Societatea Națională de Chirurgie."),
    ("MEDSkill Center", "medskill", "search_link", "ro", None,
     "https://www.google.com/search?q=site%3Amedskill.ro+{query}+chirurgie", 0, "Romanian surgical skills courses."),
    ("rezidentiat-medicina.ro", "rezidentiat", "search_link", "ro", None,
     "https://www.google.com/search?q=site%3Arezidentiat-medicina.ro+{query}", 0, "Romanian resident prep."),
    ("Vimeo (RO)", "vimeo_ro", "search_link", "ro", None,
     "https://www.google.com/search?q=site%3Avimeo.com+{query}+chirurgie", 0, "Romanian surgical videos on Vimeo."),
    # Research / curated feeds
    ("AVOS Dataset (BIDMC)", "avos", "curated_feed", "en", None,
     "https://research.bidmc.org/surgical-informatics/avos", 0,
     "Annotated open surgery YouTube research dataset."),
    ("Surch Research Corpus", "surch", "curated_feed", "en", "urology",
     "https://github.com/imurs34/surch-model/", 0, "Robotic prostatectomy video research."),
]


def main() -> None:
    init_db()
    with db_session() as conn:
        conn.execute("DELETE FROM video_sources")
        for name, slug, tier, language, specialty, base_url, requires_auth, notes in VIDEO_SOURCES:
            conn.execute(
                """
                INSERT INTO video_sources (name, slug, tier, language, specialty, base_url, requires_auth, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, slug, tier, language, specialty, base_url, requires_auth, notes),
            )
        log_import(conn, "video_sources", "seed", len(VIDEO_SOURCES))
    print(f"Seeded {len(VIDEO_SOURCES)} video sources.")


if __name__ == "__main__":
    main()
