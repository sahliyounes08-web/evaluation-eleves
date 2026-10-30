import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import plotly.express as px

# ============ CONFIGURATION DE LA PAGE ============
st.set_page_config(
    page_title="Évaluation - SAHL YOUNES",
    page_icon="📚",
    layout="wide"
)

# ============ SYSTÈME DE MOT DE PASSE ============
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True

    st.title("🔒 Accès sécurisé")
    password = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        if password == "younes08":
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("❌ Mot de passe incorrect.")
    return False

if check_password():
    # ============ CONNEXION GOOGLE SHEETS ============
    @st.cache_resource
    def get_gspread_client():
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        return gspread.authorize(credentials)

    @st.cache_data(ttl=300)
    def load_students():
        client = get_gspread_client()
        sheet = client.open_by_key(st.secrets["spreadsheet_id"])
        return pd.DataFrame(sheet.worksheet("جميع التلاميذ").get_all_records())

    @st.cache_data(ttl=60)
    def load_all_evaluations():
        client = get_gspread_client()
        sheet = client.open_by_key(st.secrets["spreadsheet_id"])
        dfs = []
        for sheet_name in ["Evaluation", "Evaluation 2", "Evaluation 3"]:
            try:
                worksheet = sheet.worksheet(sheet_name)
                data = worksheet.get_all_records()
                if data:
                    dfs.append(pd.DataFrame(data))
            except:
                pass 
        if dfs:
            return pd.concat(dfs, ignore_index=True)
        return pd.DataFrame()

    def save_evaluation(rows_to_save, target_sheet):
        client = get_gspread_client()
        sheet = client.open_by_key(st.secrets["spreadsheet_id"])
        worksheet = sheet.worksheet(target_sheet)
        for row in rows_to_save:
            worksheet.append_row(row, value_input_option="USER_ENTERED")

    # ============ INTERFACE ============
    st.title("📚 Plateforme d'Évaluation")
    st.markdown("### 👨‍🏫 Enseignant : SAHL YOUNES")
    st.caption("Lycée - USTHB - IFG Sonatrach")
    st.markdown("---")

    if st.button("🔄 Rafraîchir les données"):
        st.cache_data.clear()
        st.rerun()

    try:
        df_students = load_students()
        df_evals = load_all_evaluations()
    except Exception as e:
        st.error(f"⚠️ Erreur de chargement : {e}")
        st.stop()

    classes = sorted(df_students["القسم"].unique().tolist())
    classe_choisie = st.selectbox("🎓 Sélectionnez la classe :", classes)
    df_classe = df_students[df_students["القسم"] == classe_choisie].copy()
    
    nom_classe_nettoye = str(classe_choisie).strip().upper()
    is_usthb = "USTHB" in nom_classe_nettoye
    is_ifg = "IFG" in nom_classe_nettoye
    is_lycee = not is_usthb and not is_ifg

    # Préparation des données de la classe
    df_derniere_eval = pd.DataFrame()
    dernieres_notes_dict = {}
    
    if not df_evals.empty and "Classe" in df_evals.columns:
        df_evals_classe = df_evals[df_evals["Classe"] == classe_choisie].copy()
        if not df_evals_classe.empty:
            df_derniere_eval = df_evals_classe.sort_values("Date").groupby("ID_Eleve").last().reset_index()
            
            for col in ["Presence", "Total_Assiduite", "Note_Devoir", "Note_Composition", "Moyenne"]:
                if col in df_derniere_eval.columns:
                    df_derniere_eval[col] = pd.to_numeric(df_derniere_eval[col], errors='coerce').fillna(0).clip(0, 20)
            
            for _, r in df_derniere_eval.iterrows():
                dernieres_notes_dict[str(r["ID_Eleve"])] = float(r["Moyenne"])

    # ============ TABLEAU DE BORD (LYCÉE UNIQUEMENT) ============
    if is_lycee:
        st.markdown("### 📊 Tableau de bord de la classe")
        
        if df_derniere_eval.empty:
            st.info("Aucune évaluation enregistrée pour le moment.")
        else:
            # --- TOP 3 DES ÉLÈVES ---
            st.markdown("#### 🏆 Podium de la classe")
            top_3 = df_derniere_eval.nlargest(3, 'Moyenne')
            cols_podium = st.columns(3)
            medals = ["🥇", "🥈", "🥉"]
            for idx, (_, etudiant) in enumerate(top_3.iterrows()):
                with cols_podium[idx]:
                    st.success(f"{medals[idx]} **{etudiant['Nom']} {etudiant['Prénom']}**\n\nMoyenne : **{etudiant['Moyenne']:.2f}/20**")

            st.markdown("---")
            
            # --- GRAPHIQUES DONUTS ---
            col_g1, col_g2, col_g3 = st.columns(3)
            
            with col_g1:
                df_derniere_eval['Niveau'] = pd.cut(df_derniere_eval['Moyenne'], bins=[-1, 9.99, 13.99, 20], labels=['En difficulté', 'Moyen', 'Excellent'])
                fig1 = px.pie(df_derniere_eval, names='Niveau', hole=0.5, title="Répartition des Moyennes", color='Niveau', color_discrete_map={'En difficulté':'#ef553b', 'Moyen':'#636efa', 'Excellent':'#00cc96'})
                fig1.update_layout(margin=dict(t=40, b=0, l=0, r=0), showlegend=False)
                st.plotly_chart(fig1, use_container_width=True)

            with col_g2:
                presents = len(df_derniere_eval[df_derniere_eval["Presence"] >= 1.5])
                absents = len(df_derniere_eval) - presents
                df_pres = pd.DataFrame({"Statut": ["Présents", "Absents"], "Nombre": [presents, absents]})
                fig2 = px.pie(df_pres, names='Statut', values='Nombre', hole=0.5, title="Taux de Présence", color='Statut', color_discrete_map={'Présents':'#00cc96', 'Absents':'#ef553b'})
                fig2.update_layout(margin=dict(t=40, b=0, l=0, r=0), showlegend=False)
                st.plotly_chart(fig2, use_container_width=True)

            with col_g3:
                eleves_difficulte = len(df_derniere_eval[df_derniere_eval["Moyenne"] < 10])
                eleves_ok = len(df_derniere_eval) - eleves_difficulte
                df_alert = pd.DataFrame({"Statut": ["À encadrer", "Satisfaisant"], "Nombre": [eleves_difficulte, eleves_ok]})
                fig3 = px.pie(df_alert, names='Statut', values='Nombre', hole=0.5, title="Besoins d'encadrement", color='Statut', color_discrete_map={'À encadrer':'#ef553b', 'Satisfaisant':'#00cc96'})
                fig3.update_layout(margin=dict(t=40, b=0, l=0, r=0), showlegend=False)
                st.plotly_chart(fig3, use_container_width=True)

            # --- GRAPHIQUE EN BARRES (REVENU !) ---
            with st.expander("📈 Voir le graphique en barres des moyennes", expanded=False):
                df_derniere_eval["Nom_Complet"] = df_derniere_eval["Nom"].astype(str) + " " + df_derniere_eval["Prénom"].astype(str)
                st.bar_chart(df_derniere_eval.set_index("Nom_Complet")["Moyenne"])

            # --- LISTE DÉTAILLÉE ET EXPORTATION ---
            col_info, col_export = st.columns([3, 1])
            with col_info:
                with st.expander("🚨 Voir la liste des élèves à encadrer (Moyenne < 10)"):
                    df_dif = df_derniere_eval[df_derniere_eval["Moyenne"] < 10]
                    if not df_dif.empty:
                        st.dataframe(df_dif[["Nom", "Prénom", "Moyenne", "Remarque"]], use_container_width=True)
                    else:
                        st.write("Aucun élève en difficulté. Félicitations ! 🎉")
            
            with col_export:
                csv = df_derniere_eval[["Nom", "Prénom", "Classe", "Moyenne", "Remarque"]].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Exporter en Excel (CSV)",
                    data=csv,
                    file_name=f"resultats_{classe_choisie}.csv",
                    mime="text/csv",
                    type="primary"
                )
        st.markdown("---")

    # ============ SAISIE DES NOTES ============
    date_eval = st.date_input("📅 Date de la séance", value=datetime.today())
    st.markdown("### 📝 Saisie des notes")
    
    if is_lycee:
        st.caption("💡 Notes d'assiduité sur 20 + Devoir /20 + Composition /20.")
    elif is_usthb:
        st.caption("💡 Fac (USTHB) : Présence /2.5 + Assiduité /2.5 + TP /15.")
    elif is_ifg:
        st.caption("💡 Institut (IFG) : Présence /3 + Travaux (Salle, TP, Terrain) /5 + Examen Final /12.")

    evaluations = []

    for i, (_, row) in enumerate(df_classe.iterrows()):
        id_elev = str(row["الترتيب"])
        uid = f"{i}_{id_elev}" 
        
        moy_affichee = dernieres_notes_dict.get(id_elev, None)
        titre_moy = f" — Moy: {moy_affichee:.2f}/20" if moy_affichee is not None else ""
        
        nom_complet = f"{row['اللقب']} {row['الاسم']}"
        
        with st.expander(f"👤 {nom_complet} (ID: {id_elev}) {titre_moy}"):
            
            # ================= FORMULAIRE LYCÉE =================
            if is_lycee:
                col1, col2 = st.columns(2)
                with col1:
                    presence = st.number_input("Présence (0-2)", 0, 2, 2, key=f"pr_{uid}")
                    participation = st.number_input("Participation (0-3)", 0, 3, 2, key=f"pa_{uid}")
                    calme = st.number_input("Calme (0-2)", 0, 2, 2, key=f"ca_{uid}")
                    tablier = st.number_input("Tablier (0-1)", 0, 1, 1, key=f"ta_{uid}")
                with col2:
                    affaires = st.number_input("Affaires (0-2)", 0, 2, 2, key=f"af_{uid}")
                    cahier = st.number_input("Cahier (0-3)", 0, 3, 2, key=f"ca2_{uid}")
                    technologie = st.number_input("Technologie (0-2)", 0, 2, 2, key=f"te_{uid}")
                    projet = st.number_input("Projet (0-5)", 0, 5, 3, key=f"pr2_{uid}")
                
                col3, col4 = st.columns(2)
                with col3: devoir = st.number_input("Devoir /20", 0.0, 20.0, 10.0, 0.5, key=f"de_{uid}")
                with col4: composition = st.number_input("Composition /20", 0.0, 20.0, 10.0, 0.5, key=f"co_{uid}")
                
                remarque = st.text_area("💬 Remarque", key=f"re_{uid}")
                
                total_assiduite = presence + participation + calme + tablier + affaires + cahier + technologie + projet
                moyenne = round((total_assiduite + devoir + composition) / 3, 2)
                
                st.markdown(f"**Moyenne calculée : {moyenne}/20** | Assiduité : {total_assiduite}/20")
                st.progress(min(int(moyenne * 5), 100))
                
                evaluations.append([
                    date_eval.strftime("%d/%m/%Y"), id_elev, row["اللقب"], row["الاسم"], row["القسم"],
                    presence, participation, calme, tablier, affaires, cahier, technologie, projet,
                    total_assiduite, devoir, composition, moyenne, remarque
                ])

            # ================= FORMULAIRE USTHB =================
            elif is_usthb:
                col1, col2, col3 = st.columns(3)
                with col1: pres_usthb = st.number_input("Présence (/2.5)", 0.0, 2.5, 2.5, 0.5, key=f"up1_{uid}")
                with col2: assid_usthb = st.number_input("Assiduité (/2.5)", 0.0, 2.5, 2.5, 0.5, key=f"up2_{uid}")
                with col3: tp_usthb = st.number_input("Note du TP (/15)", 0.0, 15.0, 10.0, 0.5, key=f"ut_{uid}")
                
                remarque = st.text_area("💬 Remarque", key=f"re_{uid}")
                moyenne = round(pres_usthb + assid_usthb + tp_usthb, 2)
                
                st.markdown(f"**Note finale : {moyenne}/20**")
                st.progress(min(int(moyenne * 5), 100))
                
                evaluations.append([
                    date_eval.strftime("%d/%m/%Y"), id_elev, row["اللقب"], row["الاسم"], row["القسم"],
                    pres_usthb, assid_usthb, 0, 0, 0, 0, 0, 0, (pres_usthb + assid_usthb), tp_usthb, 0, moyenne, remarque 
                ])

            # ================= FORMULAIRE IFG =================
            elif is_ifg:
                col1, col2, col3 = st.columns(3)
                with col1: pres_ifg = st.number_input("Présence (/3)", 0.0, 3.0, 2.5, 0.5, key=f"ip_{uid}")
                with col2: trav_ifg = st.number_input("Travaux (Salle, TP, Assiduité, Terrain) (/5)", 0.0, 5.0, 4.0, 0.5, key=f"it_{uid}")
                with col3: exam_ifg = st.number_input("Examen Final (/12)", 0.0, 12.0, 8.0, 0.5, key=f"ie_{uid}")
                
                remarque = st.text_area("💬 Remarque", key=f"re_{uid}")
                moyenne = round(pres_ifg + trav_ifg + exam_ifg, 2)
                
                st.markdown(f"**Note finale : {moyenne}/20**")
                st.progress(min(int(moyenne * 5), 100))
                
                evaluations.append([
                    date_eval.strftime("%d/%m/%Y"), id_elev, row["اللقب"], row["الاسم"], row["القسم"],
                    pres_ifg, 0, 0, 0, 0, 0, 0, 0, (pres_ifg + trav_ifg), 0, exam_ifg, moyenne, remarque 
                ])

    # ============ BOUTON DE SAUVEGARDE ============
    st.markdown("---")
    if st.button("💾 Enregistrer les notes", type="primary", use_container_width=True):
        if is_ifg: target_sheet = "Evaluation 2"
        elif is_usthb: target_sheet = "Evaluation 3"
        else: target_sheet = "Evaluation"

        try:
            save_evaluation(evaluations, target_sheet)
            st.success(f"✅ Notes enregistrées dans l'onglet **{target_sheet}** !")
            st.balloons()
            st.cache_data.clear()
        except Exception as e:
            st.error(f"❌ Erreur lors de l'enregistrement : {e}")
