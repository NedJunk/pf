import re
from pathlib import Path


class WikiManager:
    INDEX = "index.md"
    LOG = "log.md"
    PAGES_DIR = "pages"

    def __init__(self, wiki_dir: str) -> None:
        self._dir = Path(wiki_dir)

    def scaffold_if_empty(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / self.PAGES_DIR).mkdir(exist_ok=True)
        index = self._dir / self.INDEX
        if not index.exists():
            index.write_text("# Wiki Index\n\n", encoding="utf-8")
        log = self._dir / self.LOG
        if not log.exists():
            log.write_text("# Wiki Log\n\n", encoding="utf-8")

    def read_index(self) -> str:
        return (self._dir / self.INDEX).read_text(encoding="utf-8")

    def read_log(self) -> str:
        return (self._dir / self.LOG).read_text(encoding="utf-8")

    def read_page(self, name: str) -> str:
        return (self._dir / self.PAGES_DIR / name).read_text(encoding="utf-8")

    def write_page(self, name: str, content: str) -> None:
        pages_dir = self._dir / self.PAGES_DIR
        pages_dir.mkdir(parents=True, exist_ok=True)
        target = pages_dir / name
        tmp = target.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.rename(target)

    def write_index(self, content: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        target = self._dir / self.INDEX
        tmp = target.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.rename(target)

    def list_pages(self) -> list[str]:
        pages_dir = self._dir / self.PAGES_DIR
        if not pages_dir.exists():
            return []
        return [f.name for f in pages_dir.iterdir() if f.suffix == ".md"]

    def append_log(self, entry: str) -> None:
        log = self._dir / self.LOG
        with log.open("a", encoding="utf-8") as f:
            f.write(entry + "\n")


def parse_ingest_response(response: str) -> tuple[list[tuple[str, str]], str | None]:
    response = response.replace("\r\n", "\n")
    pages = []
    for match in re.finditer(
        r"--- PAGE: (.+?) ---\n(.*?)--- END PAGE ---", response, re.DOTALL
    ):
        pages.append((match.group(1).strip(), match.group(2).strip()))
    index_match = re.search(
        r"--- INDEX ---\n(.*?)--- INDEX END ---", response, re.DOTALL
    )
    index = index_match.group(1).strip() if index_match else None
    return pages, index
