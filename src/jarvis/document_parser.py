"""
Document parser for extracting text from various file formats.

Supports text and PDF files using open-source parsers.
"""

import logging
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

logger = logging.getLogger(__name__)


class DocumentParser:
    """Parser for extracting text from documents."""

    @staticmethod
    def parse(file_path: Path) -> str:
        """
        Parse document and extract text.

        Args:
            file_path: Path to document file

        Returns:
            Extracted text content

        Raises:
            ValueError: If file format is unsupported
            FileNotFoundError: If file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            return DocumentParser._parse_pdf(file_path)
        elif suffix in {".txt", ".md"}:
            return DocumentParser._parse_text(file_path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    @staticmethod
    def _parse_pdf(file_path: Path) -> str:
        """
        Parse PDF file and extract text.

        Args:
            file_path: Path to PDF file

        Returns:
            Extracted text content
        """
        try:
            reader = PdfReader(file_path)
            text = ""
            for page_num, page in enumerate(reader.pages):
                try:
                    text += page.extract_text()
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {page_num}: {e}")

            logger.info(f"Successfully parsed PDF: {file_path} ({len(reader.pages)} pages)")
            return text
        except Exception as e:
            logger.error(f"Failed to parse PDF {file_path}: {e}")
            raise

    @staticmethod
    def _parse_text(file_path: Path) -> str:
        """
        Parse text file and extract content.

        Args:
            file_path: Path to text file

        Returns:
            File content
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            logger.info(f"Successfully parsed text file: {file_path}")
            return content
        except Exception as e:
            logger.error(f"Failed to parse text file {file_path}: {e}")
            raise
