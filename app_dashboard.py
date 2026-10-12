
import json
import os
import subprocess
import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime, time as dtime, timedelta

# ==============================================================================
# CONFIGURATION DE LA PAGE
# ==============================================================================
st.set_page_config(
    page_title="Hazem - NetShield AI",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration des fichiers
INVENTORY_FILE = "network_inventory.json"
OUTAGE_EXCEL = "coupures_reseau.xlsx"
OUTAGE_JSON = "outage_logs.json"
REPORT_FILE = "network_diagnostic_report.md"

def safe_read_json(filepath):
    if os.path.exists(filepath):
        try:
            if os.path.getsize(filepath) > 0:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, Exception):
            pass
    return None

def load_data():
    inventory_df = pd.DataFrame()
    outages_df = pd.DataFrame()

    inv_data = safe_read_json(INVENTORY_FILE)
    if inv_data:
        inventory_df = pd.DataFrame(inv_data)

    out_data = safe_read_json(OUTAGE_JSON)
    if out_data:
        outages_df = pd.DataFrame(out_data)
    elif os.path.exists(OUTAGE_EXCEL):
        try:
            outages_df = pd.read_excel(OUTAGE_EXCEL)
        except Exception:
            pass

    if not outages_df.empty:
        if "Outage Start" in outages_df.columns:
            outages_df["Outage Start DT"] = pd.to_datetime(outages_df["Outage Start"], errors="coerce")
        if "Outage End" in outages_df.columns:
            outages_df["Outage End DT"] = pd.to_datetime(outages_df["Outage End"], errors="coerce")
        
        outages_df = outages_df.drop_duplicates(subset=["IP Address", "Outage Start"], keep="last")

    free_ips = set()
    if not inventory_df.empty and "IP Address" in inventory_df.columns and "PC / Host Name" in inventory_df.columns:
        free_ips = set(
            inventory_df[
                (inventory_df["PC / Host Name"] == "Free Device") | 
                (inventory_df["Status"] == "AVAILABLE")
            ]["IP Address"]
        )

    if not outages_df.empty and "IP Address" in outages_df.columns:
        outages_df["Is_Free_Device"] = outages_df["IP Address"].isin(free_ips)
        outage_counts = outages_df['IP Address'].value_counts().to_dict()
        outages_df['Nombre Total de Coupures'] = outages_df['IP Address'].map(outage_counts)
        if not inventory_df.empty and 'IP Address' in inventory_df.columns:
            inventory_df['Nombre de Coupures'] = inventory_df['IP Address'].map(outage_counts).fillna(0).astype(int)

    return inventory_df, outages_df


# ==============================================================================
# SIDEBAR NAVIGATION
# ==============================================================================
st.sidebar.title("📡 NetShield AI")
st.sidebar.markdown("**Surveillance Réseau - HAZEM NetShield **")
st.sidebar.divider()

page = st.sidebar.radio(
    "📌 Navigation", 
    ["Dashboard Temps Réel", "📈 Analyse & Rapport Global"],
    index=0
)

st.sidebar.divider()


