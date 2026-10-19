"""Real browser negative control: B title must not count as B chunk content."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright

from scripts.run_browser_verification import check_late_response_isolation

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r"C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True)
    page = browser.new_page()
    page.set_content(
        """<div role="dialog"><h2>BERT: Pre-training of Deep Bidirectional Transformers</h2><button>Reprocess</button><p>Loaded 1 of 1 chunks</p><article>Recurrent neural networks have been firmly established as state of the art approaches in sequence modeling.</article></div>"""
    )
    result = check_late_response_isolation(
        page.get_by_role("dialog"),
        "BERT: Pre-training of Deep Bidirectional Transformers",
        page.get_by_role("button"),
        expected_chunk_text="BERT",
        prohibited_chunk_text="Attention Is All You Need",
    )
    print("WRONG_PAPER_CHUNK_ACCEPTED", result)
    browser.close()
