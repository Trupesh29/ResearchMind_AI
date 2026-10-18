"""Unit tests for Token-Safe Sentence-Aware Chunking Service (Phase 4)."""

from backend.app.services.chunking_service import (
    MODEL_MAX_SEQUENCE_LIMIT,
    TOKENIZER_MODEL_NAME,
    TOKENIZER_REVISION,
    chunk_document_sections,
    chunk_section,
    get_tokenizer,
    split_oversized_sentence,
)
from backend.app.services.sectioning_service import SectionResult


def test_tokenizer_metadata_and_special_tokens():
    tokenizer = get_tokenizer()
    assert tokenizer is not None
    # Verify special tokens [CLS] and [SEP] exist
    text = "Machine learning models require deterministic evaluation."
    encoded_special = tokenizer.encode(text, add_special_tokens=True)
    encoded_raw = tokenizer.encode(text, add_special_tokens=False)

    # BERT / MiniLM adds [CLS] (101) and [SEP] (102)
    assert len(encoded_special) == len(encoded_raw) + 2
    assert encoded_special[0] == tokenizer.cls_token_id
    assert encoded_special[-1] == tokenizer.sep_token_id


def test_split_oversized_sentence():
    tokenizer = get_tokenizer()
    # Construct a giant 100-word sentence with commas and semicolons
    long_sentence = (
        "In this extensive technical evaluation; we examine neural network architectures, "
        "training hyperparameters, optimization criteria, convergence behavior, gradient dynamics, "
        "and empirical generalization; furthermore, we evaluate attention heads, feedforward layers, "
        "layer normalization, residual connections, and embedding matrices across multiple distinct domains, "
        "demonstrating scalable performance improvements without degradation or regression in latency or accuracy."
    )
    pieces = split_oversized_sentence(long_sentence, tokenizer, max_tokens=30)
    assert len(pieces) > 1
    for piece in pieces:
        piece_tokens = len(tokenizer.encode(piece, add_special_tokens=False))
        assert piece_tokens <= 40


def test_chunk_section_bounds_and_no_silent_truncation():
    tokenizer = get_tokenizer()

    # Paragraph with ~500 tokens of text
    sentence = "Deep learning and natural language processing allow researchers to extract knowledge from scientific literature. "
    full_text = sentence * 25  # ~500 tokens

    sec = SectionResult(
        section_index=0,
        section="methodology",
        heading="3. Methodology",
        page_start=2,
        page_end=3,
        text=full_text,
        block_ids=["p2_b1", "p2_b2", "p3_b0"],
        is_reference=False,
    )

    chunks = chunk_section(sec, tokenizer)
    assert len(chunks) >= 2

    for c in chunks:
        # Every final chunk measured with special tokens MUST NOT exceed 256
        assert c.token_count <= MODEL_MAX_SEQUENCE_LIMIT
        assert c.token_count >= 50
        assert c.section == "methodology"
        assert c.page_start >= 2
        assert c.page_end <= 3
        assert c.is_excluded is False
        assert c.tokenizer_name == TOKENIZER_MODEL_NAME
        assert c.tokenizer_revision == TOKENIZER_REVISION
        assert any(b in ["p2_b1", "p2_b2", "p3_b0"] for b in c.block_ids)

        # Verify token count assertion
        re_encoded = len(tokenizer.encode(c.text, add_special_tokens=True))
        assert re_encoded == c.token_count

    # The entire section page range [2, 3] is covered across chunks
    assert min(c.page_start for c in chunks) == 2
    assert max(c.page_end for c in chunks) == 3


def test_references_chunk_exclusion():
    tokenizer = get_tokenizer()

    ref_text = (
        "[1] Vaswani, A., et al. Attention is all you need. In NeurIPS 2017.\n"
        "[2] Devlin, J., et al. BERT: Pre-training of deep bidirectional transformers. In NAACL 2019.\n"
        "[3] He, K., et al. Deep residual learning for image recognition. In CVPR 2016."
    )

    sec = SectionResult(
        section_index=1,
        section="references",
        heading="References",
        page_start=4,
        page_end=4,
        text=ref_text,
        block_ids=["p4_b1"],
        is_reference=True,
    )

    chunks = chunk_section(sec, tokenizer)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.is_excluded is True
        assert c.section == "references"
        assert c.token_count <= MODEL_MAX_SEQUENCE_LIMIT


