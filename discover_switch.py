from scapy.all import sniff

def process_packet(pkt):
    print(f"\n[+] Switch Frame Captured!")
    print(f"    Summary: {pkt.summary()}")
    # Extract raw data strings to reveal switch hostname / IP / Port
    raw_payload = str(bytes(pkt))
    print(f"    Raw Details: {raw_payload[:200]}")

print("[*] Listening for switch CDP/LLDP broadcast frames (60s timeout)...")
# Filter Ethernet protocols: 0x2000 (CDP) or 0x88cc (LLDP)
sniff(filter="ether proto 0x88cc or ether proto 0x2000", prn=process_packet, timeout=60, store=0)
