import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import os
from datetime import datetime
import re
import unicodedata

class EmploiPublicCrawler:
    def __init__(self, list_url):
        self.list_url = list_url
        self.base_domain = "https://www.emploi-public.ma"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'fr-FR,fr;q=0.9'
        }

        # Paths for our incremental files
        self.data_dir = "data"
        self.links_file = f"{self.data_dir}/links.csv"
        self.data_file = f"{self.data_dir}/concours_maroc.csv"

        # Ensure data folder exists
        os.makedirs(self.data_dir, exist_ok=True)

        self.existing_links = self.load_existing_links()
        self.new_links_to_scrape = []
        self.concours_data = []

        # --- Telegram config (env vars) ---
        self.tg_token = os.getenv("TG_TOKEN", "").strip()
        self.tg_chat_id = os.getenv("TG_CHAT_ID", "").strip()

    def load_existing_links(self):
        """Loads old links so we don't scrape them again."""
        if os.path.exists(self.links_file):
            try:
                df = pd.read_csv(self.links_file)
                if 'Lien' in df.columns:
                    return set(df['Lien'].tolist())
            except Exception:
                pass
        return set()

    def fetch_html(self, url, params=None):
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"[!] Erreur de connexion vers {url}: {e}")
            return None

    def collect_job_links(self, max_pages):
        print(f"\n--- ÉTAPE 1 : Collecte incrémentale (Max {max_pages} pages) ---")

        for page in range(1, max_pages + 1):
            print(f"[*] Analyse de la page liste {page}...")
            html = self.fetch_html(self.list_url, params={'page': page})

            if not html:
                continue

            # SLICING: Stop parsing at the pagination comment
            # We build the marker in two parts so it doesn't get hidden by the browser!
            marker = "<" + "!-- END.P A G I N A T I O N --" + ">"
            if marker in html:
                html = html.split(marker)[0]

            soup = BeautifulSoup(html, 'html.parser')
            link_tags = soup.select('a[href*="/fr/concours/details/"]')

            for tag in link_tags:
                href = tag.get('href')
                if href:
                    full_link = f"{self.base_domain}{href}"
                    # Cross-check to only keep NEW links
                    if full_link not in self.existing_links and full_link not in self.new_links_to_scrape:
                        self.new_links_to_scrape.append(full_link)

            time.sleep(random.uniform(1.5, 3.0))

        print(f"[+] {len(self.new_links_to_scrape)} NOUVEAUX liens détectés sur {max_pages} pages.")

    def scrape_detail_page(self, url):
        html = self.fetch_html(url)
        if not html:
            return

        soup = BeautifulSoup(html, "html.parser")

        try:
            # 1) Title & Administration
            title_tag = soup.select_one(".block-banner h1")
            if title_tag and title_tag.span:
                title_tag.span.decompose()
            titre = title_tag.get_text(" ", strip=True) if title_tag else "N/A"

            admin_tag = soup.find(
                lambda tag: tag.name == "h3"
                and "h4" in (tag.get("class") or [])
                and "Administration qui recrute" in tag.get_text(" ", strip=True)
            )
            if admin_tag and admin_tag.span:
                admin_tag.span.decompose()
            administration = admin_tag.get_text(" ", strip=True) if admin_tag else "N/A"

            # 2) Statut (nav-link active)
            status_tag = soup.find("span", class_="nav-link active")
            statut = status_tag.get_text(" ", strip=True) if status_tag else "N/A"

            # 3) Deep fields (ul + headers)
            specialite = "N/A"
            type_recrutement = "N/A"
            code_concours = "N/A"

            delai_depot = "N/A"
            date_concours = "N/A"
            date_publication = "N/A"
            nombre_postes = "N/A"
            type_depot = "N/A"

            # --- FIX DATES: elles ne sont pas toujours dans le <ul>, mais souvent dans des titres (h3/h4) ---
            def _extract_header_value(label: str) -> str:
                tag = soup.find(
                    lambda t: t.name in ["h3", "h4"]
                    and label in t.get_text(" ", strip=True)
                )
                if not tag:
                    return "N/A"
                txt = tag.get_text(" ", strip=True)
                val = txt.replace(label, "", 1).strip(" :-–—\t")
                return " ".join(val.split()) if val else "N/A"

            # Variantes possibles du libellé
            delai_depot = _extract_header_value("Délai de dépôt des candidatures")
            if delai_depot == "N/A":
                delai_depot = _extract_header_value("Délai de dépôt")

            date_concours = _extract_header_value("Date du concours")
            date_publication = _extract_header_value("Date de publication")

            # --- Le reste vient généralement du <ul> (spécialité multi-lignes, postes, type dépôt, etc.) ---
            description_list = soup.select_one(".s-content-box.full ul")
            if description_list:
                for li in description_list.find_all("li"):
                    span = li.find("span")
                    if not span:
                        continue

                    label_raw = span.get_text(" ", strip=True).lower()

                    # Enlever le label puis récupérer la valeur (robuste multi-lignes / <br>)
                    span.decompose()
                    value = li.get_text(" ", strip=True)
                    value = " ".join(value.split()).strip("- :")

                    if "spécialité" in label_raw or "specialite" in label_raw:
                        specialite = value

                    elif "type de recrutement" in label_raw:
                        type_recrutement = value

                    elif "code du concours" in label_raw:
                        code_concours = value

                    elif "délai de dépôt" in label_raw or "delai de depot" in label_raw:
                        # au cas où le site met aussi la valeur dans le <ul>
                        delai_depot = value

                    elif "date du concours" in label_raw:
                        date_concours = value

                    elif "date de publication" in label_raw:
                        date_publication = value

                    elif "nombre de postes" in label_raw:
                        m = re.search(r"\d+", value)
                        nombre_postes = int(m.group()) if m else value

                    elif "type de dépôt" in label_raw or "type de depot" in label_raw:
                        type_depot = value

            record = {
                "Date de publication": date_publication,
                "Code du Concours": code_concours,
                "Statut": statut,
                "Administration": administration,
                "Grade": titre,
                "Spécialité": specialite,
                "Nombre de postes": nombre_postes,
                "Type de Recrutement": type_recrutement,
                "Délai de dépôt": delai_depot,
                "Date du concours": date_concours,
                "Type de dépôt": type_depot,
                "Lien": url,
                "Date_Scraping": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            self.concours_data.append(record)
            self.notify_if_target(record)

        except Exception as e:
            print(f"[-] Erreur de parsing sur {url}: {e}")

    def _norm(self, s: str) -> str:
        """lowercase + remove accents + normalize spaces"""
        s = s or ""
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        s = s.lower()
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def is_target_admin2_e11(self, titre: str, statut: str) -> bool:
        t = self._norm(titre)
        st = self._norm(statut)

        # Option: ne notifier que les annonces (évite résultats/liste admis)
        if "annonce" not in st:
            return False

        # Match robuste "Administrateur 2ème grade" + "Echelle 11"
        ok_admin = "administrateur" in t and re.search(r"\b2(e|eme)\s+grade\b", t) is not None
        ok_ech11 = re.search(r"\bechelle\s*11\b", t) is not None
        return bool(ok_admin and ok_ech11)

    def send_telegram(self, message: str):
        if not (self.tg_token and self.tg_chat_id):
            return

        try:
            url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
            r = requests.post(
                url,
                data={
                    "chat_id": self.tg_chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True
                },
                timeout=20
            )
            r.raise_for_status()
        except Exception as e:
            print(f"[!] Telegram error: {e}")

    def notify_if_target(self, record: dict):
        titre = record.get("Grade", "")
        statut = record.get("Statut", "")
        if not self.is_target_admin2_e11(titre, statut):
            return

        pub = record.get("Date de publication", "N/A")
        admin = record.get("Administration", "N/A")
        code = record.get("Code du Concours", "N/A")
        postes = record.get("Nombre de postes", "N/A")
        spec = record.get("Spécialité", "N/A")
        type_depot = record.get("Type de dépôt", "N/A")
        delai = record.get("Délai de dépôt", "N/A")
        date_concours = record.get("Date du concours", "N/A")
        lien = record.get("Lien", "N/A")

        spec_line = ""
        if spec and spec != "N/A" and spec.lower() not in ["-", "—", "aucune", "non précisée", "non precisee"]:
            spec_line = f"🧩 *Spécialité* : {spec}\n"

        msg = (
            f"🆕 *Nouveau concours publié* — {pub}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Grade* : {titre}\n"
            f"🏛️ *Administration* : {admin}\n"
            f"🧾 *Code* : `{code}`\n"
            f"👥 *Postes* : {postes}\n"
            f"{spec_line}"
            f"🗂️ *Type de dépôt* : {type_depot}\n"
            f"⏳ *Délai de dépôt* : {delai}\n"
            f"🗓️ *Date du concours* : {date_concours}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 [Voir l'annonce]({lien})"
        )

        self.send_telegram(msg)

    def save_incremental_data(self):
        if not self.new_links_to_scrape or not self.concours_data:
            print("[-] Aucune nouvelle donnée à sauvegarder.")
            return

        links_df = pd.DataFrame(self.new_links_to_scrape, columns=['Lien'])
        links_file_exists = os.path.isfile(self.links_file)
        links_df.to_csv(self.links_file, mode='a', index=False, header=not links_file_exists)

        data_df = pd.DataFrame(self.concours_data)
        data_file_exists = os.path.isfile(self.data_file)
        data_df.to_csv(self.data_file, mode='a', index=False, encoding='utf-8-sig', header=not data_file_exists)

        print(f"\n[+] Succès ! {len(self.concours_data)} nouvelles offres ajoutées à la base de données.")

    def run(self, max_pages=3):
        # Mise à jour: 3 pages (ou max_pages), Bootstrap (première exécution): 25 pages
        pages_to_collect = 25 if len(self.existing_links) == 0 else max_pages

        self.collect_job_links(pages_to_collect)

        if self.new_links_to_scrape:
            print(f"\n--- ÉTAPE 2 : Scraping profond de {len(self.new_links_to_scrape)} NOUVELLES pages ---")
            for index, link in enumerate(self.new_links_to_scrape, start=1):
                print(f"[{index}/{len(self.new_links_to_scrape)}] Extraction: {link.split('/')[-1]}")
                self.scrape_detail_page(link)
                time.sleep(random.uniform(2.0, 4.0))

            self.save_incremental_data()
        else:
            print("\n[+] Base de données déjà à jour. Aucun nouveau concours détecté.")

if __name__ == "__main__":
    TARGET_LIST_URL = "https://www.emploi-public.ma/fr/concours-liste"
    crawler = EmploiPublicCrawler(list_url=TARGET_LIST_URL)
    crawler.run(max_pages=3)