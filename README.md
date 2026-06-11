# 🌌 Antigravity Auto-Apply Job Assistant

An intelligent, local job application assistant designed to help B.Tech CSE (AI) graduates automate their job search and form-filling workflows. It runs completely locally to avoid rate-limiting issues, using saved responses for deterministic applications.

## 🚀 Features
*   **Local UI Console:** Clean, dark-mode glassmorphism dashboard running at `http://localhost:8000`.
*   **Job Scraper:** Searches and aggregates the latest software engineering, CSE, and developer roles (optimized for freshers).
*   **Zero-AI Deterministic Form Filler:** Playwright browser automation matches form inputs (text, dropdowns, radio groups, checkboxes) directly to your saved profile responses.
*   **Automatic Resume PDF Attachment:** Generates and uploads a compiled PDF resume.
*   **Semi-Automated Review:** Fills out the form and waits for your final confirmation to submit, keeping failed forms open for manual correction.

## 📂 Project Structure
*   `index.html` / `style.css` / `app.js` — Frontend dashboard console.
*   `server.py` — Local HTTP server.
*   `autofill_applier.py` — Playwright autofill automation engine.
*   `job_scraper.py` — Job board scraper script.
*   `profile.json` — Your structured candidate data and saved custom responses.

## 🛠️ Setup & Running

1. **Install Dependencies:**
   ```bash
   pip install playwright reportlab
   playwright install chromium
   ```

2. **Run the Dashboard Server:**
   ```bash
   python server.py
   ```
   Access the dashboard in your browser at: **[http://localhost:8000](http://localhost:8000)**

3. **Autofill Applications:**
   * Run a single application or trigger batch applications directly from the web console.
   * Review populated fields and submit.
