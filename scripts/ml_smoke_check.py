#!/usr/bin/env python3
"""
ResearchMind AI — ML & Vector Environment Smoke Check
Verifies Python environment, PyTorch, CUDA / CPU device fallback,
SentenceTransformers embedding inference with all-MiniLM-L6-v2,
and FAISS vector index creation and querying.
"""

import sys
import time
from pathlib import Path

import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    print("=" * 70)
    print(" ResearchMind AI — Machine Learning & Vector Search Smoke Check")
    print("=" * 70)

    # 1. Python runtime
    print("\n[1/5] Python Environment:")
    print(f"  - Python Version: {sys.version.split()[0]}")
    print(f"  - Executable: {sys.executable}")

    # 2. PyTorch & Device Detection
    print("\n[2/5] PyTorch & Hardware Detection:")
    try:
        import torch

        print(f"  - PyTorch Version: {torch.__version__}")
        cuda_avail = torch.cuda.is_available()
        print(f"  - CUDA Available: {cuda_avail}")
        if cuda_avail:
            device = torch.device("cuda")
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            print(f"  - GPU Device: {gpu_name} ({vram_gb:.2f} GB VRAM)")
            # GPU tensor test
            t_gpu = torch.randn(100, 100, device=device)
            res_gpu = torch.matmul(t_gpu, t_gpu)
            print(f"  - GPU Tensor Matmul Check: Passed (shape: {res_gpu.shape})")
        else:
            print(
                "  - Notice: CUDA not detected, using CPU execution (verified fallback)."
            )

        # CPU tensor test
        t_cpu = torch.randn(100, 100, device="cpu")
        res_cpu = torch.matmul(t_cpu, t_cpu)
        print(f"  - CPU Tensor Matmul Check: Passed (shape: {res_cpu.shape})")
    except Exception as exc:
        print(f"  [ERROR] PyTorch verification failed: {exc}")
        return 1

    # 3. SentenceTransformers & all-MiniLM-L6-v2 Verification
    print("\n[3/5] Sentence Transformers (all-MiniLM-L6-v2):")
    try:
        import sentence_transformers
        from sentence_transformers import SentenceTransformer

        print(f"  - sentence-transformers Version: {sentence_transformers.__version__}")

        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        print(f"  - Loading model '{model_name}'...")
        t0 = time.perf_counter()
        # Explicitly specify device based on availability
        eval_device = "cuda" if cuda_avail else "cpu"
        model = SentenceTransformer(model_name, device=eval_device)
        load_time = time.perf_counter() - t0
        print(
            f"  - Model loaded successfully in {load_time:.2f}s on device: '{eval_device}'"
        )

        # Synthetic test inputs
        sample_texts = [
            "ResearchMind AI provides traceable page-level evidence for research papers.",
            "Universal document analysis extracts text and verifies claims with citations.",
            "Hardware benchmarking compares DDR4 and DDR5 memory bandwidth.",
        ]
        t1 = time.perf_counter()
        embeddings = model.encode(
            sample_texts, convert_to_numpy=True, normalize_embeddings=True
        )
        encode_time = time.perf_counter() - t1

        print(
            f"  - Encoded {len(sample_texts)} sentences in {encode_time * 1000:.1f}ms"
        )
        print(
            f"  - Embedding Matrix Shape: {embeddings.shape} (Expected: ({len(sample_texts)}, 384))"
        )
        assert embeddings.shape == (len(sample_texts), 384), (
            f"Unexpected embedding shape: {embeddings.shape}"
        )
        assert np.all(np.isfinite(embeddings)), "Embeddings contain NaN or Inf values!"
        print(
            "  - Embedding Verification: Passed (Normalized finite vectors, dimension=384)"
        )
    except Exception as exc:
        print(f"  [ERROR] SentenceTransformers verification failed: {exc}")
        return 1

    # 4. FAISS Index FlatIP & Query Check
    print("\n[4/5] FAISS Vector Search (CPU Fallback):")
    try:
        import faiss

        print(
            f"  - FAISS CPU Version: {faiss.__version__ if hasattr(faiss, '__version__') else 'Available'}"
        )

        dimension = 384
        index = faiss.IndexFlatIP(
            dimension
        )  # Inner Product on normalized vectors = Cosine Similarity
        print(f"  - Created FAISS IndexFlatIP (dimension={dimension})")

        # Add vectors
        index.add(embeddings.astype("float32"))
        print(f"  - Indexed {index.ntotal} vectors")
        assert index.ntotal == len(sample_texts), (
            f"Index count mismatch: {index.ntotal}"
        )

        # Query test
        query_text = ["evidence-based citations for academic research"]
        query_vec = model.encode(
            query_text, convert_to_numpy=True, normalize_embeddings=True
        ).astype("float32")
        k = 2
        distances, indices = index.search(query_vec, k)

        print(f"  - Top-{k} Query Search Results:")
        for rank, (idx, score) in enumerate(zip(indices[0], distances[0])):
            print(
                f'    Rank {rank + 1}: [Index {idx}] Score={score:.4f} => "{sample_texts[idx]}"'
            )

        # Both sentence 0 and 1 are relevant to evidence and citations; check top-2 contains both
        top_indices = set(indices[0])
        assert 0 in top_indices and 1 in top_indices, (
            f"Expected indices 0 and 1 in top results, got {indices[0]}"
        )
        assert distances[0][0] > 0.4, (
            f"Expected strong positive similarity score, got {distances[0][0]}"
        )
        print(
            "  - FAISS Search Verification: Passed (Relevant nearest neighbors retrieved with cosine scores > 0.4)"
        )
    except Exception as exc:
        print(f"  [ERROR] FAISS verification failed: {exc}")
        return 1

    # 5. Generator Provider Readiness Check
    print("\n[5/5] Generator Provider Readiness Check:")
    from backend.app.core.config import settings

    print(f"  - Provider Configured: {settings.GENERATOR_PROVIDER}")
    print(f"  - Target Model: {settings.GENERATOR_MODEL}")
    print(f"  - Timeout Seconds: {settings.GENERATOR_TIMEOUT_SECONDS}s")
    print(f"  - Max Retries: {settings.GENERATOR_MAX_RETRIES}")
    print(f"  - Cost Budget: ${settings.GENERATOR_BUDGET_USD:.2f}")

    if settings.GENERATOR_PROVIDER == "mock":
        print("  - Provider Status: Mock generator active for offline Phase 1 testing.")
        print(
            "  - Passage Disclosure: In Week 4, retrieved text excerpts sent to external LLMs will be displayed to users."
        )
    elif settings.GENERATOR_API_KEY.strip():
        print("  - Provider Status: Live API key detected in environment.")
    else:
        print(
            "  - Provider Status: Key missing for hosted provider (set GENERATOR_API_KEY in .env when ready)."
        )

    print("\n" + "=" * 70)
    print(" ALL MACHINE LEARNING & VECTOR ENVIRONMENT CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
