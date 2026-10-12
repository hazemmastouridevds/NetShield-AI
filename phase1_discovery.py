import concurrent.futures
import datetime
import json
import os
import socket
import subprocess
import tempfile
import pandas as pd
from mac_vendor_lookup import MacLookup

# Paramètres réseau
TARGET_SUBNET = "192.168.2" #Configurer le sous-réseau cible
IP_RANGE = range(1, 255)
PING_TIMEOUT = 1.0
PORT_TIMEOUT = 0.5
OFFLINE_THRESHOLD_SECONDS = 300  # 5 minutes (300 secondes)

PORT_SIGNATURES = {
    161: "Managed Switch / Router (SNMP)",
    22: "SSH Server / Switch",
    9100: "Network Printer",
    80: "HTTP Web Interface (AP / UPS / Camera)",
    443: "HTTPS Web Interface",
    445: "Windows Workstation / File Server",
    139: "NetBIOS Service",
}

def safe_json_write(data, filename):
    """Écriture atomique sécurisée contre les erreurs de lecture JSON."""
    dir_name = os.path.dirname(filename) or "."
    with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
        json.dump(data, tf, indent=4)
        temp_name = tf.name
    os.replace(temp_name, filename)

def ping_host(ip: str) -> bool:
    common_ports = [80, 445, 139, 22, 161, 9100]
    for port in common_ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex((ip, port)) == 0:
                    return True
        except Exception:
            pass

    param = "-n 1 -w 500" if os.name == "nt" else "-c 1 -W 1"
    response = os.system(f"ping {param} {ip} > NUL 2>&1" if os.name == "nt" else f"ping {param} {ip} > /dev/null 2>&1")
    return response == 0

def probe_open_ports(ip: str) -> list:
    open_ports = []
    for port in PORT_SIGNATURES.keys():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(PORT_TIMEOUT)
                if s.connect_ex((ip, port)) == 0:
                    open_ports.append(port)
        except Exception:
            pass
    return open_ports

def get_mac_address(ip: str) -> str:
    try:
        if os.name == "nt":
            output = subprocess.check_output(f"arp -a {ip}", shell=True).decode('utf-8', errors='ignore')
            for line in output.splitlines():
                if ip in line:
                    parts = line.split()
                    for part in parts:
                        if "-" in part and len(part) == 17:
                            return part.upper().replace("-", ":")
        else:
            with open("/proc/net/arp", "r") as f:
                for line in f.readlines():
                    if ip in line:
                        parts = line.split()
                        return parts[3].upper()
    except Exception:
        pass
    return "UNKNOWN"

def get_pc_name(ip: str, open_ports: list) -> str:
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        if hostname and hostname != ip:
            return hostname.split('.')[0].upper()
    except Exception:
        pass

    if os.name == "nt" and (139 in open_ports or 445 in open_ports):
        try:
            output = subprocess.check_output(f"nbtstat -A {ip}", shell=True, timeout=1.5).decode('utf-8', errors='ignore')
            for line in output.splitlines():
                if "<00>" in line and "UNIQUE" in line:
                    parts = line.split()
                    if parts:
                        return parts[0].strip().upper()
        except Exception:
            pass

    return "N/A"

def classify_device(open_ports: list, vendor: str) -> str:
    vendor_lower = vendor.lower()
    if 161 in open_ports or "cisco" in vendor_lower or "hp enterprise" in vendor_lower or "aruba" in vendor_lower:
        return "Network Switch / AP"
    elif 9100 in open_ports or "epson" in vendor_lower or "hp inc." in vendor_lower or "kyocera" in vendor_lower:
        return "Network Printer"
    elif 445 in open_ports or 139 in open_ports or "microsoft" in vendor_lower or "intel" in vendor_lower or "dell" in vendor_lower or "lenovo" in vendor_lower:
        return "Workstation / PC"
    elif 80 in open_ports or 443 in open_ports:
        if "apc" in vendor_lower or "eaton" in vendor_lower or "tripp lite" in vendor_lower:
            return "UPS / Onduleur"
        return "Web Device / AP / Camera"
    else:
        return "Generic Network Device"

