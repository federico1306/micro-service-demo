import urllib.request
import json
import sys

# Lookback in ms: opzionale come argv[1] (es. "python fetch_traces.py 330000")
# Default: 60000 ms = 1 minuto
LOOKBACK_MS = int(sys.argv[1]) if len(sys.argv) > 1 else 60000

ZIPKIN_URL  = f"http://localhost:9411/api/v2/traces?limit=10000&lookback={LOOKBACK_MS}"
OUTPUT_FILE = "dataset_tesi.json"

def main():
    print(f" Scarico tracce Zipkin (lookback={LOOKBACK_MS}ms)...")
    try:
        req = urllib.request.Request(ZIPKIN_URL)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f" ERRORE connessione Zipkin: {e}")
        return

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    n_trace = len(data)
    n_span  = sum(len(t) for t in data)
    print(f" Salvate {n_trace} tracce, {n_span} span totali → {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
