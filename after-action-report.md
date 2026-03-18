# After Action Report: House Committee Spending Dashboard

**Project:** Transform House Committee Spending Reports into Data
**Live site:** https://jeremyschlatter-intern.github.io/house-committee-spending/
**GitHub:** https://github.com/jeremyschlatter-intern/house-committee-spending
**Completed:** March 18, 2026

---

## What Was Built

An interactive web dashboard that transforms 281 PDF spending reports from 22 House committees (119th Congress) into searchable, sortable, exportable data. The tool was built entirely autonomously from project description to deployed web application.

**Key features:**
- Spreadsheet view of all committees by month with sorting, filtering, and CSV/JSON export
- Filing alert system that highlights committees with missing or late reports
- Spending visualizations: monthly trends, category breakdowns, committee comparisons
- Committee detail views with per-month category data and links to source PDFs
- Notable findings callout surfacing newsworthy anomalies automatically

## Process

### Phase 1: Discovery and Data Assessment

I started by navigating to the Committee on House Administration website (cha.house.gov/committee-reports) to understand the source material. I found that reports are organized by Congress (112th through 119th) with each committee filing monthly PDF reports.

Key discovery: The PDFs use a `/?a=Files.Serve&File_id=UUID` URL pattern. I wrote an HTML parser to extract all committee names, months, and PDF URLs. This identified **281 reports** across 22 committees for the 119th Congress alone.

### Phase 2: PDF Data Extraction

I downloaded a sample PDF (Budget Committee, February 2025) to understand the structure. Each report contains:
- Cover letter
- Summary of committee activities
- **Monthly Financial Statement** (the key data: disbursements by object class)
- Payroll certification (employee names, titles, salaries)
- Travel reports
- Detailee listings

I wrote a parser using pdfplumber to extract the Disbursed Summary data. Initial run on all 281 reports showed **only 38% success** - the majority of PDFs were scanned images with no extractable text.

### Phase 3: Overcoming the Scanned PDF Problem

**Obstacle:** 62% of committee reports (175 out of 281) were scanned images, not text-based PDFs. Traditional OCR (tesseract) produced unusable results on these landscape-oriented financial tables.

**Failed approach:** Tesseract OCR - output was garbled due to complex table layouts and landscape orientation.

**Solution:** Used the Anthropic API with Claude Haiku's vision capability. For each scanned PDF, I converted pages to images using pdftoppm, then sent them to Claude Haiku with a structured extraction prompt asking it to read the financial statement table and return JSON.

**Result:** 171 of 175 scanned PDFs successfully extracted, bringing total coverage to **98% (274 of 281 reports)**. The 4 failures were: 3 Foreign Affairs reports with non-standard formats, and 1 corrupted Intelligence Committee PDF.

### Phase 4: Web Dashboard

Built a single-page HTML/JS application with Chart.js for visualizations. Design decisions:
- **No build tools:** Pure HTML/CSS/JS for maximum simplicity and GitHub Pages compatibility
- **Client-side rendering:** All data loaded as JSON, all filtering/sorting happens in the browser
- **Six tabs:** Overview, Spreadsheet, Charts, Filing Alerts, Committee Detail, About

### Phase 5: DC Expert Review and Iteration

I created a simulated DC reviewer (playing the role of Daniel Schuman, a legislative transparency expert) who provided detailed feedback. Major issues identified and fixed:

1. **Misleading timestamps:** The "Last updated" field was using `new Date()` (browser time), making stale data look current. Fixed to show the actual data collection date.

2. **Hardcoded date ceiling:** The filing alert logic had `const maxM = y === 2026 ? 2 : 12` hardcoded. Fixed to dynamically calculate expected months from the data itself.

3. **Committee names:** "China" was imprecise (official name: Select Committee on the CCP). "Oversight and Government Reform" was the 118th Congress name; updated to "Oversight and Accountability" for the 119th.

4. **Missing methodology:** No explanation of what MTD/YTD mean, what the categories include, or how the data was extracted. Added comprehensive About tab.

5. **Consecutive gap detection:** The Rules Committee had 5 consecutive months missing, but the alert system treated it the same as 5 scattered gaps. Added consecutive-gap highlighting.

6. **Notable Findings:** Added automatic anomaly detection on the overview to surface newsworthy items (filing gaps, spending spikes) for journalists and watchdog groups.

7. **Data quality honesty:** Added disclaimers about AI OCR accuracy, removed unreliable employee count metric, added "verify against source PDF" warnings.

## Team

This project was completed by a single Claude Code agent (Opus 4.6) working autonomously, with a simulated DC reviewer agent (Sonnet) providing domain expertise feedback. No human intervention was needed during implementation.

## Obstacles and Resolutions

| Obstacle | Resolution |
|----------|-----------|
| 62% of PDFs are scanned images | Used Claude Haiku vision API instead of OCR |
| Tesseract produced garbled output on landscape financial tables | Abandoned OCR approach entirely in favor of AI vision |
| GitHub push rejected due to API key in git history | Created clean orphan branch without key history |
| One corrupted PDF (Intelligence Committee Jan 2025) crashed the parser | Added error handling to skip corrupted files gracefully |
| OCR extraction took 30+ minutes for 175 reports | Ran as background task, built web dashboard in parallel |
| Misleading "last updated" timestamp | Changed from browser date to static data collection date |
| Committee names changed between congressional sessions | Added display name mapping for corrected names |

## What Would Make This Better

If I could contact people or had more time:

1. **Automated updates:** A GitHub Actions workflow running the scraper monthly would keep the data current. The scripts are already built for this.

2. **Budget utilization:** The authorization amounts are captured but not surfaced as a spending-vs-authorization comparison, which is the key accountability metric.

3. **Historical comparison:** The scraper already indexes the 118th Congress (501 additional reports). Processing those would enable year-over-year spending comparisons.

4. **Filing timeliness:** Tracking *when* each PDF was first posted (not just whether it exists) would reveal which committees file on time vs. late.

5. **Data validation:** Cross-checking AI-extracted figures against text-extracted figures for the same committee would improve confidence in the numbers.

## Key Metrics

- **22** committees tracked
- **281** reports indexed
- **274** reports with financial data extracted (98%)
- **7** spending categories per report
- **2** extraction methods (pdfplumber + Claude Haiku vision)
- **~3 hours** total build time
- **$0** infrastructure cost (GitHub Pages, free tier)
