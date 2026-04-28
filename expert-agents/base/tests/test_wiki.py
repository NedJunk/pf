import pytest
from pathlib import Path
from expert_agent_base.wiki import WikiManager, parse_ingest_response


@pytest.fixture
def wiki(tmp_path):
    w = WikiManager(str(tmp_path / "wiki"))
    w.scaffold_if_empty()
    return w


def test_scaffold_creates_index_and_log(tmp_path):
    w = WikiManager(str(tmp_path / "wiki"))
    w.scaffold_if_empty()
    assert (tmp_path / "wiki" / "index.md").exists()
    assert (tmp_path / "wiki" / "log.md").exists()
    assert (tmp_path / "wiki" / "pages").is_dir()


def test_scaffold_is_idempotent(tmp_path):
    w = WikiManager(str(tmp_path / "wiki"))
    w.scaffold_if_empty()
    w.write_index("# Custom Index\n\ncustom content")
    w.scaffold_if_empty()  # should not overwrite
    assert "custom content" in w.read_index()


def test_read_index_returns_scaffold_content(wiki):
    content = wiki.read_index()
    assert "# Wiki Index" in content


def test_write_and_read_page(wiki):
    wiki.write_page("decisions.md", "# Decisions\n\nUse TDD.")
    assert wiki.read_page("decisions.md") == "# Decisions\n\nUse TDD."


def test_write_page_leaves_no_tmp_file(wiki, tmp_path):
    wiki.write_page("test.md", "content")
    # tmp file should be gone after write
    assert not list((tmp_path / "wiki" / "pages").glob("*.tmp"))


def test_list_pages_returns_md_files(wiki):
    wiki.write_page("a.md", "A")
    wiki.write_page("b.md", "B")
    pages = wiki.list_pages()
    assert set(pages) == {"a.md", "b.md"}


def test_list_pages_empty_when_no_pages(wiki):
    assert wiki.list_pages() == []


def test_append_log(wiki):
    wiki.append_log("## [2026-04-28] ingest | abc123")
    assert "abc123" in wiki.read_log()


def test_write_index(wiki):
    wiki.write_index("# Updated Index\n\n- [[page.md]] — some page")
    assert "Updated Index" in wiki.read_index()


def test_parse_ingest_response_extracts_pages():
    raw = """
--- PAGE: decisions.md ---
# Decisions
Use TDD.
--- END PAGE ---

--- INDEX ---
# Wiki Index

- [[decisions.md]] — TDD decision
--- INDEX END ---
"""
    pages, index = parse_ingest_response(raw)
    assert len(pages) == 1
    assert pages[0][0] == "decisions.md"
    assert "Use TDD" in pages[0][1]
    assert "decisions.md" in index


def test_parse_ingest_response_handles_missing_index():
    raw = "--- PAGE: x.md ---\ncontent\n--- END PAGE ---\n"
    pages, index = parse_ingest_response(raw)
    assert len(pages) == 1
    assert index is None


def test_parse_ingest_response_empty_response():
    pages, index = parse_ingest_response("nothing useful here")
    assert pages == []
    assert index is None
