import schedule
import time
import subprocess
import sys
from datetime import datetime
import pytz

def run_scraper_job():
    morocco_tz = pytz.timezone("Africa/Casablanca")
    current_time = datetime.now(morocco_tz).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{current_time} - Heure Maroc] Lancement du scraping incrémental planifié...")
    
    subprocess.run([sys.executable, "src/scraper.py"])
    print(f"[{datetime.now(morocco_tz).strftime('%H:%M:%S')}] Scraping terminé. En attente du prochain cycle.")

# Planifié deux fois par jour (10h00 et 18h00)
schedule.every().day.at("10:00").do(run_scraper_job)
schedule.every().day.at("18:00").do(run_scraper_job)

print("Automator activé (Cycles: 10:00 et 18:00 Heure locale).")
print("En attente... (Ctrl+C pour arrêter)")

while True:
    schedule.run_pending()
    time.sleep(60)