"""
Content extraction utilities for research pipeline.

Extracts main content, headings, code blocks from HTML pages using
BeautifulSoup and readability-lxml (with graceful fallback).
"""

import logging
import re
from typing import List, Optional

from bs4 import BeautifulSoup, Comment

logger = logging.getLogger(__name__)

# Try to import readability-lxml, gracefully fallback if not available
try:
    from readability import Document as ReadabilityDocument

    READABILITY_AVAILABLE = True
except ImportError:
    READABILITY_AVAILABLE = False
    logger.info("readability-lxml not available, using heuristic extraction")


class ContentExtractor:
    """Extract structured content from HTML pages."""

    def __init__(self):
        """Initialize content extractor."""
        self.max_text_length = 8000

    def extract_main_content(self, html: str) -> str:
        """
        Extract main content from HTML.

        Uses readability-lxml if available, falls back to heuristic extraction.

        Args:
            html: Raw HTML string

        Returns:
            Extracted main content text
        """
        if READABILITY_AVAILABLE:
            try:
                doc = ReadabilityDocument(html)
                content_html = doc.summary()
                soup = BeautifulSoup(content_html, "html.parser")
                text = soup.get_text(separator="\n", strip=True)
                return self._truncate_text(text)
            except Exception as e:
                logger.debug(f"Readability extraction failed, using fallback: {e}")

        return self._heuristic_extraction(html)

    def _heuristic_extraction(self, html: str) -> str:
        """
        Heuristic-based content extraction.

        Removes common non-content elements and extracts largest text block.

        Args:
            html: Raw HTML string

        Returns:
            Extracted content text
        """
        soup = BeautifulSoup(html, "html.parser")

        for element in soup(["script", "style", "noscript", "iframe"]):
            element.decompose()

        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        noise_patterns = ["nav", "header", "footer", "sidebar", "menu", "ad", "cookie", "popup"]

        for element in soup.find_all(True):
            element_id = element.get("id", "").lower()
            element_class = " ".join(element.get("class", [])).lower()

            if any(pattern in element_id or pattern in element_class for pattern in noise_patterns):
                element.decompose()

        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", id=re.compile(r"content|main", re.I))
            or soup.find("div", class_=re.compile(r"content|main|body", re.I))
            or soup.body
            or soup
        )

        text = main_content.get_text(separator="\n", strip=True)
        return self._truncate_text(text)

    def _truncate_text(self, text: str) -> str:
        """Truncate text to maximum length."""
        if len(text) <= self.max_text_length:
            return text

        return text[: self.max_text_length] + "..."

    def extract_headings(self, html: str) -> List[str]:
        """
        Extract h1, h2, h3 headings from HTML.

        Args:
            html: Raw HTML string

        Returns:
            List of heading texts
        """
        soup = BeautifulSoup(html, "html.parser")
        headings = []

        for tag in ["h1", "h2", "h3"]:
            for heading in soup.find_all(tag):
                text = heading.get_text(strip=True)
                if text and len(text) > 0:
                    headings.append(text)

        return headings

    def extract_code_blocks(self, html: str) -> List[str]:
        """
        Extract code blocks from HTML.

        Finds both HTML <pre>/<code> tags and Markdown-style code blocks.

        Args:
            html: Raw HTML string

        Returns:
            List of code block contents
        """
        soup = BeautifulSoup(html, "html.parser")
        code_blocks = []

        for pre in soup.find_all("pre"):
            code = pre.find("code")
            if code:
                text = code.get_text(strip=True)
            else:
                text = pre.get_text(strip=True)

            if text and len(text) > 10:
                code_blocks.append(text)

        for code in soup.find_all("code"):
            if code.parent.name != "pre":
                text = code.get_text(strip=True)
                if text and len(text) > 10:
                    code_blocks.append(text)

        markdown_code_pattern = re.compile(r"```[\w]*\n(.*?)```", re.DOTALL)
        for match in markdown_code_pattern.finditer(html):
            code_text = match.group(1).strip()
            if code_text and len(code_text) > 10:
                code_blocks.append(code_text)

        return code_blocks[:10]

    def extract_title(self, html: str) -> Optional[str]:
        """
        Extract page title from HTML.

        Args:
            html: Raw HTML string

        Returns:
            Page title or None
        """
        soup = BeautifulSoup(html, "html.parser")

        title_tag = soup.find("title")
        if title_tag:
            return str(title_tag.get_text(strip=True))

        h1_tag = soup.find("h1")
        if h1_tag:
            return str(h1_tag.get_text(strip=True))

        return None

    def extract_meta_description(self, html: str) -> Optional[str]:
        """
        Extract meta description from HTML.

        Args:
            html: Raw HTML string

        Returns:
            Meta description or None
        """
        soup = BeautifulSoup(html, "html.parser")

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            return str(meta_desc["content"]).strip()

        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc and og_desc.get("content"):
            return str(og_desc["content"]).strip()

        return None


class CodeBlockParser:
    """Parse and annotate code blocks with language information."""

    @staticmethod
    def parse_markdown_code_blocks(text: str) -> List[dict]:
        """
        Parse Markdown code blocks with language annotation.

        Args:
            text: Text containing Markdown code blocks

        Returns:
            List of dicts with 'language' and 'code' keys
        """
        pattern = re.compile(r"```([\w]*)\n(.*?)```", re.DOTALL)
        blocks = []

        for match in pattern.finditer(text):
            language = match.group(1).strip() or "unknown"
            code = match.group(2).strip()
            blocks.append({"language": language, "code": code})

        return blocks

    @staticmethod
    def parse_html_code_blocks(html: str) -> List[dict]:
        """
        Parse HTML code blocks with language annotation.

        Args:
            html: HTML containing code blocks

        Returns:
            List of dicts with 'language' and 'code' keys
        """
        soup = BeautifulSoup(html, "html.parser")
        blocks = []

        for pre in soup.find_all("pre"):
            code_tag = pre.find("code")
            if code_tag:
                text = code_tag.get_text(strip=True)
                language = "unknown"

                classes = code_tag.get("class", [])
                for cls in classes:
                    if cls.startswith("language-"):
                        language = cls.replace("language-", "")
                        break
                    elif cls.startswith("lang-"):
                        language = cls.replace("lang-", "")
                        break

                if text:
                    blocks.append({"language": language, "code": text})

        return blocks
