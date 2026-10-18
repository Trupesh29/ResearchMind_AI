"""Unit tests for Sectioning and Document Cleaning Service (Phase 4)."""

from backend.app.services.sectioning_service import (
    dehyphenate_text,
    detect_repeated_headers_footers,
    identify_heading,
    section_pages,
)


def test_dehyphenate_text():
    # Standard line-break hyphenation
    text = "This is a conser-\nvative approach to text cleaning."
    cleaned = dehyphenate_text(text)
    assert "conservative approach" in cleaned

    # Hyphenated compound with capital letter or standalone word
    compound = "state-of-the-art methodology"
    assert dehyphenate_text(compound) == compound


def test_detect_repeated_headers_footers_preserves_body():
    # 3-page document where top block has identical running header
    # and bottom has page numbers, but middle has repeated body phrase
    pages_data = [
        {
            "page_number": 1,
            "height": 792.0,
            "blocks": [
                {"id": "p1_b0", "bbox": [50, 30, 400, 50], "text": "Journal of AI Research 2026"},
                {"id": "p1_b1", "bbox": [50, 200, 500, 300], "text": "Deep neural networks are effective models."},
                {"id": "p1_b2", "bbox": [280, 750, 320, 770], "text": "1"},
            ],
        },
        {
            "page_number": 2,
            "height": 792.0,
            "blocks": [
                {"id": "p2_b0", "bbox": [50, 30, 400, 50], "text": "Journal of AI Research 2026"},
                {
                    "id": "p2_b1",
                    "bbox": [50, 200, 500, 300],
                    "text": "Deep neural networks are effective models.",
                },  # Legitimate repeated body text!
                {"id": "p2_b2", "bbox": [280, 750, 320, 770], "text": "2"},
            ],
        },
        {
            "page_number": 3,
            "height": 792.0,
            "blocks": [
                {"id": "p3_b0", "bbox": [50, 30, 400, 50], "text": "Journal of AI Research 2026"},
                {"id": "p3_b1", "bbox": [50, 200, 500, 300], "text": "Experimental evaluation confirms results."},
                {"id": "p3_b2", "bbox": [280, 750, 320, 770], "text": "3"},
            ],
        },
    ]

    repeated = detect_repeated_headers_footers(pages_data)
    assert "Journal of AI Research 2026" in repeated
    # Body text must NOT be detected as header/footer
    assert "Deep neural networks are effective models." not in repeated

    sections = section_pages(pages_data)
    # The repeated body text MUST survive in the cleaned section text
    all_text = " ".join(s.text for s in sections)
    assert "Deep neural networks are effective models." in all_text
    assert "Journal of AI Research 2026" not in all_text


def test_identify_headings():
    assert identify_heading("Abstract")[0] is True
    assert identify_heading("Abstract")[1] == "abstract"

    assert identify_heading("1. Introduction")[0] is True
    assert identify_heading("1. Introduction")[1] == "introduction"

    assert identify_heading("2. Related Work")[0] is True
    assert identify_heading("2. Related Work")[1] == "related_work"

    assert identify_heading("3. Methodology")[0] is True
    assert identify_heading("3. Methodology")[1] == "methodology"

    assert identify_heading("4. Experimental Results")[0] is True
    assert identify_heading("4. Experimental Results")[1] == "results"

    assert identify_heading("References")[0] is True
    assert identify_heading("References")[1] == "references"

    # Full sentence should NOT be a heading
    assert identify_heading("This is a normal paragraph with a sentence ending in a period.")[0] is False


def test_section_pages_provenance_and_references():
    pages_data = [
        {
            "page_number": 1,
            "height": 792.0,
            "blocks": [
                {"id": "p1_b0", "bbox": [50, 100, 500, 150], "text": "Pre-heading preamble text describing context."},
                {
                    "id": "p1_b1",
                    "bbox": [50, 200, 500, 240],
                    "text": "Abstract\nWe introduce a novel method for paper analysis.",
                },
                {
                    "id": "p1_b2",
                    "bbox": [50, 300, 500, 400],
                    "text": "1. Introduction\nResearch papers contain deep knowledge.",
                },
            ],
        },
        {
            "page_number": 2,
            "height": 792.0,
            "blocks": [
                {
                    "id": "p2_b0",
                    "bbox": [50, 100, 500, 200],
                    "text": "References\n[1] Author A, 2024. Paper title. Venue.",
                },
            ],
        },
    ]

    sections = section_pages(pages_data)
    assert len(sections) >= 3

    # First section before abstract is unknown
    assert sections[0].section == "unknown"
    assert "Pre-heading preamble" in sections[0].text
    assert sections[0].is_reference is False

    # Second section is abstract
    assert sections[1].section == "abstract"
    assert "We introduce a novel method" in sections[1].text
    assert sections[1].is_reference is False

    # References section
    ref_sec = [s for s in sections if s.section == "references"][0]
    assert ref_sec.is_reference is True
    assert "[1] Author A" in ref_sec.text
    assert "p2_b0" in ref_sec.block_ids
