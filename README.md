# Antigravity — Auto-Apply Job Assistant

A local web app that **scrapes real Greenhouse & Lever job listings**, matches them against your profile, and **auto-fills + submits applications** using Playwright — with Gemini 2.5 Pro as the AI fallback for unknown questions.

## Features

- Scrapes live job boards from SimplifyJobs and speedyapply (2026 New Grad / Intern lists)
- Separates Global and India-based jobs into dedicated tabs
- Skill-match scoring with resume profile comparison
- Playwright-powered browser automation that auto-fills every field including:
  - Personal info, resume upload, LinkedIn/GitHub links
  - EEO / diversity questions, work authorization, salary expectations
  - Custom open-ended questions via Gemini 2.5 Pro AI fallback
- Saves AI answers back to your profile for future reuse (learns over time)
- Batch apply up to 10 jobs at once
- Web dashboard to track Applied / Pending / Review Required status

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/harishvarri/auto-apply.git
cd auto-apply
pip install -r requirements.txt
playwright install chromium
```

### 2. Set up your profile

```bash
cp profile.example.json profile.json
```

Edit `profile.json` with your real details — name, email, phone, LinkedIn, GitHub, resume PDF path, and all custom responses.

### 3. Set your Gemini API key

The app uses **Gemini 2.5 Pro** for AI-powered form filling. Get a free key at [Google AI Studio](https://aistudio.google.com).

**Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY = "your-api-key-here"
```

**Linux/macOS:**
```bash
export GEMINI_API_KEY="your-api-key-here"
```

Or create a `.env` file (never commit it):
```
GEMINI_API_KEY=your-api-key-here
```

### 4. Start the server

```bash
python server.py
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

### 5. Scrape jobs

Click **Refresh Jobs** in the sidebar, or run manually:
```bash
python job_scraper.py
```

This fetches live Greenhouse and Lever listings from GitHub job boards and saves them to `jobs_database.json`.

### 6. Apply

- Click any job → click **Auto-Fill in Browser** to open Playwright and fill the form
- Or click **Apply Batch (Top 10)** to queue the top-matched pending jobs

## File Structure

```
auto-apply/
├── server.py               # Python HTTP server (API + static files)
├── app.js                  # Frontend JavaScript
├── index.html              # Main UI
├── style.css               # Styles
├── job_scraper.py          # Scrapes Greenhouse/Lever jobs from GitHub boards
├── autofill_applier.py     # Playwright automation + Gemini AI filling
├── generate_resume_pdf.py  # Generates a PDF resume from profile.json
├── profile.example.json    # Template — copy to profile.json and fill in your data
├── requirements.txt        # Python dependencies
└── README.md
```

## Notes

- `profile.json` and `jobs_database.json` are gitignored — they contain personal data and machine-generated content
- The Playwright browser profile (`playwright_user_data/`) is also gitignored; it persists your login sessions between runs
- The app runs fully locally — no cloud servers, no data sent anywhere except the Gemini API for unknown form fields
