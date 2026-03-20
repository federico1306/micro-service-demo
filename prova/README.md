# Cartella PROVA - Test Rapido

## Scopo
Questa cartella contiene uno script di prova per verificare che tutto funzioni correttamente prima di lanciare la campagna completa.

## Cosa fa `run_prova.py`
- Esegue **3 test totali** (uno per blocco utenti: 10, 25, 50)
- Ogni test dura **5 minuti**
- Pausa di **5 minuti** tra blocchi (raffreddamento CPU)
- Durata totale: **~25 minuti**

## Come utilizzare

### Prerequisiti
1. Docker Compose avviato: `docker-compose up -d`
2. LibreHardwareMonitor attivo su porta 8085
3. Gateway risponde: `curl http://localhost:8222/api/v1/students`
4. Zipkin risponde: `curl http://localhost:9411/api/v2/services`

### Esecuzione

```bash
cd C:\Users\berar\Documents\micro-service-demo\prova
python run_prova.py
```

### Output
```
prova/risultati/
  ├─ blocco_1_10utenti/test_01/
  │   ├─ LibreHardwareMonitorLog-Custom.csv
  │   ├─ dataset_tesi.json
  │   ├─ dataset_con_energia.json
  │   ├─ dataset_con_energia_LIGHT.json
  │   └─ risultati_jmeter.csv
  ├─ blocco_2_25utenti/test_01/
  └─ blocco_3_50utenti/test_01/
```

## Dopo la prova

Se tutto funziona correttamente, puoi lanciare la campagna completa dalla cartella padre:

```bash
cd ..
python run_all_experiments.py
```

Questo eseguirà **30 test totali** (10 ripetizioni per ogni blocco).
