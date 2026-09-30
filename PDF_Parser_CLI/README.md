# PDF Parser CLI

A small, dependency-light command-line tool to extract the text of a page
range from a PDF into a plain-text file.

## What it does

Given a PDF and a 1-indexed, inclusive page range, it extracts each page's
text via [`pypdf`](https://pypi.org/project/pypdf/) and writes it to a
`.txt` file, with each page separated by a `----- Page N -----` header.

## Requirements

- Python 3.9+
- [`pypdf`](https://pypi.org/project/pypdf/)

Install the dependency:

```
pip install pypdf
```

> **Note**: if `pip install` fails with `Could not find a suitable TLS CA
> certificate bundle`, your `CURL_CA_BUNDLE` environment variable may be
> pointing at a nonexistent file. Work around it for a single command with:
> ```powershell
> $env:CURL_CA_BUNDLE=""; pip install pypdf
> ```

## Usage

```
python extract_pdf_pages.py <pdf_path> <start_page> <end_page> [output_path]
```

- `pdf_path` — path to the source PDF.
- `start_page` / `end_page` — 1-indexed, inclusive page range. Validated
  against the PDF's actual page count.
- `output_path` (optional) — where to write the extracted text. Defaults to
  `<pdf_stem>_p<start_page>-<end_page>.txt` next to the source PDF.

### Example

```
python extract_pdf_pages.py "input_test/Master-En-Robotica-Y-Sistemas-De-Control-Ceupe.pdf" 15 36
```

Writes `Master-En-Robotica-Y-Sistemas-De-Control-Ceupe_p15-36.txt` next to
the source PDF, containing the text of pages 15 through 36.

## Output format

```
----- Page 15 -----
<extracted text of page 15>

----- Page 16 -----
<extracted text of page 16>

...
```