def scan_single_ip(ip: str) -> dict:
    is_online = ping_host(ip)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not is_online:
        return {"ip": ip, "status": "OFFLINE", "last_seen": now_str}

    mac = get_mac_address(ip)
    open_ports = probe_open_ports(ip)
    pc_name = get_pc_name(ip, open_ports)

    return {
        "ip": ip,
        "mac": mac,
        "pc_name": pc_name,
        "open_ports": open_ports,
        "status": "ONLINE",
        "last_seen": now_str
    }

def save_and_merge_inventory(current_scan_results):
    excel_path = "network_inventory.xlsx"
    json_path = "network_inventory.json"
    now_dt = datetime.datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    # 1. Charger l'inventaire existant
    existing_inventory = []
    if os.path.exists(json_path) and os.path.getsize(json_path) > 0:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                existing_inventory = json.load(f)
        except Exception as e:
            print(f"[!] Erreur de lecture de l'inventaire existant : {e}")

    inventory_map = {item["IP Address"]: item for item in existing_inventory if "IP Address" in item}
    mac_lookup = MacLookup()

    # 2. Mettre à jour avec les résultats du scan actuel
    for res in current_scan_results:
        ip = res["ip"]
        status = res["status"]

        # HÔTE EN LIGNE
        if status == "ONLINE":
            mac = res["mac"]
            vendor = "Unknown Vendor"
            if mac != "UNKNOWN":
                try:
                    vendor = mac_lookup.lookup(mac)
                except Exception:
                    vendor = "Unregistered OUI"

            device_type = classify_device(res["open_ports"], vendor)
            pc_name = res["pc_name"] if res["pc_name"] != "N/A" else f"Host-{ip.split('.')[-1]}"

            inventory_map[ip] = {
                "IP Address": ip,
                "MAC Address": mac,
                "Device Type": device_type,
                "PC / Host Name": pc_name,
                "Original_Host_Name": pc_name,
                "Hardware Vendor": vendor,
                "Open Ports": ", ".join(map(str, res["open_ports"])),
                "Status": "ONLINE",
                "Timestamp": now_str,
                "Offline_Since": None
            }

        # HÔTE HORS LIGNE
        else:
            if ip in inventory_map:
                prev_entry = inventory_map[ip]

                # Conserver le nom initial de la machine
                if "Original_Host_Name" not in prev_entry or not prev_entry["Original_Host_Name"]:
                    prev_entry["Original_Host_Name"] = prev_entry.get("PC / Host Name", "N/A")

                # Début d'absence enregistré s'il n'existe pas encore
                offline_since_str = prev_entry.get("Offline_Since")
                if not offline_since_str:
                    offline_since_str = now_str
                    prev_entry["Offline_Since"] = offline_since_str

                # Calcul de la durée d'absence en secondes
                try:
                    offline_dt = datetime.datetime.strptime(offline_since_str, "%Y-%m-%d %H:%M:%S")
                    offline_seconds = (now_dt - offline_dt).total_seconds()
                except Exception:
                    offline_seconds = 0

                # Passage en "Free Device" si absent depuis plus de 5 minutes
                if offline_seconds >= OFFLINE_THRESHOLD_SECONDS:
                    prev_entry["PC / Host Name"] = "Free Device"
                    prev_entry["Status"] = "AVAILABLE"
                else:
                    prev_entry["Status"] = "OFFLINE"

                prev_entry["Timestamp"] = now_str

    merged_list = list(inventory_map.values())

    # 3. Sauvegarde sécurisée (JSON & Excel)
    safe_json_write(merged_list, json_path)
    df = pd.DataFrame(merged_list)
    df.to_excel(excel_path, index=False, engine='openpyxl')

    print(f"\n[✔] Balayage et mise à jour de l'inventaire terminés !")
    print(f"    - Nombre d'équipements gérés dans le master JSON : {len(merged_list)}")

def run_discovery_sweep():
    print(f"[*] Lancement du balayage de découverte sur {TARGET_SUBNET}.0/24 ...")
    ip_list = [f"{TARGET_SUBNET}.{i}" for i in IP_RANGE]
    
    scan_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        results = executor.map(scan_single_ip, ip_list)
        for res in results:
            if res:
                scan_results.append(res)

    save_and_merge_inventory(scan_results)

if __name__ == "__main__":
    run_discovery_sweep()