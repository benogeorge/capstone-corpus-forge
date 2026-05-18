"""Helpers for extracting raw text from uploaded files."""

from __future__ import annotations

import os
import re

try:
    import pdfplumber
except Exception:
    pdfplumber = None


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
    with open(file_path, "r", encoding="utf-8", errors="replace") as file_handle:
        return file_handle.read()


def extract_text_from_md(file_path: str) -> str:
    return extract_text_from_txt(file_path)


def extract_text_from_py(file_path: str) -> str:
    return extract_text_from_txt(file_path)


def extract_text_from_js(file_path: str) -> str:
    return extract_text_from_txt(file_path)


def extract_text_from_pdf(file_path: str) -> str:
    if pdfplumber is None:
        # pdfplumber not available, return empty string to allow app to continue
        return ""

    extracted_pages = []

    with pdfplumber.open(file_path) as pdf_file:
        for page in pdf_file.pages:
            page_text = page.extract_text() or ""
            if page_text:
                extracted_pages.append(page_text)

    return clean_extracted_text("\n\n".join(extracted_pages))


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