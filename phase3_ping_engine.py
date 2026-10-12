import concurrent.futures
import datetime
import json
import os
import tempfile
import time
import pandas as pd

# Configurations
INVENTORY_FILE = "network_inventory.json"
EXCEL_LOG_FILE = "coupures_reseau.xlsx"
JSON_LOG_FILE = "outage_logs.json"

POLL_INTERVAL = 3.0   # Ping check frequency in seconds
PING_TIMEOUT = 0.5    # Socket connection timeout in seconds
MAX_WORKERS = 35      # Parallel thread limit

# Critical infrastructure targets to always include
CRITICAL_TARGETS = [
    {"IP Address": "192.168.2.1", "PC / Host Name": "Google DNS", "Device Type": "Internet Gateway", "Hardware Vendor": "Public DNS"},
    {"IP Address": "192.168.100.2", "PC / Host Name": "Cloudflare DNS", "Device Type": "Internet Gateway", "Hardware Vendor": "Public DNS"}
]

def safe_json_write(data, filename):
    """Écriture atomique pour éviter les conflits de lecture simultanée avec Streamlit."""
    dir_name = os.path.dirname(filename) or "."
    with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
        json.dump(data, tf, indent=4)
        temp_name = tf.name
    os.replace(temp_name, filename)

def load_existing_outages():
    """Charge l'historique existant des coupures pour éviter d'écraser les enregistrements passés."""
    if os.path.exists(JSON_LOG_FILE) and os.path.getsize(JSON_LOG_FILE) > 0:
        try:
            with open(JSON_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Erreur de lecture de {JSON_LOG_FILE}: {e}")

    if os.path.exists(EXCEL_LOG_FILE):
        try:
            df = pd.read_excel(EXCEL_LOG_FILE)
            return df.to_dict(orient="records")
        except Exception as e:
            print(f"[!] Erreur de lecture de {EXCEL_LOG_FILE}: {e}")

    return []

def load_targets():
    """Loads target IPs from Phase 1 inventory and appends critical infrastructure targets."""
    targets = {}
    
    # Load critical targets first
    for target in CRITICAL_TARGETS:
        targets[target["IP Address"]] = target

    # Load discovered devices from Phase 1
    if os.path.exists(INVENTORY_FILE) and os.path.getsize(INVENTORY_FILE) > 0:
        try:
            with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for dev in data:
                    ip = dev.get("IP Address")
                    if ip:
                        targets[ip] = dev
            print(f"[*] Loaded {len(targets)} target endpoints for continuous monitoring.")
        except Exception as e:
            print(f"[!] Error loading {INVENTORY_FILE}: {e}")
    else:
        print(f"[!] {INVENTORY_FILE} not found or empty. Monitoring default critical targets only.")

    return targets

def check_ip_status(ip: str) -> bool:
    """Probes host availability using fast socket connections followed by ICMP fallback."""
    import socket
    common_ports = [80, 445, 139, 22, 161, 9100]
    for port in common_ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(PING_TIMEOUT)
                if s.connect_ex((ip, port)) == 0:
                    return True
        except Exception:
            pass

    # Fallback to ICMP Ping
    param = "-n 1 -w 500" if os.name == "nt" else "-c 1 -W 1"
    response = os.system(f"ping {param} {ip} > NUL 2>&1" if os.name == "nt" else f"ping {param} {ip} > /dev/null 2>&1")
    return response == 0

def save_outage_records(outage_history):
    """Saves accumulated outage event records atomically to Excel and JSON files."""
    if not outage_history:
        return

    # Export to JSON via atomic safe write
    safe_json_write(outage_history, JSON_LOG_FILE)

    # Export to Excel
    df = pd.DataFrame(outage_history)
    df.to_excel(EXCEL_LOG_FILE, index=False, engine="openpyxl")

def start_monitoring_loop():
    targets = load_targets()
    if not targets:
        print("[!] No valid target IPs to monitor. Exiting.")
        return

    # Tracking states: {ip: {"status": "ONLINE"/"OFFLINE", "down_since": datetime}}
    device_states = {ip: {"status": "ONLINE", "down_since": None} for ip in targets.keys()}
    
    # Charger l'historique complet existant au démarrage
    outage_history = load_existing_outages()

    print("\n========================================================")
    print("  NETWORK OUTAGE MONITORING ENGINE STARTED")
    print(f"  - Polling {len(targets)} endpoints every {POLL_INTERVAL} seconds.")
    print(f"  - Total Historical Outages Loaded: {len(outage_history)}")
    print(f"  - Logging outages to: {EXCEL_LOG_FILE} and {JSON_LOG_FILE}")
    print("  - Press Ctrl+C to stop the monitoring loop.")
    print("========================================================\n")

    try:
        cycle_count = 0
        while True:
            cycle_count += 1
            timestamp_now = datetime.datetime.now()
            time_str = timestamp_now.strftime("%Y-%m-%d %H:%M:%S")

            # Rechargement périodique des cibles (toutes les 100 boucles ~5 min) pour capturer les nouveaux hôtes découverts
            if cycle_count % 100 == 0:
                updated_targets = load_targets()
                for ip, dev in updated_targets.items():
                    if ip not in targets:
                        targets[ip] = dev
                        device_states[ip] = {"status": "ONLINE", "down_since": None}

            # Parallel status sweep
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_ip = {executor.submit(check_ip_status, ip): ip for ip in targets.keys()}
                
                for future in concurrent.futures.as_completed(future_to_ip):
                    ip = future_to_ip[future]
                    is_online = future.result()
                    
                    current_state = device_states[ip]["status"]
                    info = targets[ip]

                    # Detect State Transition: ONLINE -> OFFLINE
                    if not is_online and current_state == "ONLINE":
                        device_states[ip]["status"] = "OFFLINE"
                        device_states[ip]["down_since"] = timestamp_now
                        print(f" [ALERT 🔴] {time_str} | Disconnection Detected on {ip} ({info.get('PC / Host Name', 'N/A')})")

                    # Detect State Transition: OFFLINE -> ONLINE
                    elif is_online and current_state == "OFFLINE":
                        down_since = device_states[ip]["down_since"]
                        duration_sec = round((timestamp_now - down_since).total_seconds(), 1)
                        
                        device_states[ip]["status"] = "ONLINE"
                        device_states[ip]["down_since"] = None

                        record = {
                            "IP Address": ip,
                            "PC / Host Name": info.get("PC / Host Name", "N/A"),
                            "Device Type": info.get("Device Type", "N/A"),
                            "Hardware Vendor": info.get("Hardware Vendor", "N/A"),
                            "Outage Start": down_since.strftime("%Y-%m-%d %H:%M:%S"),
                            "Outage End": time_str,
                            "Duration (Seconds)": duration_sec,
                            "Status": "RESOLVED"
                        }

                        outage_history.append(record)
                        save_outage_records(outage_history)

                        print(f" [RECOVERY 🟢] {time_str} | {ip} is BACK ONLINE | Outage Duration: {duration_sec}s")

            # Status ping heartbeat every 10 cycles (~30 seconds)
            if cycle_count % 10 == 0:
                offline_count = sum(1 for state in device_states.values() if state["status"] == "OFFLINE")
                print(f"[*] Heartbeat {time_str} | Active Monitored Hosts: {len(targets)} | Currently Down: {offline_count} | Total Logged Outages: {len(outage_history)}")

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n[*] Stopping Ping Engine. Saving final outage records...")
        save_outage_records(outage_history)
        print(f"[✔] Outage monitoring stopped. All {len(outage_history)} outage records saved to {EXCEL_LOG_FILE}.")

if __name__ == "__main__":
    start_monitoring_loop()