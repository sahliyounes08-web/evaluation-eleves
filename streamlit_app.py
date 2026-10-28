import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime

# ============ CONFIGURATION DE LA PAGE ============
st.set_page_config(
    page_title="Évaluation Histoire-Géo",
    page_icon="📚",
    layout="wide"
)

# ============ CONNEXION GOOGLE SHEETS ============
@st.cache_resource
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    return gspread.authorize(credentials)

@st.cache_data(ttl=300)
def load_students():
    client = get_gspread_client()
    sheet = client.open_by_key(st.secrets["spreadsheet_id"])
    worksheet = sheet.worksheet("جميع التلاميذ")
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

@st.cache_data(ttl=60) # Recharge souvent pour voir les nouvelles notes
def load_evaluations():
    client = get_gspread_client()
    sheet = client.open_by_key(st.secrets["spreadsheet_id"])
    worksheet = sheet.worksheet("Evaluation")
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def save_evaluation(rows_to_save):
    client = get_gspread_client()
    sheet = client.open_by_key(st.secrets["spreadsheet_id"])
    worksheet = sheet.worksheet("Evaluation")
    for row in rows_to_save:
        worksheet.append_row(row, value_input_option="USER_ENTERED")

# ============ INTERFACE ============
st.title("📚 Évaluation - Histoire-Géographie")
st.caption("ثانوية الفضيل الورتلاني — السنة الدراسية 2026/2027")
st.markdown("---")

# Bouton de rafraîchissement
col_r1, col_r2 = st.columns([1, 4])
with col_r1:
    if st.button("🔄 Rafraîchir"):
        st.cache_data.clear()
        st.rerun()

# Chargement des données
try:
    df_students = load_students()
    df_evals = load_evaluations()
except Exception as e:
    st.error("⚠️ Impossible de charger les données.")
    st.error(f"Détail technique : {e}")
    st.info("Vérifiez que les secrets sont bien configurés.")
    st.stop()

# Sélection de la classe
classes = sorted(df_students["القسم"].unique().tolist())
classe_choisie = st.selectbox("🎓 Sélectionnez une classe :", classes)

df_classe = df_students[df_students["القسم"] == classe_choisie].copy()
st.success(f"**{len(df_classe)} élèves** dans la classe « {classe_choisie} »")

# ============ TABLEAU DE BORD (NOUVEAU) ============
st.markdown("### 📊 Tableau de bord de la classe")

# On filtre les évaluations de la classe choisie
if not df_evals.empty and "Classe" in df_evals.columns:
    df_evals_classe = df_evals[df_evals["Classe"] == classe_choisie].copy()
else:
    df_evals_classe = pd.DataFrame()

if df_evals_classe.empty:
    st.info("Aucune évaluation enregistrée pour cette classe pour le moment. Le tableau de bord s'affichera dès que vous aurez enregistré des notes.")
else:
    # On convertit les colonnes en nombres pour faire les calculs
    colonnes_numeriques = ["Presence", "Total_Assiduite", "Moyenne"]
    for col in colonnes_numeriques:
        if col in df_evals_classe.columns:
            df_evals_classe[col] = pd.to_numeric(df_evals_classe[col], errors='coerce').fillna(0)

    # On garde la DERNIÈRE évaluation de chaque élève
    df_derniere_eval = df_evals_classe.sort_values("Date").groupby("ID_Eleve").last().reset_index()

    # Calculs des statistiques
    total_eleves_notes = len(df_derniere_eval)
    moyenne_classe = df_derniere_eval["Moyenne"].mean()
    
    # Taux de présence (basé sur une note de présence sur 2)
    # Si la présence est à 2, l'élève est considéré présent.
    presents = len(df_derniere_eval[df_derniere_eval["Presence"] >= 1.5])
    taux_presence = (presents / total_eleves_notes) * 100 if total_eleves_notes > 0 else 0

    # Élèves en difficulté (moyenne < 10)
    eleves_difficulte = df_derniere_eval[df_derniere_eval["Moyenne"] < 10]

    # Affichage des métriques
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Élèves évalués", f"{total_eleves_notes} / {len(df_classe)}")
    col2.metric("Moyenne de la classe", f"{moyenne_classe:.2f} / 20")
    col3.metric("Taux de présence", f"{taux_presence:.1f} %")
    col4.metric("Élèves en difficulté", f"{len(eleves_difficulte)}")

    # Liste des élèves à encadrer
    if not eleves_difficulte.empty:
        with st.expander("🚨 Voir les élèves qui ont besoin d'encadrement (Moyenne < 10)"):
            df_affichage = eleves_difficulte[["Nom", "Prénom", "Moyenne", "Remarque"]].copy()
            df_affichage.columns = ["Nom", "Prénom", "Moyenne", "Remarque"]
            st.dataframe(df_affichage, use_container_width=True)

    # Graphique simple
    with st.expander("📈 Voir le graphique des moyennes"):
        st.bar_chart(df_derniere_eval.set_index("Nom")["Moyenne"])

