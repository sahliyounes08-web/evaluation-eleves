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

# ============ SYSTÈME DE MOT DE PASSE ============
def check_password():
    """Retourne True si le mot de passe est correct."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    # Affichage de l'écran de connexion
    st.title("🔒 Accès sécurisé")
    st.caption("Veuillez entrer le mot de passe pour accéder à l'application.")
    password = st.text_input("Mot de passe", type="password")
    
    if st.button("Se connecter"):
        if password == "younes08":
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("❌ Mot de passe incorrect.")
    
    return False

# On n'affiche la suite que si le mot de passe est correct
if check_password():

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

    @st.cache_data(ttl=60)
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
    st.markdown("### 👨‍🏫 Enseignant : SAHL YOUNES") # Votre nom ajouté ici
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
        st.stop()

    # Sélection de la classe
    classes = sorted(df_students["القسم"].unique().tolist())
    classe_choisie = st.selectbox("🎓 Sélectionnez une classe :", classes)

    df_classe = df_students[df_students["القسم"] == classe_choisie].copy()
    st.success(f"**{len(df_classe)} élèves** dans la classe « {classe_choisie} »")

    # ============ PRÉPARATION DES DERNIÈRES NOTES ============
    last_grades = {}
    if not df_evals.empty and "Classe" in df_evals.columns:
        df_evals_classe = df_evals[df_evals["Classe"] == classe_choisie].copy()
        
        if not df_evals_classe.empty:
            df_sorted = df_evals_classe.sort_values("Date")
            df_derniere_eval = df_sorted.groupby("ID_Eleve").last().reset_index()
            
            for _, r in df_derniere_eval.iterrows():
                try:
                    d = float(r.get("Note_Devoir", 10.0))
                    c = float(r.get("Note_Composition", 10.0))
                except:
                    d, c = 10.0, 10.0
                d = max(0.0, min(20.0, d))
                c = max(0.0, min(20.0, c))
                last_grades[str(r["ID_Eleve"])] = (d, c)
    else:
        df_evals_classe = pd.DataFrame()

    # ============ TABLEAU DE BORD ============
    st.markdown("### 📊 Tableau de bord de la classe")

    if df_evals_classe.empty:
        st.info("Aucune évaluation enregistrée pour cette classe pour le moment.")
    else:
        cols_to_clean = ["Presence", "Total_Assiduite", "Note_Devoir", "Note_Composition", "Moyenne"]
        for col in cols_to_clean:
            if col in df_derniere_eval.columns:
                df_derniere_eval[col] = pd.to_numeric(df_derniere_eval[col], errors='coerce').fillna(0)
                df_derniere_eval[col] = df_derniere_eval[col].clip(0, 20)

        df_derniere_eval["Moyenne"] = (df_derniere_eval["Total_Assiduite"] + df_derniere_eval["Note_Devoir"] + df_derniere_eval["Note_Composition"]) / 3

        total_eleves_notes = len(df_derniere_eval)
        moyenne_classe = df_derniere_eval["Moyenne"].mean()
        
        presents = len(df_derniere_eval[df_derniere_eval["Presence"] >= 1.5])
        taux_presence = (presents / total_eleves_notes) * 100 if total_eleves_notes > 0 else 0

        eleves_difficulte = df_derniere_eval[df_derniere_eval["Moyenne"] < 10]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Élèves évalués", f"{total_eleves_notes} / {len(df_classe)}")
        col2.metric("Moyenne de la classe", f"{moyenne_classe:.2f} / 20")
        col3.metric("Taux de présence", f"{taux_presence:.1f} %")
        col4.metric("Élèves en difficulté", f"{len(eleves_difficulte)}")

        if not eleves_difficulte.empty:
            with st.expander("🚨 Voir les élèves qui ont besoin d'encadrement (Moyenne < 10)"):
                df_affichage = eleves_difficulte[["Nom", "Prénom", "Moyenne", "Remarque"]].copy()
                df_affichage.columns = ["Nom", "Prénom", "Moyenne", "Remarque"]
                st.dataframe(df_affichage, use_container_width=True)

        with st.expander("📈 Voir le graphique des moyennes"):
            df_derniere_eval["Nom_Complet"] = df_derniere_eval["Nom"] + " " + df_derniere_eval["Prénom"]
            st.bar_chart(df_derniere_eval.set_index("Nom_Complet")["Moyenne"])

    st.markdown("---")

    # ============ SAISIE DES NOTES ============
    date_eval = st.date_input("📅 Date de l'évaluation", value=datetime.today())

    st.markdown("### 📝 Saisie des notes")
    st.caption("💡 Les notes de Devoir et de Composition sont mémorisées. Vous n'avez pas besoin de les ressaisir à chaque fois !")

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
            
            val_dev, val_comp = last_grades.get(id_elev, (10.0, 10.0))
            
            with col3:
                devoir = st.number_input("Note Devoir /20", 0.0, 20.0, float(val_dev), 0.5, key=f"dev_{id_elev}")
            with col4:
                composition = st.number_input("Note Composition /20", 0.0, 20.0, float(val_comp), 0.5, key=f"comp_{id_elev}")
            
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
            st.success(f"✅ {len(rows_to_save)} évaluations enregistrées !")
            st.balloons()
        except Exception as e:
            st.error(f"❌ Erreur lors de l'enregistrement : {e}")
