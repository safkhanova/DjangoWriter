#!/usr/bin/env python3
"""Extract the article body from downloaded HTML pages into importable Markdown.

The source HTML is downloaded separately with curl. This script has no network access.
It deliberately extracts only pages listed in MANIFEST, all signed by the portfolio owner.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = Path("/tmp/djangowriter-author-pages")

MANIFEST = {
    "serxosluq.html": "instanceJavid/content/texts/serxosluq.md",
    "gurcu-qizi.html": "instanceJavid/content/texts/gurcu-qizi.md",
    "yol.html": "instanceJavid/content/texts/yol.md",
    "seyahet.html": "instanceJavid/content/texts/seyahet.md",
    "yazicilar-gundemi.html": "instanceJavid/content/texts/yazicilar-gundemi-serh-etmelidirmi.md",
    "medeni-gerilik.html": "instanceJavid/content/texts/medeni-geriliyin-sebebi-asagi-zumredirmi.md",
    "uslub-kohnelende.html": "instanceJavid/content/texts/uslub-kohnelende.md",
    "kor-noqte.html": "instanceJavid/content/texts/mektebdeki-musahide-kameralarinin-cekmediyi-kor-noqtelerde-ne-bas-verir.md",
    "dalgalanmayan.html": "instanceJavid/content/texts/dalgalanmayan-yaddas-tarlasi.md",
    "seymur-baycan.html": "instanceJavid/content/texts/seymur-baycan-neden-narahatdir.md",
    "edebiyyati-oldurmek.html": "instanceJavid/content/texts/edebiyyati-oldurmek-isteyenler.md",
    "ilk-defe-amerikada.html": "instanceJavid/content/texts/ilk-defe-amerikada.md",
    "yaziciliq-romantikasi.html": "instanceJavid/content/texts/yaziciliq-romantikasi.md",
    "nabat.html": "instanceJavid/content/texts/nabat-kimi-olmayan-nabat.md",
    "yolun-ehemiyyeti.html": "instanceJavid/content/texts/yolun-ehemiyyetinden-danisib-yoldan-cixanlar.md",
    "atasinin-olumu.html": "instanceJavid/content/texts/atasinin-olumunu-arzulayan-yazici.md",
    "diem-perdidi.html": "instanceJavid/content/texts/diem-perdidi.md",
    "a-romani.html": "instanceJavid/content/texts/a-romani-plagiatdir.md",
    "folklor-modern.html": "instanceJavid/content/texts/folklor-ve-modern-arasinda.md",
}


class BodyExtractor(HTMLParser):
    CONTAINER_CLASSES = {
        "entry-content", "post-content", "article-content", "article-body",
        "article_body", "news-text", "news_content", "texts",
    }
    SKIP_TAGS = {"script", "style", "noscript", "svg", "form", "button"}
    BLOCK_TAGS = {"p", "div", "section", "article", "li", "blockquote", "h1", "h2", "h3", "h4"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.capture_depth = 0
        self.skip_depth = 0
        self.parts: list[str] = []

    @staticmethod
    def is_container(attrs: dict[str, str]) -> bool:
        if attrs.get("id") in {"article-content", "news-content"} or attrs.get("itemprop") == "articleBody":
            return True
        classes = set((attrs.get("class") or "").split())
        return bool(classes & BodyExtractor.CONTAINER_CLASSES)

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {key: value or "" for key, value in attrs_list}
        if not self.capture_depth and self.is_container(attrs):
            self.capture_depth = 1
            return
        if not self.capture_depth:
            return
        self.capture_depth += 1
        classes = set((attrs.get("class") or "").split())
        if tag in self.SKIP_TAGS or "links_block" in classes or "share" in classes:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in {"h2", "h3", "h4"}:
            self.parts.append("\n\n## ")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n\n")
        elif tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if not self.capture_depth:
            return
        if self.skip_depth and tag in self.SKIP_TAGS | {"ul", "div"}:
            self.skip_depth -= 1
        self.capture_depth -= 1
        if self.capture_depth and not self.skip_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if self.capture_depth and not self.skip_depth:
            self.parts.append(data)

    def result(self) -> str:
        text = "".join(self.parts).replace("\xa0", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        # Some publishers place navigation, social links, and related stories in
        # the same DOM container as the signed article. Keep the article only.
        for marker in (
            "\nSaytın bloklandığı yerlərdə",
            "\n## Buna da bax:",
            "\n## Paradiqma\n",
            "\nE-mail\n",
        ):
            if marker in text:
                text = text.split(marker, 1)[0].rstrip()
        return text + "\n" if text else ""


def main() -> int:
    failures = []
    for source_name, relative_target in MANIFEST.items():
        source = DOWNLOADS / source_name
        target = ROOT / relative_target
        if not source.exists():
            failures.append(f"missing download: {source_name}")
            continue
        parser = BodyExtractor()
        parser.feed(source.read_text(encoding="utf-8", errors="replace"))
        text = parser.result()
        words = len(text.split())
        if words < 80:
            failures.append(f"no article body: {source_name} ({words} words)")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        print(f"{target.relative_to(ROOT)}: {words} words")
    if failures:
        print("\nUnresolved:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
