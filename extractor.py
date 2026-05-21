"""Helpers for extracting raw text from uploaded files."""

from __future__ import annotations

import os
import re
from pathlib import Path

try:
    from charset_normalizer import from_bytes
except Exception:
    from_bytes = None

try:
    import pdfplumber
except Exception:
    pdfplumber = None

from utils import guard_expanded_bytes


MAX_EXTRACTED_BYTES = 20 * 1024 * 1024


ANSI_ESCAPE_RE = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
WHITESPACE_RE = re.compile(r"[ \t\f\v]+")


def strip_control_characters(text: str) -> str:
    """Remove ANSI escape codes and ASCII control noise from extracted text."""

    if not text:
        return ""

    cleaned_text = ANSI_ESCAPE_RE.sub(" ", text)
    cleaned_text = CONTROL_CHAR_RE.sub(" ", cleaned_text)
    cleaned_text = cleaned_text.replace("\ufeff", "")
    cleaned_text = cleaned_text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned_text = WHITESPACE_RE.sub(" ", cleaned_text)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
    return cleaned_text.strip()


def clean_extracted_text(raw_text: str) -> str:
    """Normalize extracted text before it is embedded into vectors.

    This removes obvious page-number lines and collapses excessive blank-line
    runs so PDF extraction noise does not pollute embeddings.
    """
    if not raw_text:
        return ""

    normalized_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned_lines: list[str] = []

    for raw_line in normalized_text.split("\n"):
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue

        compact_line = re.sub(r"\s+", " ", line)

        if re.fullmatch(r"(?:page\s*)?\d+(?:\s*/\s*\d+)?", compact_line, re.IGNORECASE):
            continue

        if re.fullmatch(r"page\s+\d+(?:\s+of\s+\d+)?", compact_line, re.IGNORECASE):
            continue

        cleaned_lines.append(compact_line)

    collapsed_text = "\n".join(cleaned_lines)
    collapsed_text = re.sub(r"\n{3,}", "\n\n", collapsed_text)
    return collapsed_text.strip()


def extract_text_from_txt(file_path: str) -> str:
    return safe_read_text(file_path)


def extract_text_from_md(file_path: str) -> str:
    return extract_text_from_txt(file_path)


def extract_text_from_py(file_path: str) -> str:
    return extract_text_from_txt(file_path)


def extract_text_from_js(file_path: str) -> str:
    return extract_text_from_txt(file_path)


def safe_read_text(file_path: str) -> str:
    """Read a text file defensively by detecting encoding before decoding."""

    raw_bytes = Path(file_path).read_bytes()

    if not raw_bytes:
        return ""

    bom_prefixes = (
        (b"\xef\xbb\xbf", "utf-8-sig"),
        (b"\xff\xfe\x00\x00", "utf-32"),
        (b"\x00\x00\xfe\xff", "utf-32"),
        (b"\xff\xfe", "utf-16"),
        (b"\xfe\xff", "utf-16"),
    )

    for bom_bytes, encoding in bom_prefixes:
        if raw_bytes.startswith(bom_bytes):
            text = raw_bytes.decode(encoding, errors="strict")
            return strip_control_characters(text)

    if from_bytes is not None:
        detection = from_bytes(raw_bytes).best()
        if detection is not None:
            text = str(detection)
            if text:
                return strip_control_characters(text)

    if b"\x00" in raw_bytes:
        even_null_ratio = raw_bytes[::2].count(0) / max(len(raw_bytes[::2]), 1)
        odd_null_ratio = raw_bytes[1::2].count(0) / max(len(raw_bytes[1::2]), 1)
        if odd_null_ratio > 0.3 and even_null_ratio < 0.1:
            try:
                return strip_control_characters(raw_bytes.decode("utf-16-le"))
            except UnicodeDecodeError:
                pass
        if even_null_ratio > 0.3 and odd_null_ratio < 0.1:
            try:
                return strip_control_characters(raw_bytes.decode("utf-16-be"))
            except UnicodeDecodeError:
                pass

    fallback_encodings = ("utf-8", "utf-8-sig", "cp1252", "latin-1")
    for encoding in fallback_encodings:
        try:
            text = raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
        if text:
            return strip_control_characters(text)

    return strip_control_characters(raw_bytes.decode("utf-8", errors="replace"))


def extract_text_from_pdf(file_path: str) -> str:
    if pdfplumber is None:
        # pdfplumber not available, return empty string to allow app to continue
        return ""

    extracted_pages = []
    current_total_bytes = 0

    with pdfplumber.open(file_path) as pdf_file:
        for page in pdf_file.pages:
            page_text = page.extract_text() or ""
            if page_text:
                current_total_bytes = guard_expanded_bytes(
                    current_total_bytes, page_text, MAX_EXTRACTED_BYTES
                )
                extracted_pages.append(page_text)

    return strip_control_characters("\n".join(extracted_pages))


def extract_text_from_file(file_path: str) -> str:
    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".pdf":
        return extract_text_from_pdf(file_path)
    if extension == ".txt":
        return extract_text_from_txt(file_path)
    if extension == ".md":
        return extract_text_from_md(file_path)
    if extension == ".py":
        return extract_text_from_py(file_path)
    if extension == ".js":
        return extract_text_from_js(file_path)

    raise ValueError(f"Unsupported file extension: {extension}")