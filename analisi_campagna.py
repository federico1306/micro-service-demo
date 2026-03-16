import json
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

# ================================================================
# CONFIGURAZIONE
# ================================================================

SCRIPT_DIR    = Path(__file__).parent
RISULTATI_DIR = SCRIPT_DIR / "risultati"
OUTPUT_DIR    = SCRIPT_DIR / "grafici_campagna"

COLORI = ["#2196F3", "#FF9800", "#4CAF50"]


# ================================================================
# LETTURA DATI
# ================================================================

def leggi_metriche_test(test_dir):
    json_path = test_dir / "dataset_con_energia.json"
    if not json_path.exists():
        return None

    with open(json_path, "r", encoding="utf-8") as f:
        spans = json.load(f)

    energia_totale   = 0.0
    cpu_nanos_totale = 0
    span_data        = []

    for span in spans:
        tags = span.get("tags", {})
        energy_j = float(tags.get("energy.joules", 0))
        energia_totale += energy_j

        if "cpu.nanos" in tags:
            cpu_nanos_totale += int(tags["cpu.nanos"])

        duration_us = span.get("duration", 0)
        if energy_j > 0 and duration_us > 0:
            span_data.append((duration_us / 1000.0, energy_j))

    if energia_totale == 0:
        return None

    costo_per_nano = energia_totale / cpu_nanos_totale if cpu_nanos_totale > 0 else 0

    return {
        "energia_totale_j": energia_totale,
        "costo_per_nano":   costo_per_nano,
        "span_data":        span_data,
    }


def carica_tutti_dati():
    if not RISULTATI_DIR.exists():
        print(f"[!] Cartella risultati non trovata: {RISULTATI_DIR}")
        return []

    blocchi = []
    for blocco_dir in sorted(RISULTATI_DIR.iterdir()):
        if not blocco_dir.is_dir() or not blocco_dir.name.startswith("blocco_"):
            continue
        try:
            n_utenti = int(blocco_dir.name.split("_")[-1].replace("utenti", ""))
        except (ValueError, IndexError):
            continue

        metriche = []
        for test_dir in sorted(blocco_dir.iterdir()):
            if not test_dir.is_dir() or not test_dir.name.startswith("test_"):
                continue
            m = leggi_metriche_test(test_dir)
            if m is not None:
                metriche.append(m)

        if metriche:
            blocchi.append({"n_utenti": n_utenti, "nome": blocco_dir.name, "metriche": metriche})
            print(f"  {blocco_dir.name}: {len(metriche)} test caricati")

    return blocchi


# ================================================================
# GRAFICI
# ================================================================

def grafico_boxplot_energia(blocchi, ax):
    dati      = [[m["energia_totale_j"] for m in b["metriche"]] for b in blocchi]
    etichette = [f"{b['n_utenti']} utenti" for b in blocchi]

    bp = ax.boxplot(dati, patch_artist=True, widths=0.5)
    for patch, colore in zip(bp["boxes"], COLORI):
        patch.set_facecolor(colore)
        patch.set_alpha(0.75)
    for median in bp["medians"]:
        median.set_color("black")
        median.set_linewidth(2)

    ax.set_title("Distribuzione Energia Netta per Blocco di Carico", fontsize=12, fontweight="bold")
    ax.set_xlabel("Carico (N. Utenti)", fontsize=11)
    ax.set_ylabel("Energia Netta Totale (Joule)", fontsize=11)
    ax.set_xticklabels(etichette)
    ax.grid(True, axis="y", linestyle="--", alpha=0.6)


def grafico_trend_energia(blocchi, ax):
    utenti = [b["n_utenti"] for b in blocchi]
    medie  = [np.mean([m["energia_totale_j"] for m in b["metriche"]]) for b in blocchi]
    stds   = [np.std( [m["energia_totale_j"] for m in b["metriche"]]) for b in blocchi]

    ax.errorbar(utenti, medie, yerr=stds,
                fmt="-o", color="#1976D2", linewidth=2,
                markersize=8, capsize=6, capthick=2, elinewidth=1.5,
                label="Media ± σ")
    for u, m in zip(utenti, medie):
        ax.annotate(f"{m:.1f} J", (u, m),
                    textcoords="offset points", xytext=(0, 12),
                    ha="center", fontsize=9)

    ax.set_title("Trend Energia Media al Crescere del Carico", fontsize=12, fontweight="bold")
    ax.set_xlabel("Carico (N. Utenti)", fontsize=11)
    ax.set_ylabel("Energia Netta Media (Joule)", fontsize=11)
    ax.set_xticks(utenti)
    ax.legend(fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.6)


def grafico_costo_nano(blocchi, ax):
    dati      = [[m["costo_per_nano"] for m in b["metriche"] if m["costo_per_nano"] > 0]
                 for b in blocchi]
    etichette = [f"{b['n_utenti']} utenti" for b in blocchi]

    bp = ax.boxplot(dati, patch_artist=True, widths=0.5)
    for patch, colore in zip(bp["boxes"], COLORI):
        patch.set_facecolor(colore)
        patch.set_alpha(0.75)
    for median in bp["medians"]:
        median.set_color("black")
        median.set_linewidth(2)

    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.2e}"))
    ax.set_title("Efficienza CPU: Costo Energetico per Nanosecondo", fontsize=12, fontweight="bold")
    ax.set_xlabel("Carico (N. Utenti)", fontsize=11)
    ax.set_ylabel("Costo CPU (Joule / Nanosecondo)", fontsize=11)
    ax.set_xticklabels(etichette)
    ax.grid(True, axis="y", linestyle="--", alpha=0.6)


