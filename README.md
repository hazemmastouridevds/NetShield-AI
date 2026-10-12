
# 🛡️ NetShield AI: Enterprise Network Monitoring & Automated Diagnostics

NetShield AI est une plateforme intelligente de surveillance réseau qui effectue un balayage multi-thread et un suivi en temps réel des hôtes. Elle intègre un moteur de diagnostic IA pour classifier automatiquement les pannes d'infrastructure et les analyser via un tableau de bord Streamlit.

---

## 🏗️ Architecture du Système

netshield-ai/
├── phase1_discovery.py            # Scan sous-réseau & inventaire
├── phase3_ping_engine.py          # Surveillance ping en arrière-plan
├── phase4_ai_diagnostics.py      # Moteur de classification IA
├── app_dashboard.py               # Interface web Streamlit
├── network_inventory.json         # Master JSON inventaire
├── outage_logs.json               # Logs d'arrêts historiques
├── coupures_reseau.xlsx           # Export Excel
├── network_diagnostic_report.md   # Rapport synthétique IA
└── requirements.txt               # Liste des dépendances Python

Le système est découpé en 4 composants modulaires :

1. **`phase1_discovery.py` (Découverte & Inventaire) :** Balayage multi-thread du sous-réseau (`10.10.50.x`), résolution ARP/MAC, lookup constructeur et libération automatique des adresses IP inactives (`Free Device` après 5 min).
2. **`phase3_ping_engine.py` (Surveillance Temps Réel) :** Moteur de ping continu avec sockets et fallback ICMP. Sauvegarde atomique sécurisée contre les erreurs de lecture concurrentes.
3. **`phase4_ai_diagnostics.py` (Moteur IA) :** Analyse temporelle et clustering pour distinguer les vraies pannes réseau des arrêts volontaires/mises en veille utilisateur.
4. **`app_dashboard.py` (Interface Streamlit) :** Tableau de bord web à double page : suivi en temps réel fragmenté et page d'analyse globale statique avec filtres temporels précis (à la seconde).

---

## 📋 Table des Matières
1. [Fonctionnalités Clés](#-fonctionnalités-clés)
2. [Stack Technique](#-stack-technique)
3. [Guide d'Installation Pas à Pas](#-guide-dinstallation-pas-à-pas)
4. [Lancement et Utilisation](#-lancement-et-utilisation)
5. [Structure du Projet](#-structure-du-projet)
6. [Auteur](#-auteur)

---

## ✨ Fonctionnalités Clés

* **Découverte Automatique Réseau :** Cartographie dynamique enregistrée dans `network_inventory.json`.
* **Gestion "Free Devices" & Excluant KPI :** Les adresses IP inactives depuis plus de 5 minutes sont marquées `Free Device` et exclues automatiquement du calcul du temps d'arrêt cumulé.
* **Surveillance Continue Haute Fréquence :** Analyse par thread pools avec mécanismes d'écriture atomique (`tempfile` + `os.replace`) prévenant toute corruption JSON.
* **Classification IA des Pannes :** Modèle de clustering identifiant la nature des coupures (Infrastructure vs Humain).
* **Dashboard Interactif Streamlit :**
  * Auto-refresh partiel (`@st.fragment`) évitant les scintillements d'écran.
  * Page d'Analyse avec injection manuelle des données.
  * Filtres par plage de dates, recherche IP/Nom, et plage horaire exacte (`HH:MM:SS`).

---

## 🛠️ Stack Technique

* **Langage :** Python 3.10+
* **Interface Web & Visualisation :** Streamlit, Plotly
* **Traitement de Données :** Pandas, Openpyxl
* **Réseau & Multi-Threading :** Sockets, Subprocess, `concurrent.futures`, `mac-vendor-lookup`

---

## 🚀 Guide d'Installation Pas à Pas

### Étape 1 : Cloner le dépôt
```bash
git clone [https://github.com/hazemmastouridevds/netshield-ai.git](https://github.com/votre-nom-utilisateur/netshield-ai.git)
cd netshield-ai

###Étape 2 : Créer et activer un environnement virtuel