st.markdown("---")

# ============ SAISIE DES NOTES (EXISTANT) ============
date_eval = st.date_input("📅 Date de l'évaluation", value=datetime.today())

st.markdown("### 📝 Saisie des notes")
st.caption("Notes d'assiduité sur 20 + Devoir /20 + Composition /20. La moyenne est calculée automatiquement.")

evaluations = []

for _, row in df_classe.iterrows():
    id_elev = str(row["الترتيب"])
    nom_complet = f"{row['اللقب']} {row['الاسم']}"
    
    with st.expander(f"👤 {nom_complet}"):
        col1, col2 = st.columns(2)
        with col1:
            presence = st.number_input("Présence (0-2)", 0, 2, 2, key=f"pres_{id_elev}")
            participation = st.number_input("Participation (0-3)", 0, 3, 2, key=f"part_{id_elev}")
            calme = st.number_input("Calme (0-2)", 0, 2, 2, key=f"calme_{id_elev}")
            tablier = st.number_input("Tablier (0-1)", 0, 1, 1, key=f"tab_{id_elev}")
        with col2:
            affaires = st.number_input("Affaires (0-2)", 0, 2, 2, key=f"aff_{id_elev}")
            cahier = st.number_input("Cahier (0-3)", 0, 3, 2, key=f"cah_{id_elev}")
            technologie = st.number_input("Technologie (0-2)", 0, 2, 2, key=f"tech_{id_elev}")
            projet = st.number_input("Projet (0-5)", 0, 5, 3, key=f"proj_{id_elev}")
        
        col3, col4 = st.columns(2)
        with col3:
            devoir = st.number_input("Note Devoir /20", 0.0, 20.0, 10.0, 0.5, key=f"dev_{id_elev}")
        with col4:
            composition = st.number_input("Note Composition /20", 0.0, 20.0, 10.0, 0.5, key=f"comp_{id_elev}")
        
        remarque = st.text_area("💬 Remarque", key=f"rem_{id_elev}")
        
        total_assiduite = presence + participation + calme + tablier + affaires + cahier + technologie + projet
        moyenne = round((total_assiduite + devoir + composition) / 3, 2)
        
        st.markdown(
            f"**Résumé :** Assiduité = **{total_assiduite}/20** | "
            f"Devoir = **{devoir}/20** | Composition = **{composition}/20** | "
            f"Moyenne générale = **{moyenne}/20**"
        )
        
        evaluations.append({
            "id": id_elev,
            "nom": row["اللقب"],
            "prenom": row["الاسم"],
            "classe": row["القسم"],
            "presence": presence,
            "participation": participation,
            "calme": calme,
            "tablier": tablier,
            "affaires": affaires,
            "cahier": cahier,
            "technologie": technologie,
            "projet": projet,
            "total_assiduite": total_assiduite,
            "devoir": devoir,
            "composition": composition,
            "moyenne": moyenne,
            "remarque": remarque,
        })

# Bouton de sauvegarde
st.markdown("---")
if st.button("💾 Enregistrer les évaluations dans Google Sheets", type="primary", use_container_width=True):
    rows_to_save = []
    for ev in evaluations:
        rows_to_save.append([
            date_eval.strftime("%d/%m/%Y"),
            ev["id"],
            ev["nom"],
            ev["prenom"],
            ev["classe"],
            ev["presence"],
            ev["participation"],
            ev["calme"],
            ev["tablier"],
            ev["affaires"],
            ev["cahier"],
            ev["technologie"],
            ev["projet"],
            ev["total_assiduite"],
            ev["devoir"],
            ev["composition"],
            ev["moyenne"],
            ev["remarque"],
        ])
    try:
        save_evaluation(rows_to_save)
        st.success(f"✅ {len(rows_to_save)} évaluations enregistrées dans la feuille « Evaluation » !")
        st.balloons()
    except Exception as e:
        st.error(f"❌ Erreur lors de l'enregistrement : {e}")