def grafico_scatter_correlazione(blocchi, ax):
    patches = []
    for blocco, colore in zip(blocchi, COLORI):
        tutti_span = []
        for m in blocco["metriche"]:
            tutti_span.extend(m["span_data"])
        if not tutti_span:
            continue

        durate  = [s[0] for s in tutti_span]
        energie = [s[1] for s in tutti_span]

        ax.scatter(durate, energie, alpha=0.25, color=colore, s=12, edgecolors="none")

        z     = np.polyfit(durate, energie, 1)
        x_rng = np.linspace(min(durate), max(durate), 200)
        ax.plot(x_rng, np.poly1d(z)(x_rng), color=colore, linewidth=2, linestyle="--")

        r = np.corrcoef(durate, energie)[0, 1]
        patches.append(mpatches.Patch(
            color=colore,
            label=f"{blocco['n_utenti']} utenti  (r = {r:.2f}, n = {len(durate)})"
        ))

    ax.set_title("Correlazione Latenza–Energia per Livello di Carico", fontsize=12, fontweight="bold")
    ax.set_xlabel("Durata Operazione (ms)", fontsize=11)
    ax.set_ylabel("Energia Operazione (Joule)", fontsize=11)
    ax.legend(handles=patches, fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.6)


def grafico_variabilita(blocchi, ax):
    etichette = [f"{b['n_utenti']} utenti" for b in blocchi]
    cv_valori = []

    for b in blocchi:
        valori = [m["energia_totale_j"] for m in b["metriche"]]
        media  = np.mean(valori)
        std    = np.std(valori)
        cv_valori.append((std / media * 100) if media > 0 else 0)

    bars = ax.bar(etichette, cv_valori,
                  color=COLORI[: len(blocchi)], alpha=0.85,
                  edgecolor="black", linewidth=0.8)
    for bar, cv in zip(bars, cv_valori):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.15,
                f"{cv:.1f}%", ha="center", va="bottom",
                fontsize=11, fontweight="bold")

    ax.axhline(y=10, color="red", linestyle="--", linewidth=1.5,
               label="Soglia 10% (accettabile)")
    ax.set_title("Riproducibilità: Coefficiente di Variazione (CV%)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Carico (N. Utenti)", fontsize=11)
    ax.set_ylabel("CV%  (σ / μ × 100)", fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(True, axis="y", linestyle="--", alpha=0.6)
    ax.set_ylim(0, max(cv_valori) * 1.5 + 2)


# ================================================================
# MAIN
# ================================================================

def main():
    print("=" * 60)
    print("  ANALISI AUTOMATICA CAMPAGNA — MICRO-SERVICE-DEMO")
    print("=" * 60)

    OUTPUT_DIR.mkdir(exist_ok=True)

    print("\nCaricamento dati da risultati/ ...")
    blocchi = carica_tutti_dati()

    if not blocchi:
        print("\n[!] Nessun dato trovato. Esegui prima run_all_experiments.py.")
        return

    n_test_totali = sum(len(b["metriche"]) for b in blocchi)
    print(f"\nTotale: {len(blocchi)} blocchi, {n_test_totali} test caricati.\n")

    fig1, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig1.suptitle("Analisi Energetica — School/Student Microservices", fontsize=14, fontweight="bold")
    grafico_boxplot_energia(blocchi, ax1)
    grafico_trend_energia(blocchi, ax2)
    fig1.tight_layout()
    out1 = OUTPUT_DIR / "01_energia_distribuzione_trend.png"
    fig1.savefig(out1, dpi=300)
    plt.close(fig1)
    print(f"Salvato: {out1.name}")

    fig2, (ax3, ax4) = plt.subplots(1, 2, figsize=(14, 6))
    fig2.suptitle("Efficienza CPU e Riproducibilità — School/Student Microservices", fontsize=14, fontweight="bold")
    grafico_costo_nano(blocchi, ax3)
    grafico_variabilita(blocchi, ax4)
    fig2.tight_layout()
    out2 = OUTPUT_DIR / "02_efficienza_variabilita.png"
    fig2.savefig(out2, dpi=300)
    plt.close(fig2)
    print(f"Salvato: {out2.name}")

    fig3, ax5 = plt.subplots(figsize=(10, 7))
    grafico_scatter_correlazione(blocchi, ax5)
    fig3.tight_layout()
    out3 = OUTPUT_DIR / "03_correlazione_latenza_energia.png"
    fig3.savefig(out3, dpi=300)
    plt.close(fig3)
    print(f"Salvato: {out3.name}")

    print("\n--- REPORT STATISTICO ---")
    for b in blocchi:
        valori = [m["energia_totale_j"] for m in b["metriche"]]
        media  = np.mean(valori)
        std    = np.std(valori)
        cv     = std / media * 100 if media > 0 else 0
        print(f"\n  {b['n_utenti']} utenti  ({len(valori)} test):")
        print(f"    Energia media : {media:.2f} J")
        print(f"    Std dev       : {std:.2f} J")
        print(f"    CV%           : {cv:.1f}%")
        print(f"    Min / Max     : {min(valori):.2f} J  /  {max(valori):.2f} J")

    print(f"\nTutti i grafici in: {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
