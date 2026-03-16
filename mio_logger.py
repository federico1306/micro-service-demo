import urllib.request
import json
import time
import csv
from datetime import datetime

URL = "http://localhost:8085/data.json"
OUTPUT_FILE = "LibreHardwareMonitorLog-Custom.csv"

def estrai_watt_da_json(nodo):
    if nodo.get("Text") == "CPU Package" and "W" in nodo.get("Value", ""):
        valore_testo = nodo.get("Value").replace(" W", "").replace(",", ".")
        try:
            return float(valore_testo)
        except:
            return None
    for figlio in nodo.get("Children", []):
        risultato = estrai_watt_da_json(figlio)
        if risultato is not None:
            return risultato
    return None

def main():
    print(" Connessione a Libre Hardware Monitor...")
    print(" REGISTRAZIONE AVVIATA!")

    with open(OUTPUT_FILE, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Time", "/intelcpu/0/power/0"])
        writer.writerow(["Time", "CPU Package"])

        try:
            while True:
                try:
                    req = urllib.request.Request(URL)
                    with urllib.request.urlopen(req) as response:
                        data = json.loads(response.read().decode('utf-8'))
                    watt = estrai_watt_da_json(data)
                    adesso = datetime.now()
                    now = adesso.strftime("%m/%d/%Y %H:%M:%S.") + adesso.strftime("%f")[:3]
                    if watt is not None:
                        writer.writerow([now, watt])
                        f.flush()
                except Exception:
                    pass
                time.sleep(0.25)
        except KeyboardInterrupt:
            print(f"\n Registrazione terminata. File: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
