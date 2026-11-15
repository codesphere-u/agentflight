"""Integrity tests for the AgentFlight v1.5.0 website, docs, and metadata."""

from __future__ import annotations

from pathlib import Path

import agentflight

ROOT_DIR = Path(__file__).resolve().parent.parent
WEBSITE_DIR = ROOT_DIR / "website"


def test_version_is_1_6_0() -> None:
    assert agentflight.__version__ == "1.6.0"


def test_website_pages_and_assets_present() -> None:
    expected_files = [
        "index.html",
        "studio.html",
        "proof.html",
        "docs.html",
        "rules.html",
        "styles.css",
        "app.js",
        "favicon.svg",
        "og-image.svg",
        "llms.txt",
        "llms-full.txt",
        "robots.txt",
        "sitemap.xml",
        "manifest.webmanifest",
    ]
    for name in expected_files:
        path = WEBSITE_DIR / name
        assert path.is_file(), f"Missing website artifact: {path}"


def test_html_pages_have_cache_busted_assets_and_hidden_guard() -> None:
    html_pages = ["index.html", "studio.html", "proof.html", "docs.html", "rules.html"]
    for page in html_pages:
        content = (WEBSITE_DIR / page).read_text(encoding="utf-8")
        assert "styles.css?v=1.6.0" in content
        assert "app.js?v=1.6.0" in content
        assert "favicon.svg?v=1.6.0" in content
        assert "[hidden]" in content
        assert 'width="196" height="36"' in content


def test_docs_guides_and_llms_files_present() -> None:
    assert (ROOT_DIR / "docs" / "GETTING_STARTED.md").is_file()
    assert (ROOT_DIR / "docs" / "MCP_AND_AGENTS.md").is_file()
    assert (ROOT_DIR / "llms.txt").is_file()
    assert (ROOT_DIR / "llms-full.txt").is_file()
