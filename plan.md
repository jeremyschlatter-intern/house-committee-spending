# Plan: House Committee Spending Reports Data Tool

## Problem
House committees submit monthly spending reports to the Committee on House Administration as PDFs.
These are published at https://cha.house.gov/committee-reports but are only available as PDFs,
making analysis impossible without manual work.

## Solution
Build a web application that:
1. **Scrapes** the CHA website to find all committee report PDFs
2. **Extracts** financial data from each PDF using pdfplumber
3. **Presents** the data in an interactive dashboard with:
   - Sortable spreadsheet view of all committees by month
   - Missing report alerts (which committees haven't filed)
   - Spending category breakdowns and trends
   - CSV/JSON data export

## Architecture
- **Backend**: Python script to scrape, download, and parse PDFs → JSON data files
- **Frontend**: Single-page HTML/JS app (GitHub Pages compatible) with:
  - Chart.js for visualizations
  - Client-side filtering/sorting
  - Responsive design

## Data Extracted Per Report
From the "Disbursed Summary" section:
- Personnel Compensation (MTD + YTD)
- Travel (MTD + YTD)
- Rent, Communications, Utilities (MTD + YTD)
- Printing and Reproduction (MTD + YTD)
- Other Services (MTD + YTD)
- Supplies and Materials (MTD + YTD)
- Equipment (MTD + YTD)
- Total expenditures (MTD + YTD)
- Franked Mail (MTD + YTD)
- Authorization amount

Also from payroll:
- Number of employees
- Total payroll

## Implementation Steps
1. Build HTML parser to map all committees/months/PDF URLs
2. Build PDF downloader (with caching)
3. Build PDF financial data extractor
4. Generate JSON data files
5. Build web dashboard
6. Deploy to GitHub Pages
7. Iterate with DC agent feedback

## Scope
- Start with 119th Congress (current)
- Can expand to historical data later