# ==============================================================================
# PAGE 1 : DASHBOARD TEMPS RÉEL (AUTO-REFRESH)
# ==============================================================================
if page == "Dashboard Temps Réel":
    auto_refresh = st.sidebar.checkbox("Auto-refresh partiel", value=True)
    refresh_interval = st.sidebar.slider("Intervalle d'affichage (sec)", 2, 30, 5)

    if st.sidebar.button("⚡ Relancer l'Inventaire (Phase 1)"):
        subprocess.Popen(["python", "phase1_discovery.py"])
        st.sidebar.success("Scan Phase 1 démarré !")

    @st.fragment(run_every=refresh_interval if auto_refresh else None)
    def render_live_dashboard():
        inventory_df, outages_df = load_data()

        st.title("📊 NetShield AI - Dashboard Temps Réel")
        st.caption(f"Dernière injection : **{datetime.now().strftime('%H:%M:%S')}**")

        k1, k2, k3, k4 = st.columns(4)
        total_hosts = len(inventory_df) if not inventory_df.empty else 0
        total_outages = len(outages_df) if not outages_df.empty else 0

        if not outages_df.empty and 'Duration (Seconds)' in outages_df.columns:
            active_outages = outages_df[~outages_df["Is_Free_Device"]] if "Is_Free_Device" in outages_df.columns else outages_df
            total_downtime = active_outages['Duration (Seconds)'].sum()
        else:
            total_downtime = 0

        if not outages_df.empty and 'IP Address' in outages_df.columns:
            active_outages_df = outages_df[~outages_df["Is_Free_Device"]] if "Is_Free_Device" in outages_df.columns else outages_df
            if not active_outages_df.empty:
                most_impacted_ip = active_outages_df['IP Address'].mode()[0]
                drop_count = (active_outages_df['IP Address'] == most_impacted_ip).sum()
                most_impacted_str = f"{most_impacted_ip} ({drop_count} pannes)"
            else:
                most_impacted_str = "Aucun"
        else:
            most_impacted_str = "Aucun"

        k1.metric("Équipements Inventoriés", f"{total_hosts}")
        k2.metric("Coupures Enregistrées", f"{total_outages}")
        k3.metric("Temps d'Arrêt Cumulé (Actifs)", f"{int(total_downtime)} sec")
        k4.metric("Hôte le plus Perturbé", most_impacted_str)

        st.divider()

        tab1, tab2, tab3, tab4 = st.tabs([
            "🚨 Historique des Coupures", 
            "🤖 Classification IA", 
            "📈 Analyse par Sous-Réseau", 
            "📋 Inventaire Réseau"
        ])

        with tab1:
            st.subheader("Journal Chronologique des Coupures")
            if not outages_df.empty:
                c1, c2, c3 = st.columns([2, 2.5, 1.5])
                with c1:
                    search_ip = st.text_input("Filtrer par IP / Nom :", key="t1_search")
                with c2:
                    max_log_duration = int(outages_df['Duration (Seconds)'].max()) if 'Duration (Seconds)' in outages_df.columns else 300
                    slider_max_limit = max(max_log_duration, 300)
                    dur_range = st.slider("Durée de coupure (min/max sec) :", 0, slider_max_limit, (0, slider_max_limit), key="t1_slider_range")
                    min_dur, max_dur = dur_range
                with c3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    group_by_ip = st.checkbox("Groupé par IP", value=False, key="t1_group")

                filtered_outages = outages_df.copy()
                if search_ip:
                    filtered_outages = filtered_outages[
                        filtered_outages['IP Address'].astype(str).str.contains(search_ip, case=False, na=False) |
                        filtered_outages['PC / Host Name'].astype(str).str.contains(search_ip, case=False, na=False)
                    ]
                if 'Duration (Seconds)' in filtered_outages.columns:
                    filtered_outages = filtered_outages[
                        (filtered_outages['Duration (Seconds)'] >= min_dur) & 
                        (filtered_outages['Duration (Seconds)'] <= max_dur)
                    ]

                st.caption(f"**{len(filtered_outages)}** événement(s) affiché(s) pour une durée comprise entre **{min_dur}s** et **{max_dur}s**.")
                
                if group_by_ip and 'IP Address' in filtered_outages.columns:
                    grouped_df = filtered_outages.groupby('IP Address').agg(
                        **{
                            'Nom du PC': ('PC / Host Name', 'first'),
                            'Type d\'Équipement': ('Device Type', 'first'),
                            'Nombre Total de Coupures': ('IP Address', 'count'),
                            'Durée Cumulée (sec)': ('Duration (Seconds)', 'sum'),
                            'Dernière Coupure': ('Outage End', 'max')
                        }
                    ).reset_index().sort_values(by="Nombre Total de Coupures", ascending=False)
                    st.dataframe(grouped_df, use_container_width=True)
                else:
                    st.dataframe(filtered_outages, use_container_width=True)
            else:
                st.info("Aucun incident enregistré.")

        with tab2:
            st.subheader("🔍 Classification des Coupures (IA & Clustering)")
            if st.button("⚡ Lancer la Classification IA", key="btn_run_ai"):
                subprocess.run(["python", "phase4_ai_diagnostics.py"])
                st.success("Analyse terminée !")

            if not outages_df.empty and "Type de Coupure" in outages_df.columns:
                c_g1, c_g2 = st.columns(2)
                with c_g1:
                    class_counts = outages_df["Type de Coupure"].value_counts().reset_index()
                    class_counts.columns = ["Type de Coupure", "Total"]
                    st.plotly_chart(px.pie(class_counts, values="Total", names="Type de Coupure", title="Répartition des Classes"), use_container_width=True)
                with c_g2:
                    st.plotly_chart(px.bar(class_counts, x="Type de Coupure", y="Total", color="Type de Coupure"), use_container_width=True)

        with tab3:
            st.subheader("📈 Cartographie des Incidents par Sous-Réseau")
            if not outages_df.empty and 'IP Address' in outages_df.columns:
                outages_df['Subnet'] = outages_df['IP Address'].apply(lambda x: '.'.join(str(x).split('.')[:3]) if '.' in str(x) else 'Inconnu')
                subnet_counts = outages_df['Subnet'].value_counts().reset_index()
                subnet_counts.columns = ['Sous-Réseau', 'Total']
                st.plotly_chart(px.bar(subnet_counts, x='Sous-Réseau', y='Total', color='Sous-Réseau'), use_container_width=True)

        with tab4:
            st.subheader("📋 Inventaire Réseau")
            st.dataframe(inventory_df, use_container_width=True)

    render_live_dashboard()


