# Cartella TEST - Micro-Service-Demo Energy Profiling

## Descrizione

Questa cartella contiene tutti gli script necessari per eseguire test di carico con misurazione energetica automatica su micro-service-demo (Students/Schools).

## File Presenti

### Esecuzione Test
- **`run_all_experiments.py`** - Campagna completa automatizzata
  - 3 blocchi utenti: [10, 25, 50]
  - 10 ripetizioni per blocco
  - Durata: 5 min per test
  - Pause: 1 min tra test, 5 min tra blocchi
  - Totale: 30 test (~3.5 ore)
  - Include reset automatico Zipkin tra test

- **`run_experiment.py`** - Test singolo veloce
  - 10 utenti, 60 secondi
  - Utile per verifiche rapide

### Utility (automaticamente invocati)
- **`mio_logger.py`** - Logger hardware (CPU Package Watt ogni 250ms)
- **`fetch_traces.py`** - Scarica tracce da Zipkin
- **`energy_injector.py`** - Calcola e inietta energia negli span

### Analisi Risultati
- **`analisi_campagna.py`** - Analisi automatica completa campagna
  - Genera 3 grafici PNG statistici
  - Statistiche aggregate per blocco

- **`genera_grafici.py`** - Grafici interattivi (modalità manuale)
- **`grafico_energia_span_ripetizioni.py`** - Line + box plot span
- **`grafico_heatmap_energia_timeline.py`** - Heatmap timeline completa
- **`grafico_energia_span_temporale_blocco.py`** - Grafico temporale dettagliato

## Prerequisiti

**Prima di eseguire qualsiasi test:**

1. **Docker Compose avviato**
   ```bash
   cd C:\Users\berar\Documents\micro-service-demo
   docker-compose up -d
   ```

2. **LibreHardwareMonitor attivo** su porta 8085
   - Apri LibreHardwareMonitor GUI
   - Options → Remote Web Server → porta 8085
   - Verifica: `curl http://localhost:8085/data.json`

3. **Servizi funzionanti**
   ```bash
   curl http://localhost:8222/api/v1/students  # Gateway
   curl http://localhost:9411/api/v2/services  # Zipkin
   ```

4. **Zipkin in salute** (importante!)
   - Le tracce sono in-memory, Zipkin può crashare se sovraccaricato
   - Prima di campagne lunghe: `docker-compose restart zipkin`

## Uso

### Test Singolo Rapido (1 minuto)
```bash
cd C:\Users\berar\Documents\micro-service-demo\TEST
python run_experiment.py
```

**Output:** file nella stessa cartella TEST

### Campagna Completa (30 test, ~3.5 ore)
```bash
cd C:\Users\berar\Documents\micro-service-demo\TEST
python run_all_experiments.py
```

**Output:** `risultati/blocco_X_Yutenti/test_ZZ/`

Ogni test genera:
- `LibreHardwareMonitorLog-Custom.csv` - Misure hardware
- `risultati_jmeter.csv` - Performance JMeter
- `dataset_tesi.json` - Tracce Zipkin originali
- `dataset_con_energia.json` - Tracce con energia iniettata
- `dataset_con_energia_LIGHT.json` - Prime 20 tracce (debug)

### Analisi Campagna
```bash
cd C:\Users\berar\Documents\micro-service-demo\TEST
python analisi_campagna.py
```

**Output:** `grafici_campagna/` con 3 grafici PNG

### Altri Script di Analisi

```bash
# Energia span attraverso ripetizioni
python grafico_energia_span_ripetizioni.py

# Heatmap timeline completa
python grafico_heatmap_energia_timeline.py

# Grafico temporale blocco specifico
python grafico_energia_span_temporale_blocco.py
```

## Configurazione Personalizzata

### Modificare parametri campagna completa

Apri `run_all_experiments.py` e modifica:

```python
BLOCCHI_UTENTI       = [10, 25, 50]   # Cambia livelli di carico
N_TEST_PER_BLOCCO    = 10             # Cambia numero ripetizioni
DURATA_TEST_SECONDI  = 300            # Cambia durata singolo test
PAUSA_TRA_TEST_S     = 60             # Pausa tra test
PAUSA_TRA_BLOCCHI_S  = 300            # Pausa tra blocchi
```

### Modificare test singolo

Apri `run_experiment.py` e modifica:

```python
N_UTENTI = 10      # Numero utenti concorrenti
DURATA_S = 60      # Durata test in secondi
```

## Workflow Energia

1. **Logger hardware** registra CPU Package Watt ogni 250ms
2. **10s calibrazione** a riposo → calcola tara (consumo baseline)
3. **Stress test** JMeter → continua registrazione
4. **Stop logger** → salva CSV
5. **Fetch Zipkin** → scarica tracce con lookback = durata + 30s
6. **Energy Injector** → calcola energia netta, distribuisce proporzionalmente a `cpu.nanos`

## Troubleshooting

### Zipkin crash durante campagna
- I container mostrano: "Up 4 minutes" = restart recente
- Soluzione: `docker-compose restart zipkin` prima di iniziare
- La campagna include reset automatico tra test

### Nessuna energia negli span
- Verifica che gli span abbiano il tag `cpu.nanos`
- Solo gli span di students/schools hanno cpu.nanos
- Gli span del gateway (routing) hanno energy=0 → normale

### JMeter non trovato
- Verifica path: `C:\apache-jmeter-5.6.3\bin\jmeter.bat`
- Modifica `JMETER_BIN` negli script se necessario

### LibreHardwareMonitor non risponde
- Apri GUI LibreHardwareMonitor
- Options → Remote Web Server → porta 8085
- Test: `curl http://localhost:8085/data.json`

## Note

- **Output separato dalla cartella prova**: questa cartella TEST è indipendente da `../prova/`
- **Reset Zipkin automatico**: la campagna completa resetta Zipkin tra ogni test
- **Tara dinamica**: energia netta = energia totale - (tara × durata)
- **CPU Proportional**: energia distribuita in base ai `cpu.nanos` effettivi degli span
