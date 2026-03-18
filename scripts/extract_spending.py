#!/usr/bin/env python3
"""
Download House Committee spending report PDFs and extract financial data.
Produces structured JSON with spending categories by committee and month.
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.request import urlopen, Request

import pdfplumber


def download_pdf(url, dest_path):
    """Download a PDF file if not already cached."""
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return True
    try:
        req = Request(url, headers={"User-Agent": "HouseCommitteeSpendingTracker/1.0"})
        with urlopen(req, timeout=30) as resp:
            data = resp.read()
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"  ERROR downloading {url}: {e}", file=sys.stderr)
        return False


def parse_dollar_amount(s):
    """Parse a dollar amount string like '1,234.56' or '(1,234.56)' into a float."""
    if not s:
        return 0.0
    s = s.strip()
    negative = s.startswith("(") and s.endswith(")")
    s = s.replace("(", "").replace(")", "").replace(",", "").replace("$", "").strip()
    try:
        val = float(s)
        return -val if negative else val
    except ValueError:
        return 0.0


OBJECT_CLASS_MAP = {
    "11": "personnel_compensation",
    "21": "travel",
    "23": "rent_communications_utilities",
    "24": "printing_reproduction",
    "25": "other_services",
    "26": "supplies_materials",
    "31": "equipment",
}


def extract_financial_data(pdf_path):
    """Extract spending data from a committee spending report PDF."""
    result = {
        "authorization": 0.0,
        "categories": {},
        "mtd_total": 0.0,
        "ytd_total": 0.0,
        "franked_mail_mtd": 0.0,
        "franked_mail_ytd": 0.0,
        "employee_count": 0,
        "total_payroll": 0.0,
        "extraction_method": "disbursed_summary",
    }

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

            # Extract from Disbursed Summary pages
            result.update(extract_disbursed_summary(full_text))

            # Extract employee count and payroll from payroll pages
            payroll_data = extract_payroll_data(full_text)
            result["employee_count"] = payroll_data["employee_count"]
            result["total_payroll"] = payroll_data["total_payroll"]

            # Extract authorization from Budget to Actual if present
            auth = extract_authorization(full_text)
            if auth > 0:
                result["authorization"] = auth

    except Exception as e:
        result["error"] = str(e)

    return result


def extract_disbursed_summary(text):
    """Extract MTD/YTD totals from the Disbursed Summary section."""
    data = {
        "categories": {},
        "mtd_total": 0.0,
        "ytd_total": 0.0,
        "franked_mail_mtd": 0.0,
        "franked_mail_ytd": 0.0,
    }

    lines = text.split("\n")

    # Track which object class section we're in
    current_class = None
    in_franked = False
    found_general_total = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect object class headers
        for code, name in OBJECT_CLASS_MAP.items():
            # Match patterns like "11 Personnel Compensation" or just the object class at start
            if re.match(rf"^{code}\s+\w", stripped):
                current_class = name
                in_franked = False
                break

        # Detect Franked Mail section
        if "Franked Mail" in stripped or "FM Franked Mail" in stripped:
            in_franked = True
            current_class = None

        # Look for "Total" lines with dollar amounts
        # Pattern: "Total" followed by one or two dollar amounts
        total_match = re.match(
            r"Total\s+([\d,]+\.?\d*)\s*([\d,]+\.?\d*)?",
            stripped,
        )
        if not total_match:
            # Try pattern where Total has numbers right next to it (no space separation)
            total_match = re.match(
                r"Total\s+([\d,]+\.\d{2})([\d,]+\.\d{2})",
                stripped,
            )

        if total_match:
            mtd = parse_dollar_amount(total_match.group(1))
            ytd = parse_dollar_amount(total_match.group(2)) if total_match.group(2) else mtd

            if in_franked:
                data["franked_mail_mtd"] = mtd
                data["franked_mail_ytd"] = ytd
            elif current_class:
                data["categories"][current_class] = {
                    "mtd": mtd,
                    "ytd": ytd,
                }
                # The last non-franked Total before franked mail is the grand total
                if not found_general_total:
                    data["mtd_total"] = mtd
                    data["ytd_total"] = ytd
                current_class = None

    # Find the actual grand total - it's the Total line right before Franked Mail section
    # Re-scan to find the grand total more accurately
    in_expenditures = False
    last_total_mtd = 0.0
    last_total_ytd = 0.0

    for i, line in enumerate(lines):
        stripped = line.strip()

        if "Disbursed Summary" in stripped:
            in_expenditures = True

        if in_expenditures and "Franked Mail" in stripped:
            data["mtd_total"] = last_total_mtd
            data["ytd_total"] = last_total_ytd
            break

        if in_expenditures:
            total_match = re.match(r"Total\s+([\d,]+\.?\d*)\s*([\d,]+\.?\d*)?", stripped)
            if not total_match:
                total_match = re.match(r"Total\s+([\d,]+\.\d{2})([\d,]+\.\d{2})", stripped)
            if total_match:
                last_total_mtd = parse_dollar_amount(total_match.group(1))
                last_total_ytd = parse_dollar_amount(total_match.group(2)) if total_match.group(2) else last_total_mtd

    # If we didn't find a separate grand total, sum the categories
    if data["mtd_total"] == 0.0 and data["categories"]:
        data["mtd_total"] = sum(c.get("mtd", 0) for c in data["categories"].values())
        data["ytd_total"] = sum(c.get("ytd", 0) for c in data["categories"].values())

    return data


def extract_authorization(text):
    """Extract the authorization amount from Budget to Actual section."""
    # Look for "** Authorization" followed by an amount
    match = re.search(r"\*\*\s*Authorization\s+([\d,]+\.?\d*)", text)
    if match:
        return parse_dollar_amount(match.group(1))

    # Also try pattern in Budget to Actual tables
    match = re.search(r"Authorization.*?(\d[\d,]*\.\d{2})", text)
    if match:
        return parse_dollar_amount(match.group(1))

    return 0.0


def extract_payroll_data(text):
    """Extract employee count and total payroll from payroll certification pages."""
    employee_count = 0
    total_payroll = 0.0

    # Count employees by finding lines with gross pay amounts in payroll section
    in_payroll = False
    for line in text.split("\n"):
        if "PAYROLL CERTIFICATION" in line:
            in_payroll = True
            continue
        if in_payroll:
            # Employee lines have a name in caps followed by a dollar amount
            pay_match = re.search(r"(\d[\d,]*\.\d{2})\s+\d{2}/\d{2}/\d{4}", line)
            if pay_match:
                amount = parse_dollar_amount(pay_match.group(1))
                if amount > 0:
                    employee_count += 1
                    total_payroll += amount

    return {"employee_count": employee_count, "total_payroll": total_payroll}


def month_to_num(month_name):
    """Convert month name to number."""
    months = {
        "January": 1, "February": 2, "March": 3, "April": 4,
        "May": 5, "June": 6, "July": 7, "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12,
    }
    return months.get(month_name, 0)


def main():
    project_dir = Path(__file__).parent.parent
    data_dir = project_dir / "data"
    pdf_dir = project_dir / "pdfs"
    pdf_dir.mkdir(exist_ok=True)

    # Load report index
    index_file = data_dir / "report_index.json"
    with open(index_file) as f:
        reports = json.load(f)

    # Filter to 119th Congress for now
    congress_filter = int(sys.argv[1]) if len(sys.argv) > 1 else 119
    reports = [r for r in reports if r["congress"] == congress_filter]
    print(f"Processing {len(reports)} reports for {congress_filter}th Congress...")

    all_spending = []
    errors = []

    for i, report in enumerate(reports):
        committee = report["committee"]
        month = report["month"]
        year = report["year"]
        file_id = report["file_id"]

        filename = f"{congress_filter}_{committee.replace(' ', '_')}_{year}_{month}.pdf"
        pdf_path = pdf_dir / filename

        print(f"[{i+1}/{len(reports)}] {committee} - {month} {year}...", end=" ")

        # Download
        if not download_pdf(report["pdf_url"], pdf_path):
            errors.append({"report": report, "error": "download_failed"})
            print("DOWNLOAD FAILED")
            continue

        # Extract
        spending = extract_financial_data(pdf_path)
        spending["committee"] = committee
        spending["month"] = month
        spending["year"] = year
        spending["month_num"] = month_to_num(month)
        spending["congress"] = congress_filter
        spending["file_id"] = file_id
        spending["pdf_url"] = report["pdf_url"]

        if "error" in spending:
            errors.append({"report": report, "error": spending["error"]})
            print(f"PARSE ERROR: {spending['error']}")
        else:
            mtd = spending["mtd_total"]
            ytd = spending["ytd_total"]
            cats = len(spending["categories"])
            print(f"MTD=${mtd:,.0f} YTD=${ytd:,.0f} ({cats} categories)")

        all_spending.append(spending)
        time.sleep(0.3)  # Be polite to the server

    # Save results
    output_file = data_dir / f"spending_{congress_filter}.json"
    with open(output_file, "w") as f:
        json.dump(all_spending, f, indent=2)

    print(f"\nExtracted data from {len(all_spending)} reports")
    print(f"Errors: {len(errors)}")
    print(f"Saved to {output_file}")

    if errors:
        error_file = data_dir / f"errors_{congress_filter}.json"
        with open(error_file, "w") as f:
            json.dump(errors, f, indent=2)
        print(f"Error details saved to {error_file}")


if __name__ == "__main__":
    main()
