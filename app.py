import streamlit as st
import pandas as pd
import subprocess
import os
import sys
import re
import unicodedata
import math
from datetime import datetime

# -----------------------------
# Page config + small CSS polish
# -----------------------------
st.set_page_config(page_title="Emploi Public - Dashboard", layout="wide")

st.markdown(
    """
    <style>
      .small-muted { color: #6b7280; font-size: 0.9rem; }
      .chip {
        display: inline-block; padding: 0.25rem 0.6rem; margin: 0.15rem 0.2rem 0 0;
        border-radius: 999px; border: 1px solid rgba(148,163,184,0.5);
        background: rgba(148,163,184,0.12); font-size: 0.85rem;
      }
      .header-card {
        padding: 0.9rem 1rem; border-radius: 16px; border: 1px solid rgba(148,163,184,0.35);
        background: rgba(148,163,184,0.10);
      }
    </style>
    """,
    unsafe_allow_html=True
)

# -----------------------------
# Constants
# -----------------------------
DATA_FILE = os.path.join("data", "concours_maroc.csv")

# -----------------------------
# French date parsing helpers
# -----------------------------
FR_MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12
}

def _strip_accents(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")

def parse_fr_datetime(x):
    if x is None:
        return pd.NaT
    x = str(x).strip()
    if x in ("", "N/A", "NA", "None", "nan"):
        return pd.NaT

    x_clean = " ".join(x.split())
    x_ascii = _strip_accents(x_clean).lower()

    # Match: "2 Mars 2026 - 15:00" or "8 Mars 2026"
    m = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})(?:\s*-\s*(\d{1,2}:\d{2}))?", x_ascii)
    if m:
        day = int(m.group(1))
        month_name = m.group(2)
        year = int(m.group(3))
        month = FR_MONTHS.get(month_name)
        if month:
            hour = 0
            minute = 0
            if m.group(4):
                hour, minute = map(int, m.group(4).split(":"))
            return pd.Timestamp(year=year, month=month, day=day, hour=hour, minute=minute)

    return pd.to_datetime(x_clean, errors="coerce", dayfirst=True)

def norm_text(s: str) -> str:
    s = s or ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s

def is_admin2_e11(grade: str) -> bool:
    t = norm_text(grade)
    ok_admin = "administrateur" in t and re.search(r"\b2(e|eme)\s+grade\b", t) is not None
    ok_ech11 = re.search(r"\bechelle\s*11\b", t) is not None
    return bool(ok_admin and ok_ech11)

def days_remaining_ceil(deadline_ts: pd.Timestamp, now_ts: pd.Timestamp) -> float:
    """
    Arrondi CEIL sur le nombre de jours restants.
    Exemple: 0.2 jour -> 1 jour. Si expiré -> négatif.
    """
    if pd.isna(deadline_ts):
        return float("nan")
    delta_sec = (deadline_ts - now_ts).total_seconds()
    if delta_sec >= 0:
        return math.ceil(delta_sec / 86400.0)
    # expiré
    return math.floor(delta_sec / 86400.0)

# -----------------------------
# Data loading
# -----------------------------
@st.cache_data(ttl=600)
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE, encoding="utf-8-sig", keep_default_na=False)
    return pd.DataFrame()

def file_last_modified(path: str):
    try:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "N/A"

df = load_data()

expected_cols = [
    "Administration", "Grade", "Statut", "Code du Concours", "Lien",
    "Date de publication", "Délai de dépôt", "Date du concours",
    "Nombre de postes", "Type de dépôt", "Spécialité"
]
for c in expected_cols:
    if c not in df.columns:
        df[c] = ""

# ✅ Remplacer les colonnes dates texte par des datetime (pas de colonnes dt séparées)
if not df.empty:
    df["Date de publication"] = df["Date de publication"].apply(parse_fr_datetime)
    df["Délai de dépôt"] = df["Délai de dépôt"].apply(parse_fr_datetime)
    df["Date du concours"] = df["Date du concours"].apply(parse_fr_datetime)
    df["Nombre de postes"] = pd.to_numeric(df["Nombre de postes"], errors="coerce")

