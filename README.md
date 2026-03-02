Status: stable (v1.0.0)

# 🇲🇦 Emploi Public — Automated Incremental Crawler & Dashboard

## Overview
This project is an automated web scraping pipeline and an interactive dashboard that collect, structure, and explore Moroccan public-sector competitions and job postings from `emploi-public.ma`.

The tool is designed as an **incremental crawler**: it detects and processes **only newly published postings**, stores them in a clean dataset, and optionally sends Telegram alerts for targeted opportunities.

---

## Key Features
- **Incremental crawling (delta load)**  
  Keeps a persistent URL ledger (`data/links.csv`) and scrapes only new postings.
- **Deep scraping (detail pages)**  
  Extracts key fields from each posting (administration, grade, status, deadlines, etc.).
- **Automation (scheduled runs)**  
  Runs twice a day (10:00 and 18:00, Morocco timezone) via `src/automator.py`.
- **Streamlit dashboard**  
  Search, filters, and CSV export via `app.py`.
- **Optional Telegram alerts**  
  Sends a notification when a posting matches a target rule (customizable).
- **Responsible scraping**  
  Randomized delays, request headers, and incremental logic to minimize server load.

---

## Project Structure
```text
emploi-public-scraper/
│
├── data/                       # Local storage (recommended to keep out of Git)
│   ├── concours_maroc.csv      # Main dataset (append-only)
│   └── links.csv               # URL ledger (crawl state)
│
├── src/
│   ├── scraper.py              # Incremental crawler + deep scraping + Telegram alerts (optional)
│   └── automator.py            # Scheduler (10:00 / 18:00, Africa/Casablanca)
│
├── app.py                      # Streamlit dashboard (search / filters / export + manual update button)
├── requirements.txt            # Dependencies
└── .gitignore                  # Exclusions (data/, caches, secrets, etc.)

## Create and activate a virtual environment - recommended (Windows)
```cmd
python -m venv .venv
.\.venv\Scripts\activate
```

Install dependencies:
```cmd
pip install -r requirements.txt
```

## Usage
A) Run the scraper once (manual run)

This runs the incremental pipeline:
- scans listing pages,
- deep-scrapes only new detail pages,
- appends new rows to data/concours_maroc.csv,
- appends new URLs to data/links.csv.
```cmd
python src/scraper.py
```

B) Run the automation scheduler
```cmd
python src/automator.py
```
Stop with Ctrl + C.

C) Launch the Streamlit Dashboard
```cmd
streamlit run app.py
```

## Telegram Alerts (Optional)
What it does

If Telegram credentials are provided, the scraper can send alerts for postings matching a target rule.
The rule is implemented in src/scraper.py (e.g., a function like is_target_admin2_e11()), and you can customize it to match your own keywords.

1) Set Telegram credentials as environment variables

You need:
- TG_TOKEN (your bot token)
- TG_CHAT_ID (the chat id where messages will be delivered)

Windows (PowerShell) — for the current terminal session
```cmd
$env:TG_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
$env:TG_CHAT_ID="YOUR_CHAT_ID"
python src/scraper.py
```
If you do NOT set these variables, Telegram alerts are disabled (the scraper runs normally).

2) Make variables persistent (Windows)

If you want them to persist across terminals (Windows):
```cmd
setx TG_TOKEN "YOUR_TELEGRAM_BOT_TOKEN"
setx TG_CHAT_ID "YOUR_CHAT_ID"
```
Then open a new terminal.

3) How to find your TG_CHAT_ID

Start a chat with your bot and send any message (e.g., "test").

Then open the Telegram API endpoint below and read the chat.id field:

https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates

## Data Output

- data/links.csv
Persistent crawl state (already seen URLs).

- data/concours_maroc.csv
Append-only dataset (Excel-friendly encoding: utf-8-sig).

## Ethics & Disclaimer

This project is developed for educational purposes. It only accesses publicly available pages and uses responsible scraping practices:

- incremental updates (reduced traffic),
- randomized delays,
- request headers,
- and a compliance mindset (robots.txt / terms of use).

Use it respectfully and avoid overwhelming servers.