def test_full_document_sequential_chunking():
    sections = [
        SectionResult(
            section_index=0,
            section="abstract",
            heading="Abstract",
            page_start=1,
            page_end=1,
            text="ResearchMind AI introduces robust automated document processing.",
            block_ids=["p1_b0"],
            is_reference=False,
        ),
        SectionResult(
            section_index=1,
            section="introduction",
            heading="1. Introduction",
            page_start=1,
            page_end=2,
            text="We address the challenge of ingesting academic papers with strict token safety.",
            block_ids=["p1_b1", "p2_b0"],
            is_reference=False,
        ),
        SectionResult(
            section_index=2,
            section="references",
            heading="References",
            page_start=2,
            page_end=2,
            text="[1] Goodfellow, I., et al. Deep Learning. MIT Press, 2016.",
            block_ids=["p2_b2"],
            is_reference=True,
        ),
    ]

    chunks = chunk_document_sections(sections)
    assert len(chunks) == 3

    # Check indices are sequential 0, 1, 2
    assert [c.chunk_index for c in chunks] == [0, 1, 2]
    assert chunks[0].section == "abstract"
    assert chunks[0].is_excluded is False
    assert chunks[1].section == "introduction"
    assert chunks[1].is_excluded is False
    assert chunks[2].section == "references"
    assert chunks[2].is_excluded is True


def test_lossless_bounded_bisection_cjk_and_unbroken_text():
    """Verify P4-01: No character truncation, termination guaranteed on continuous text."""
    tokenizer = get_tokenizer()

    # 400 continuous CJK characters
    text400 = "研" * 400
    pieces400 = split_oversized_sentence(text400, tokenizer, max_tokens=150)
    assert len(pieces400) > 1
    assert sum(map(len, pieces400)) == len(text400)
    for p in pieces400:
        tokens = len(tokenizer.encode(p, add_special_tokens=False))
        assert tokens <= 150

    # 1200 continuous CJK characters (previously truncated to 1000)
    text1200 = "研" * 1200
    pieces1200 = split_oversized_sentence(text1200, tokenizer, max_tokens=150)
    assert len(pieces1200) > 1
    assert sum(map(len, pieces1200)) == len(text1200)
    for p in pieces1200:
        tokens = len(tokenizer.encode(p, add_special_tokens=False))
        assert tokens <= 150

    # Unbroken identifier sequence without spaces or clause punctuation (300 tokens)
    unbroken = "alpha_beta_gamma_" * 50  # 850 chars
    pieces_unbroken = split_oversized_sentence(unbroken, tokenizer, max_tokens=50)
    assert len(pieces_unbroken) > 1
    assert sum(map(len, pieces_unbroken)) == len(unbroken)
    for p in pieces_unbroken:
        tokens = len(tokenizer.encode(p, add_special_tokens=False))
        assert tokens <= 50


def test_chunk_fine_grained_provenance():
    """Verify P4-02: Chunks attribute only contributing pages and blocks."""
    tokenizer = get_tokenizer()

    # Two-page synthetic section
    alpha_text = "Alpha evidence appears only on the first page. " * 35
    beta_text = "Beta evidence appears only on the second page. " * 35
    full_text = alpha_text + beta_text

    section = SectionResult(
        section_index=0,
        section="unknown",
        heading=None,
        page_start=1,
        page_end=2,
        text=full_text,
        block_ids=["page1-alpha", "page2-beta"],
    )

    chunks = chunk_section(section, tokenizer)
    assert len(chunks) >= 2

    # First chunk must belong only to page 1 and block page1-alpha
    assert "Beta" not in chunks[0].text
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 1
    assert chunks[0].block_ids == ["page1-alpha"]

    # Last chunk must belong only to page 2 and block page2-beta
    assert "Alpha" not in chunks[-1].text
    assert chunks[-1].page_start == 2
    assert chunks[-1].page_end == 2
    assert chunks[-1].block_ids == ["page2-beta"]

    # Test explicit block_spans
    explicit_section = SectionResult(
        section_index=1,
        section="methodology",
        heading="Methods",
        page_start=5,
        page_end=6,
        text=full_text,
        block_ids=["blk_5", "blk_6"],
        block_spans=[
            ("blk_5", 5, 0, len(alpha_text)),
            ("blk_6", 6, len(alpha_text), len(full_text)),
        ],
    )
    explicit_chunks = chunk_section(explicit_section, tokenizer)
    assert explicit_chunks[0].page_start == 5
    assert explicit_chunks[0].page_end == 5
    assert explicit_chunks[0].block_ids == ["blk_5"]
    assert explicit_chunks[-1].page_start == 6
    assert explicit_chunks[-1].page_end == 6
    assert explicit_chunks[-1].block_ids == ["blk_6"]


def test_strict_tokenizer_verification_and_sequence_limit():
    """Verify P4-03: Model limits and tokenizer configuration are strictly verified."""
    tokenizer = get_tokenizer()
    assert tokenizer.name_or_path == TOKENIZER_MODEL_NAME

    # Strict token limit enforcement on chunks
    long_text = "Continuous token safety measurement. " * 80
    sec = SectionResult(
        section_index=0,
        section="discussion",
        heading=None,
        page_start=1,
        page_end=1,
        text=long_text,
        block_ids=["b_disc"],
    )
    chunks = chunk_section(sec, tokenizer)
    for c in chunks:
        assert c.token_count <= MODEL_MAX_SEQUENCE_LIMIT
        assert c.tokenizer_revision == TOKENIZER_REVISION