# ==============================================================================
# PAGE 2 : ANALYSE & RAPPORT GLOBAL (SANS AUTO-REFRESH)
# ==============================================================================
elif page == "📈 Analyse & Rapport Global":
    st.title("📈 Page d'Analyse & Rapport Global")
    st.markdown("Cette page **ne se rafraîchit pas automatiquement**. Cliquez sur le bouton ci-dessous pour injecter les données récentes.")

    col_btn, col_txt = st.columns([1.5, 4])
    with col_btn:
        if st.button("🔄 Injecter / Mettre à Jour les Données Now", use_container_width=True):
            st.cache_data.clear()
            st.session_state["last_analysis_refresh"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.rerun()

    last_refresh_time = st.session_state.get("last_analysis_refresh", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    with col_txt:
        st.info(f"📅 **Dernière injection des données effectuée le :** `{last_refresh_time}`")

    st.divider()

    inventory_df, outages_df = load_data()

    # ==========================================
    # FILTRES AVANCÉS
    # ==========================================
    st.subheader("🔍 Filtres Avancés (Période, IP, Plage Horaire, Statut)")
    
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)

    min_date = outages_df["Outage Start DT"].min().date() if not outages_df.empty and "Outage Start DT" in outages_df.columns and pd.notnull(outages_df["Outage Start DT"].min()) else datetime.now().date()
    max_date = datetime.now().date()
    
    with f_col1:
        date_range = st.date_input("Plage de Dates :", value=(min_date, max_date))

    # Filtre Plage Horaire précis (à la seconde)
    with f_col2:
        time_range = st.slider(
            "Plage Horaire (HH:MM:SS) :",
            value=(dtime(0, 0, 0), dtime(23, 59, 59)),
            format="HH:mm:ss",
            step=timedelta(seconds=1)
        )

    with f_col3:
        filter_ip = st.text_input("Filtrer par IP ou Nom PC :", placeholder="Ex: 10.10.50.93...")

    with f_col4:
        status_options = ["Tous", "Actifs (ONLINE/OFFLINE)", "Inactifs (Free Device / AVAILABLE)"]
        selected_status = st.selectbox("Statut Équipement :", status_options)

    # ==========================================
    # APPLICATION DES FILTRES
    # ==========================================
    filtered_df = outages_df.copy()

    if not filtered_df.empty and "Outage Start DT" in filtered_df.columns:
        # 1. Filtre par date
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_d, end_d = date_range
            filtered_df = filtered_df[
                (filtered_df["Outage Start DT"].dt.date >= start_d) & 
                (filtered_df["Outage Start DT"].dt.date <= end_d)
            ]

        # 2. Filtre par plage horaire à la seconde
        start_t, end_t = time_range
        filtered_df = filtered_df[
            (filtered_df["Outage Start DT"].dt.time >= start_t) & 
            (filtered_df["Outage Start DT"].dt.time <= end_t)
        ]

    # 3. Filtre par recherche IP/Nom
    if filter_ip and not filtered_df.empty:
        filtered_df = filtered_df[
            filtered_df["IP Address"].astype(str).str.contains(filter_ip, case=False, na=False) |
            filtered_df["PC / Host Name"].astype(str).str.contains(filter_ip, case=False, na=False)
        ]

    # 4. Filtre par statut d'activité
    if selected_status != "Tous" and not filtered_df.empty:
        if selected_status == "Inactifs (Free Device / AVAILABLE)":
            filtered_df = filtered_df[filtered_df["Is_Free_Device"] == True]
        else:
            filtered_df = filtered_df[filtered_df["Is_Free_Device"] == False]

    st.divider()

    # ==========================================
    # KPIS ET METRIQUES
    # ==========================================
    st.subheader("📊 Tableau Analytique des KPIs")

    kpi_a1, kpi_a2, kpi_a3, kpi_a4, kpi_a5 = st.columns(5)

    tot_events = len(filtered_df)
    tot_downtime_sec = filtered_df["Duration (Seconds)"].sum() if not filtered_df.empty and "Duration (Seconds)" in filtered_df.columns else 0
    avg_downtime_sec = filtered_df["Duration (Seconds)"].mean() if not filtered_df.empty and "Duration (Seconds)" in filtered_df.columns else 0
    median_downtime_sec = filtered_df["Duration (Seconds)"].median() if not filtered_df.empty and "Duration (Seconds)" in filtered_df.columns else 0
    critical_events = len(filtered_df[filtered_df["Duration (Seconds)"] >= 300]) if not filtered_df.empty and "Duration (Seconds)" in filtered_df.columns else 0

    kpi_a1.metric("Incidents Filtrés", f"{tot_events}")
    kpi_a2.metric("Temps d'Arrêt Total", f"{int(tot_downtime_sec)} sec")
    kpi_a3.metric("Moyenne par Panne", f"{round(avg_downtime_sec, 1)} sec")
    kpi_a4.metric("Médiane par Panne", f"{round(median_downtime_sec, 1)} sec")
    kpi_a5.metric("Pannes Critiques (>5m)", f"{critical_events}", delta_color="inverse")

    st.divider()

    # ==========================================
    # ONGLETS DE DONNÉES ET GRAPHIQUES
    # ==========================================
    tab_ana1, tab_ana2, tab_ana3 = st.tabs([
        "📋 Tableau Synthétique Filtré", 
        "📈 Graphiques d'Analyse", 
        "🤖 Rapport Médical / IA Généré"
    ])

    with tab_ana1:
        st.markdown("##### 📄 Données Détaillées des Coupures Filtrées")
        st.caption(f"Affichage de **{len(filtered_df)}** ligne(s) correspondant aux filtres.")
        st.dataframe(filtered_df, use_container_width=True)

    with tab_ana2:

        # --- 2. Graphiques de Classification IA dupliqués ---
        st.markdown("##### 🔍 Répartition des Types de Coupures (IA)")
        if not filtered_df.empty and "Type de Coupure" in filtered_df.columns:
            c_g1, c_g2 = st.columns(2)
            class_counts = filtered_df["Type de Coupure"].value_counts().reset_index()
            class_counts.columns = ["Type de Coupure", "Total"]
            
            with c_g1:
                st.plotly_chart(px.pie(class_counts, values="Total", names="Type de Coupure", title="Répartition des Classes en %"), use_container_width=True)
            with c_g2:
                st.plotly_chart(px.bar(class_counts, x="Type de Coupure", y="Total", color="Type de Coupure", title="Volume par Type de Coupure"), use_container_width=True)
        else:
            st.info("Aucune donnée de classification IA générée. Lancez la classification depuis le dashboard.")        
        # --- 1. Graphique des PC (Groupé et coloré par Adresse IP) ---
        st.markdown("##### 📊 Graphique des Temps d'Arrêt Cumulés par Équipement")
        if not filtered_df.empty and "IP Address" in filtered_df.columns and "Duration (Seconds)" in filtered_df.columns:
            # Groupement strict par IP Address
            device_sum = filtered_df.groupby("IP Address")["Duration (Seconds)"].sum().reset_index()
            device_sum = device_sum.sort_values(by="Duration (Seconds)", ascending=False)

            fig_top_down = px.bar(
                device_sum,
                x="IP Address",
                y="Duration (Seconds)",
                color="IP Address",  # Coloration uniquement par IP Address
                title="Cumul des Temps d'Arrêt par Adresse IP (Secondes)"
            )
            st.plotly_chart(fig_top_down, use_container_width=True)
        else:
            st.info("Aucune donnée à afficher pour le graphique.")

        st.divider()

       

    with tab_ana3:
        st.markdown("##### 🤖 Rapport Synthétique de Diagnostic IA")
        if st.button("⚡ Exécuter / Régénérer le Rapport IA"):
            subprocess.run(["python", "phase4_ai_diagnostics.py"])
            st.success("Rapport ré-analysé avec succès !")
            st.rerun()

        if os.path.exists(REPORT_FILE):
            with open(REPORT_FILE, "r", encoding="utf-8") as f:
                st.markdown(f.read())
        else:
            st.warning("Le rapport d'analyse IA n'a pas encore été généré. Cliquez sur le bouton ci-dessus pour le créer.")