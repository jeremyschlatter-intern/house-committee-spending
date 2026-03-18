#!/usr/bin/env python3
"""
Use Claude Vision API to extract financial data from scanned committee spending PDFs.
Only processes PDFs that pdfplumber couldn't extract text from.
"""

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import anthropic

API_KEY = "REDACTED"

client = anthropic.Anthropic(api_key=API_KEY)

EXTRACTION_PROMPT = """Analyze this page from a U.S. House Committee monthly spending report PDF.

Extract the financial data from the "Monthly Financial Statement" / "Disbursed Summary" table.

Return a JSON object with this exact structure:
{
  "has_financial_data": true/false,
  "authorization": <total authorization amount or 0>,
  "categories": {
    "personnel_compensation": {"mtd": <amount>, "ytd": <amount>},
    "travel": {"mtd": <amount>, "ytd": <amount>},
    "rent_communications_utilities": {"mtd": <amount>, "ytd": <amount>},
    "printing_reproduction": {"mtd": <amount>, "ytd": <amount>},
    "other_services": {"mtd": <amount>, "ytd": <amount>},
    "supplies_materials": {"mtd": <amount>, "ytd": <amount>},
    "equipment": {"mtd": <amount>, "ytd": <amount>}
  },
  "mtd_total": <total MTD disbursed>,
  "ytd_total": <total YTD disbursed>,
  "franked_mail_mtd": <amount or 0>,
  "franked_mail_ytd": <amount or 0>
}

The categories map to object class codes:
- 11 = Personnel Compensation
- 21 = Travel
- 23 = Rent, Communications, Utilities
- 24 = Printing and Reproduction
- 25 = Other Services
- 26 = Supplies and Materials
- 31 = Equipment

MTD = Month To Date, YTD = Year To Date.

If this page does not contain a financial statement table, set has_financial_data to false and leave everything else at 0.

Return ONLY valid JSON, no other text."""


def pdf_page_to_base64(pdf_path, page_num):
    """Convert a PDF page to a base64-encoded PNG image."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            ["pdftoppm", "-png", "-r", "200", "-f", str(page_num), "-l", str(page_num),
             str(pdf_path), f"{tmpdir}/page"],
            check=True, capture_output=True,
        )
        images = list(Path(tmpdir).glob("*.png"))
        if not images:
            return None
        with open(images[0], "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")


def extract_with_vision(pdf_path, pages_to_check=None):
    """Use Claude Vision to extract financial data from a scanned PDF."""
    if pages_to_check is None:
        # Try to get page count; fall back to checking pages 1-10 on error
        try:
            import pdfplumber
            with pdfplumber.open(str(pdf_path)) as pdf:
                num_pages = len(pdf.pages)
            pages_to_check = list(range(1, min(num_pages + 1, 12)))
        except Exception:
            # Corrupted PDF - try pdftoppm directly for pages 1-10
            pages_to_check = list(range(1, 11))

    # Try sending multiple pages at once to find the financial statement
    # Start with pages most likely to have financial data
    for page_num in pages_to_check:
        img_b64 = pdf_page_to_base64(pdf_path, page_num)
        if not img_b64:
            continue

        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1500,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_b64,
                            },
                        },
                        {"type": "text", "text": EXTRACTION_PROMPT},
                    ],
                }],
            )

            text = response.content[0].text.strip()
            # Extract JSON from response
            if text.startswith("```"):
                text = re.sub(r"^```\w*\n?", "", text)
                text = re.sub(r"\n?```$", "", text)

            data = json.loads(text)
            if data.get("has_financial_data"):
                data["extraction_page"] = page_num
                return data

        except (json.JSONDecodeError, anthropic.APIError) as e:
            print(f"    Page {page_num}: {e}", file=sys.stderr)
            continue

    return None


def main():
    project_dir = Path(__file__).parent.parent
    data_dir = project_dir / "data"
    pdf_dir = project_dir / "pdfs"

    # Load existing spending data
    spending_file = data_dir / "spending_119.json"
    with open(spending_file) as f:
        all_spending = json.load(f)

    # Find reports that need OCR (no data extracted and not already vision-processed)
    needs_ocr = []
    for i, report in enumerate(all_spending):
        if (report["mtd_total"] == 0 and report["ytd_total"] == 0
                and not report.get("categories")
                and report.get("extraction_method") != "claude_vision"):
            needs_ocr.append(i)

    print(f"Found {len(needs_ocr)} reports needing OCR extraction")

    success = 0
    failures = 0

    for count, idx in enumerate(needs_ocr):
        report = all_spending[idx]
        committee = report["committee"]
        month = report["month"]
        year = report["year"]

        filename = f"119_{committee.replace(' ', '_')}_{year}_{month}.pdf"
        pdf_path = pdf_dir / filename

        if not pdf_path.exists():
            print(f"[{count+1}/{len(needs_ocr)}] {committee} {month} {year}: PDF not found")
            failures += 1
            continue

        print(f"[{count+1}/{len(needs_ocr)}] {committee} {month} {year}...", end=" ", flush=True)

        try:
            result = extract_with_vision(pdf_path)
        except Exception as e:
            print(f"ERROR: {e}")
            failures += 1
            continue

        if result and result.get("has_financial_data"):
            report["categories"] = result.get("categories", {})
            report["mtd_total"] = result.get("mtd_total", 0)
            report["ytd_total"] = result.get("ytd_total", 0)
            report["franked_mail_mtd"] = result.get("franked_mail_mtd", 0)
            report["franked_mail_ytd"] = result.get("franked_mail_ytd", 0)
            report["authorization"] = result.get("authorization", 0)
            report["extraction_method"] = "claude_vision"
            report["extraction_page"] = result.get("extraction_page", 0)
            mtd = report["mtd_total"]
            ytd = report["ytd_total"]
            print(f"OK MTD=${mtd:,.0f} YTD=${ytd:,.0f}")
            success += 1
        else:
            print("no financial data found")
            failures += 1

        time.sleep(0.5)  # Rate limit

    # Save updated data
    with open(spending_file, "w") as f:
        json.dump(all_spending, f, indent=2)

    print(f"\nDone: {success} successful, {failures} failed/no data")
    print(f"Updated {spending_file}")


if __name__ == "__main__":
    main()
