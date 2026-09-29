#!/usr/bin/env python3
"""Extract text from a page range of a PDF into a plain-text file.

Usage:
    python extract_pdf_pages.py <pdf_path> <start_page> <end_page> [output_path]

Page numbers are 1-indexed and inclusive.
"""

import sys
from pathlib import Path

from pypdf import PdfReader


def main():
    if len(sys.argv) < 4:
        sys.exit("Usage: python extract_pdf_pages.py <pdf_path> <start_page> <end_page> [output_path]")

    pdf_path = Path(sys.argv[1]).resolve()
    start_page = int(sys.argv[2])
    end_page = int(sys.argv[3])
    output_path = Path(sys.argv[4]).resolve() if len(sys.argv) > 4 else pdf_path.with_name(
        f"{pdf_path.stem}_p{start_page}-{end_page}.txt"
    )

    reader = PdfReader(str(pdf_path))
    num_pages = len(reader.pages)
    if start_page < 1 or end_page > num_pages or start_page > end_page:
        sys.exit(f"Invalid page range {start_page}-{end_page}; PDF has {num_pages} pages.")

    chunks = []
    for page_num in range(start_page, end_page + 1):
        text = reader.pages[page_num - 1].extract_text() or ""
        chunks.append(f"----- Page {page_num} -----\n{text.strip()}\n")

    output_path.write_text("\n".join(chunks), encoding="utf-8")
    print(f"Wrote pages {start_page}-{end_page} ({num_pages} total) to {output_path}")


if __name__ == "__main__":
    main()
