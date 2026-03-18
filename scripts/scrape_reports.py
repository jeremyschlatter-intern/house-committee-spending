#!/usr/bin/env python3
"""
Scrape the House Administration Committee website to build a mapping of
committee -> month -> PDF URL for all monthly spending reports.
"""

import json
import re
import sys
import time
from html.parser import HTMLParser
from urllib.request import urlopen, Request
from pathlib import Path

BASE_URL = "https://cha.house.gov"

CONGRESS_PAGES = {
    "119": "/119th-congressional-reports",
    "118": "/118th-congressional-reports",
}


class ReportParser(HTMLParser):
    """Parse the CHA reports page to extract committee names and PDF links."""

    def __init__(self):
        super().__init__()
        self.in_main = False
        self.committees = []
        self.current_committee = None
        self.current_links = []
        self.capture_text = False
        self.current_text = ""
        self.in_heading = False
        self.current_href = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "main":
            self.in_main = True
        if self.in_main and tag in ("h2", "h3", "h4", "strong", "b"):
            self.in_heading = True
            self.current_text = ""
        if self.in_main and tag == "a":
            href = attrs_dict.get("href", "")
            if "Files.Serve" in href:
                self.capture_text = True
                self.current_text = ""
                self.current_href = href

    def handle_endtag(self, tag):
        if tag == "main":
            self.in_main = False
            # Save last committee
            if self.current_committee and self.current_links:
                self.committees.append(
                    (self.current_committee, list(self.current_links))
                )
        if self.in_heading and tag in ("h2", "h3", "h4", "strong", "b"):
            self.in_heading = False
            text = self.current_text.strip()
            months = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            ]
            if (
                text
                and not any(m in text for m in months)
                and "Congress" not in text
                and "ECMO" not in text
                and len(text) > 2
            ):
                if self.current_committee and self.current_links:
                    self.committees.append(
                        (self.current_committee, list(self.current_links))
                    )
                self.current_committee = text
                self.current_links = []
        if self.capture_text and tag == "a":
            self.capture_text = False
            link_text = self.current_text.strip()
            self.current_links.append((link_text, self.current_href))

    def handle_data(self, data):
        if self.in_heading or self.capture_text:
            self.current_text += data


def parse_month_text(text):
    """Parse 'January 2025 - (2.8 MBs)' into (month, year)."""
    match = re.match(r"(\w+)\s+(\d{4})", text)
    if match:
        return match.group(1), int(match.group(2))
    return None, None


def clean_committee_name(name):
    """Remove congress number suffix like '119' from committee names."""
    return re.sub(r"\s+\d{3}$", "", name).strip()


def fetch_page(url):
    """Fetch a web page and return its HTML."""
    req = Request(url, headers={"User-Agent": "HouseCommitteeSpendingTracker/1.0"})
    with urlopen(req) as resp:
        return resp.read().decode("utf-8")


def scrape_congress(congress_num, path):
    """Scrape all reports for a given congress."""
    url = f"{BASE_URL}{path}"
    print(f"Fetching {url}...")
    html = fetch_page(url)

    parser = ReportParser()
    parser.feed(html)

    reports = []
    for committee_raw, links in parser.committees:
        committee = clean_committee_name(committee_raw)
        for link_text, href in links:
            month_name, year = parse_month_text(link_text)
            if month_name and year:
                file_id_match = re.search(r"File_id=([A-Fa-f0-9-]+)", href)
                file_id = file_id_match.group(1) if file_id_match else None
                pdf_url = f"{BASE_URL}{href}" if href.startswith("/") else href
                reports.append({
                    "congress": int(congress_num),
                    "committee": committee,
                    "month": month_name,
                    "year": year,
                    "file_id": file_id,
                    "pdf_url": pdf_url,
                    "link_text": link_text.strip(),
                })

    return reports


def main():
    project_dir = Path(__file__).parent.parent
    data_dir = project_dir / "data"
    data_dir.mkdir(exist_ok=True)

    all_reports = []
    for congress_num, path in CONGRESS_PAGES.items():
        reports = scrape_congress(congress_num, path)
        all_reports.extend(reports)
        print(f"  Found {len(reports)} reports for {congress_num}th Congress")
        time.sleep(1)

    output_file = data_dir / "report_index.json"
    with open(output_file, "w") as f:
        json.dump(all_reports, f, indent=2)

    print(f"\nTotal: {len(all_reports)} reports indexed")
    print(f"Saved to {output_file}")

    # Print summary
    committees = set(r["committee"] for r in all_reports if r["congress"] == 119)
    print(f"\n119th Congress committees ({len(committees)}):")
    for c in sorted(committees):
        count = sum(1 for r in all_reports if r["committee"] == c and r["congress"] == 119)
        print(f"  {c}: {count} reports")


if __name__ == "__main__":
    main()
