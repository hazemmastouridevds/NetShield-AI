import json
import os
import tempfile
from datetime import datetime
import pandas as pd

EXCEL_LOG = "coupures_reseau.xlsx"
JSON_LOG = "outage_logs.json"
REPORT_FILE = "network_diagnostic_report.md"

def safe_json_write(data, filename):
    """Écrit de manière atomique pour éviter la corruption du fichier JSON."""
    dir_name = os.path.dirname(filename) or "."
    with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
        json.dump(data, tf, indent=4)
        temp_name = tf.name
    os.replace(temp_name, filename)

def classify_outage_event(row, df_all):
    start_str = str(row.get("Outage Start", ""))
    ip = str(row.get("IP Address", ""))
    duration = float(row.get("Duration (Seconds)", 0))
    
    try:
        dt_start = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        hour = dt_start.hour
    except Exception:
        hour = 12

    subnet = ".".join(ip.split(".")[:3]) if "." in ip else ip
    
    coincident_events = 0
    if "Outage Start" in df_all.columns:
        for _, other in df_all.iterrows():
            if str(other.get("IP Address", "")) != ip and str(other.get("IP Address", "")).startswith(subnet):
                try:
                    dt_other = datetime.strptime(str(other.get("Outage Start", "")), "%Y-%m-%d %H:%M:%S")
                    if abs((dt_start - dt_other).total_seconds()) <= 30:
                        coincident_events += 1
                except Exception:
                    pass

    # Algorithme de classification
    if coincident_events >= 2:
        return "🔴 Panne Réseau Infrastructure (Switch / Onduleur)"
    elif hour >= 19 or hour < 7:
        return "🌙 Mise en Veille / Extinction (Hors-Heures)"
    elif duration >= 1800:
        return "👤 Extinction Poste Utilisateur"
    else:
        return "🟡 Instabilité Câble RJ45 / Port Switch"

def run_classification():
    df = pd.DataFrame()
    if os.path.exists(JSON_LOG) and os.path.getsize(JSON_LOG) > 0:
        try:
            with open(JSON_LOG, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data:
                    df = pd.DataFrame(data)
        except Exception:
            pass

    if df.empty and os.path.exists(EXCEL_LOG):
        try:
            df = pd.read_excel(EXCEL_LOG)
        except Exception:
            pass

    if not df.empty:
        df["Type de Coupure"] = df.apply(lambda row: classify_outage_event(row, df), axis=1)
        
        # Sauvegarde sécurisée
        records = df.to_dict(orient="records")
        safe_json_write(records, JSON_LOG)
        df.to_excel(EXCEL_LOG, index=False, engine="openpyxl")

        # Génération du rapport Markdown
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        counts = df["Type de Coupure"].value_counts().to_dict()
        
        report_md = f"""# 🛡️ NetShield AI - Rapport de Classification
**Généré le :** {now_str}

## 📊 Synthese
* **Total des Coupures Analysées :** {len(df)}
* **🔴 Pannes Infra/Switch :** {counts.get('🔴 Panne Réseau Infrastructure (Switch / Onduleur)', 0)}
* **🌙 / 👤 Actions Utilisateurs / Veille :** {counts.get('🌙 Mise en Veille / Extinction (Hors-Heures)', 0) + counts.get('👤 Extinction Poste Utilisateur', 0)}
* **🟡 Câbles Instables :** {counts.get('🟡 Instabilité Câble RJ45 / Port Switch', 0)}
"""
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write(report_md)
        print("[✔] Classification et rapport IA mis à jour.")

if __name__ == "__main__":
    run_classification()