# -----------------------------
# Header
# -----------------------------
left, mid, right = st.columns([3, 2, 2], vertical_alignment="center")

with left:
    st.markdown(
        """
        <div class="header-card">
          <div style="font-size:1.5rem; font-weight:700;">🇲🇦 Emploi Public — Dashboard</div>
          <div class="small-muted">Filtres + alertes + export (incrémental)</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with mid:
    last_refresh = file_last_modified(DATA_FILE) if os.path.exists(DATA_FILE) else "N/A"
    st.markdown(
        f"<div class='small-muted'>Dernière mise à jour fichier : <b>{last_refresh}</b></div>",
        unsafe_allow_html=True
    )

with right:
    if st.button("🔄 Lancer la mise à jour (scraper)", use_container_width=True):
        with st.spinner("Scraping en cours..."):
            subprocess.run([sys.executable, "src/scraper.py"])
            st.cache_data.clear()
            df = load_data()
            for c in expected_cols:
                if c not in df.columns:
                    df[c] = ""
            if not df.empty:
                df["Date de publication"] = df["Date de publication"].apply(parse_fr_datetime)
                df["Délai de dépôt"] = df["Délai de dépôt"].apply(parse_fr_datetime)
                df["Date du concours"] = df["Date du concours"].apply(parse_fr_datetime)
                df["Nombre de postes"] = pd.to_numeric(df["Nombre de postes"], errors="coerce")
        st.success("Mise à jour terminée ✅")

st.divider()

# -----------------------------
# Sidebar filters
# -----------------------------
with st.sidebar:
    st.header("🔎 Filtres")

    if df.empty:
        st.info("Aucune donnée. Lance d'abord une mise à jour.")
        selected_admins = []
        selected_statuts = []
        selected_grade = "Tous"
        q = ""
        regex_specialite = ""
        pub_range = depot_range = concours_range = None
        only_admin2 = False
        postes_range = None
        sort_label = "Délai de dépôt"
        sort_desc = False
    else:
        admins = sorted([a for a in df["Administration"].dropna().unique() if str(a).strip() != ""])
        statuts = sorted([s for s in df["Statut"].dropna().unique() if str(s).strip() != ""])
        grades = sorted([g for g in df["Grade"].dropna().unique() if str(g).strip() != ""])
        grade_choices = ["Tous"] + grades

        selected_admins = st.multiselect("Administration", admins, default=[])
        selected_statuts = st.multiselect("Statut", statuts, default=[])

        # ✅ filtre grade en liste déroulante
        selected_grade = st.selectbox("Grade", grade_choices, index=0)

        st.subheader("Recherche")
        q = st.text_input("Mot-clé (Grade / Code / Admin)")

        # ✅ regex sur Spécialité
        regex_specialite = st.text_input("Regex Spécialité (ex: Data|Finance|Informatique)")

        st.subheader("Dates")
        pub_range = depot_range = concours_range = None

        if df["Date de publication"].notna().any():
            dmin = df["Date de publication"].min()
            dmax = df["Date de publication"].max()
            pub_range = st.date_input("Publication", (dmin.date(), dmax.date()))

        if df["Délai de dépôt"].notna().any():
            dmin = df["Délai de dépôt"].min()
            dmax = df["Délai de dépôt"].max()
            depot_range = st.date_input("Délai de dépôt", (dmin.date(), dmax.date()))

        if df["Date du concours"].notna().any():
            dmin = df["Date du concours"].min()
            dmax = df["Date du concours"].max()
            concours_range = st.date_input("Date du concours", (dmin.date(), dmax.date()))

        with st.expander("⚙️ Avancé", expanded=False):
            only_admin2 = st.checkbox("Seulement : Administrateur 2ème grade — échelle 11", value=False)

            postes_range = None
            if df["Nombre de postes"].notna().any():
                pn = df["Nombre de postes"].dropna()
                minp, maxp = int(pn.min()), int(pn.max())
                postes_range = st.slider("Nombre de postes", minp, maxp, (minp, maxp))

            sort_label = st.selectbox(
                "Trier par",
                ["Délai de dépôt", "Date de publication", "Date du concours", "Nombre de postes"],
                index=0
            )
            sort_desc = st.toggle("Décroissant", value=False)

# -----------------------------
# Apply filters
# -----------------------------
filtered_df = df.copy()

if not df.empty:
    if selected_admins:
        filtered_df = filtered_df[filtered_df["Administration"].isin(selected_admins)]

    if selected_statuts:
        filtered_df = filtered_df[filtered_df["Statut"].isin(selected_statuts)]

    if selected_grade != "Tous":
        filtered_df = filtered_df[filtered_df["Grade"] == selected_grade]

    if q:
        qq = q.lower()
        filtered_df = filtered_df[
            filtered_df["Grade"].astype(str).str.lower().str.contains(qq, na=False)
            | filtered_df["Code du Concours"].astype(str).str.lower().str.contains(qq, na=False)
            | filtered_df["Administration"].astype(str).str.lower().str.contains(qq, na=False)
        ]

    if regex_specialite:
        filtered_df = filtered_df[
            filtered_df["Spécialité"].astype(str).str.contains(regex_specialite, case=False, na=False, regex=True)
        ]

    if pub_range and filtered_df["Date de publication"].notna().any():
        start, end = pub_range
        mask = (filtered_df["Date de publication"].dt.date >= start) & (filtered_df["Date de publication"].dt.date <= end)
        filtered_df = filtered_df[mask]

    if depot_range and filtered_df["Délai de dépôt"].notna().any():
        start, end = depot_range
        mask = (filtered_df["Délai de dépôt"].dt.date >= start) & (filtered_df["Délai de dépôt"].dt.date <= end)
        filtered_df = filtered_df[mask]

    if concours_range and filtered_df["Date du concours"].notna().any():
        start, end = concours_range
        mask = (filtered_df["Date du concours"].dt.date >= start) & (filtered_df["Date du concours"].dt.date <= end)
        filtered_df = filtered_df[mask]

    if only_admin2:
        filtered_df = filtered_df[filtered_df["Grade"].apply(is_admin2_e11)]

    if postes_range is not None and filtered_df["Nombre de postes"].notna().any():
        pn = filtered_df["Nombre de postes"]
        filtered_df = filtered_df[(pn >= postes_range[0]) & (pn <= postes_range[1])]

    sort_map = {
        "Date de publication": "Date de publication",
        "Délai de dépôt": "Délai de dépôt",
        "Date du concours": "Date du concours",
        "Nombre de postes": "Nombre de postes",
    }
    sort_col = sort_map.get(sort_label, "Délai de dépôt")
    if sort_col in filtered_df.columns:
        filtered_df = filtered_df.sort_values(sort_col, ascending=not sort_desc)

# -----------------------------
# KPIs (your definition)
# -----------------------------
now = pd.Timestamp.now()

if df.empty:
    st.warning("Aucune donnée trouvée. Lance la mise à jour.")
else:
    active_deadline = df["Délai de dépôt"].notna() & (df["Délai de dépôt"] >= now)
    annonces_actives = int(active_deadline.sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total en base", len(df))
    c2.metric("Administrations uniques", int(df["Administration"].nunique()))
    c3.metric("Annonces actives (dépôt non atteint)", annonces_actives)
    c4.metric("Résultats filtrés", len(filtered_df))

# -----------------------------
# Tabs
# -----------------------------
tab1, tab2, tab3 = st.tabs(["📋 Table", "📊 Timeline", "🚨 Alertes"])

with tab1:
    if df.empty:
        st.warning("Aucune donnée trouvée. Lance la mise à jour.")
    else:
        st.subheader(f"📋 Résultats ({len(filtered_df)} concours)")

        cols_default = [
            "Date de publication", "Délai de dépôt", "Date du concours",
            "Statut", "Administration", "Grade", "Spécialité",
            "Nombre de postes", "Type de dépôt", "Code du Concours", "Lien"
        ]
        cols_existing = [c for c in cols_default if c in filtered_df.columns]

        st.dataframe(
            filtered_df[cols_existing],
            use_container_width=True,
            column_config={
                "Lien": st.column_config.LinkColumn("Lien", display_text="Ouvrir"),
            }
        )

        st.divider()
        if not filtered_df.empty:
            csv_export = filtered_df[cols_existing].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                label="📥 Télécharger CSV (résultats filtrés)",
                data=csv_export,
                file_name="concours_filtrés.csv",
                mime="text/csv",
                use_container_width=True
            )

with tab2:
    if df.empty:
        st.warning("Aucune donnée trouvée. Lance la mise à jour.")
    else:
        st.subheader("📊 Publications dans le temps (selon filtre)")
        if filtered_df["Date de publication"].notna().any():
            timeline = (
                filtered_df.dropna(subset=["Date de publication"])
                .assign(day=filtered_df["Date de publication"].dt.date)
                .groupby("day")
                .size()
            )
            st.line_chart(timeline)
        else:
            st.info("Dates de publication indisponibles ou non parsées.")

with tab3:
    if df.empty:
        st.warning("Aucune donnée trouvée. Lance la mise à jour.")
    else:
        st.subheader("🚨 Alertes : Administrateur 2ème grade — Échelle 11")

        alerts_df = filtered_df.copy()
        alerts_df = alerts_df[alerts_df["Grade"].apply(is_admin2_e11)]

        only_annonce = st.toggle("Seulement statut = Annonce", value=True)
        if only_annonce and "Statut" in alerts_df.columns:
            alerts_df = alerts_df[alerts_df["Statut"] == "Annonce"]

        show_deadlines = st.toggle("Mettre en avant les dépôts proches (≤ 3 jours)", value=True)

        if alerts_df.empty:
            st.info("Aucun concours correspondant dans les résultats filtrés.")
        else:
            alerts_df = alerts_df.copy()
            alerts_df["Jours restants (dépôt)"] = alerts_df["Délai de dépôt"].apply(lambda x: days_remaining_ceil(x, now))

            if show_deadlines:
                urgent = alerts_df.dropna(subset=["Jours restants (dépôt)"])
                urgent = urgent[
                    (urgent["Jours restants (dépôt)"] <= 3)
                    & (urgent["Jours restants (dépôt)"] >= 0)
                ].sort_values("Jours restants (dépôt)")

                if not urgent.empty:
                    st.warning("⏳ Dépôts très proches")
                    st.dataframe(
                        urgent[[
                            "Jours restants (dépôt)", "Délai de dépôt", "Date du concours",
                            "Administration", "Grade", "Nombre de postes", "Code du Concours", "Lien"
                        ]],
                        use_container_width=True,
                        column_config={
                            "Lien": st.column_config.LinkColumn("Lien", display_text="Ouvrir"),
                        }
                    )
                    st.divider()

            st.subheader("Tous les concours Admin 2e grade — E11")
            st.dataframe(
                alerts_df[[
                    "Date de publication", "Délai de dépôt", "Date du concours",
                    "Statut", "Administration", "Grade", "Spécialité",
                    "Nombre de postes", "Type de dépôt", "Code du Concours", "Lien"
                ]],
                use_container_width=True,
                column_config={
                    "Lien": st.column_config.LinkColumn("Lien", display_text="Ouvrir"),
                }
            )