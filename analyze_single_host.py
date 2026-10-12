import os
import json
import pandas as pd

TARGET_IP = "IP-HERE"
EXCEL_LOG_FILE = "single_coupures_reseau.xlsx"
JSON_LOG_FILE = "single_outage_logs.json"

def analyze_host_outages(target_ip):
    df = pd.DataFrame()

    # 1. Load data from JSON or Excel
    if os.path.exists(JSON_LOG_FILE):
        try:
            with open(JSON_LOG_FILE, "r") as f:
                data = json.load(f)
                if data:
                    df = pd.DataFrame(data)
        except Exception as e:
            print(f"[!] JSON load error: {e}")

    if df.empty and os.path.exists(EXCEL_LOG_FILE):
        try:
            df = pd.read_excel(EXCEL_LOG_FILE)
        except Exception as e:
            print(f"[!] Excel load error: {e}")

    if df.empty:
        print(f"[!] No outage logs found in `{EXCEL_LOG_FILE}` or `{JSON_LOG_FILE}`.")
        return

    # Filter records specifically for target_ip
    host_df = df[df['IP Address'].astype(str) == target_ip]

    if host_df.empty:
        print(f"[✔] No outage records found for IP: {target_ip}")
        return

    # Calculate statistics
    total_drops = len(host_df)
    total_downtime = host_df['Duration (Seconds)'].sum() if 'Duration (Seconds)' in host_df.columns else 0
    avg_downtime = host_df['Duration (Seconds)'].mean() if 'Duration (Seconds)' in host_df.columns else 0
    host_name = host_df['PC / Host Name'].iloc[0] if 'PC / Host Name' in host_df.columns else "N/A"

    print("\n" + "="*60)
    print(f" 🔍 DEEP DIVE REPORT FOR HOST: {target_ip} ({host_name})")
    print("="*60)
    print(f"• Total Disconnection Events : {total_drops}")
    print(f"• Total Downtime             : {round(total_downtime, 1)} seconds ({round(total_downtime/60, 2)} minutes)")
    print(f"• Average Outage Duration   : {round(avg_downtime, 1)} seconds")
    print("-" * 60)
    print("📋 DETAILED DISCONNECTION TIMELINE:")
    
    # Display breakdown of disconnections
    display_cols = [col for col in ['Outage Start', 'Outage End', 'Duration (Seconds)', 'Status'] if col in host_df.columns]
    print(host_df[display_cols].to_string(index=False))
    print("="*60)

    # Root Cause Diagnostic Suggestion
    print("\n💡 POSSIBLE ROOT CAUSES BASED ON DISCONNECTION PATTERNS:")
    if avg_downtime < 15:
        print(" ➔ Flapping / Micro-Cuts (< 15s avg duration):")
        print("   - Loose RJ45 connector or faulty patch cable.")
        print("   - Corrupted/outdated NIC driver or power-saving mode (EEE) enabled.")
        print("   - Unstable Wi-Fi signal or IP address collision on DHCP.")
    elif total_drops > 10 and avg_downtime >= 30:
        print(" ➔ Intermittent Power / Edge Port Flap:")
        print("   - Loose power cord or faulty wall socket at workstation.")
        print("   - User frequently putting PC to sleep or rebooting.")
        print("   - Port speed/duplex mismatch on the switch interface.")

if __name__ == "__main__":
    analyze_host_outages(TARGET_IP)