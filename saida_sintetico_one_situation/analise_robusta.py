#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Análise robusta (sem GUI) dos JSONLs de respostas STAI.
- Lê JSONL(s) em chunks, combina e limpa.
- Limita em 3.000 linhas por temperatura (0.60, 0.75, 0.90).
- Gera PNGs e CSVs em ./resultados_tcc2 (sem abrir janelas).
- Sem seaborn, só matplotlib (backend 'Agg') para evitar BSOD/driver.

Uso básico:
    python analise_robusta.py --glob "stai_respostas*.jsonl"

Uso com várias pastas/arquivos:
    python analise_robusta.py --glob "saida_sintetico_one_situation/**/*.jsonl"
"""

import os, sys, json, math, argparse, glob, textwrap, datetime, random
from pathlib import Path
import numpy as np
import pandas as pd

# Backend não interativo -> nenhuma janela gráfica
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# -------- Config padrão --------
OUT_DIR = Path("./resultados_tcc2")
OUT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR = OUT_DIR / "figuras"
TAB_DIR = OUT_DIR / "tabelas"
LOG = OUT_DIR / "exec.log"
for d in (IMG_DIR, TAB_DIR):
    d.mkdir(parents=True, exist_ok=True)

random.seed(42)
np.random.seed(42)

TEMPS_VALIDAS = {0.60, 0.75, 0.90}
LIMS_POR_TEMP = 3000  # limite por temperatura

def log(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LOG.write_text((LOG.read_text(encoding="utf-8") if LOG.exists() else "") + f"[{ts}] {msg}\n", encoding="utf-8")
    print(msg)

def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue

def carregar_jsonls(glob_pattern: str) -> pd.DataFrame:
    files = sorted([Path(p) for p in glob.glob(glob_pattern, recursive=True)])
    if not files:
        log(f"Nenhum arquivo encontrado para glob: {glob_pattern}")
        return pd.DataFrame()

    rows = []
    for p in files:
        log(f"Lendo: {p}")
        for rec in iter_jsonl(p):
            # Esperados: id_persona/id, temperature, lifestyle, stai_total ou 20 itens
            d = {}
            # ids / campos possíveis
            d["id"] = rec.get("id_persona") or rec.get("id") or rec.get("sid") or ""
            # temperature pode vir string/float
            temp = rec.get("temperature") or rec.get("temp")
            try:
                d["temperature"] = round(float(temp), 2) if temp is not None else None
            except Exception:
                d["temperature"] = None

            # lifestyle
            d["lifestyle"] = (rec.get("lifestyle") or rec.get("estilo") or rec.get("estilo_vida") or "").strip().lower()

            # stai_total pode estar pronto…
            stai_total = rec.get("stai_total") or rec.get("stai_soma") or rec.get("stai_score")
            # …ou vir como lista/dict de itens
            itens = rec.get("itens") or rec.get("stai_items") or {}
            # normaliza itens
            itens_norm = {}
            if isinstance(itens, dict):
                itens_norm = {str(k): itens[k] for k in itens.keys()}
            elif isinstance(itens, list) and len(itens) == 20:
                itens_norm = {str(i+1): itens[i] for i in range(20)}
            # se houver itens itemizados stai_1..stai_20:
            for k in range(1, 21):
                key1 = f"stai_{k}"
                if key1 in rec:
                    itens_norm[str(k)] = rec[key1]

            # tenta calcular soma se não veio pronta
            if stai_total is None and itens_norm:
                # itens 1..4, clamp e inverte os padrões do STAI-Y1: {1,2,5,8,10,11,15,16,19}
                rev = {1,2,5,8,10,11,15,16,19}
                som = 0
                ok = True
                for k in range(1, 21):
                    v = itens_norm.get(str(k))
                    try:
                        v = int(round(float(v)))
                        v = 1 if v < 1 else (4 if v > 4 else v)
                        if k in rev:
                            v = 5 - v
                        som += v
                    except Exception:
                        ok = False
                        break
                if ok:
                    stai_total = som

            d["stai_total"] = int(stai_total) if stai_total is not None else None

            # sed_ratio (se existir):
            sdr = rec.get("sed_ratio") or rec.get("sedentarismo") or rec.get("indice_sed")
            try:
                d["sed_ratio"] = float(sdr) if sdr is not None else None
            except Exception:
                d["sed_ratio"] = None

            rows.append(d)

    df = pd.DataFrame(rows)
    return df

def limpar_e_capar(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    # normaliza lifestyle
    def norm_l(s):
        s = (s or "").strip().lower()
        if s.startswith("sed"):
            return "sedentário"
        if s.startswith("ati") or s.startswith("ativo"):
            return "ativo"
        if s.startswith("mod"):
            return "moderado"
        return s or "indef"
    df["lifestyle"] = df["lifestyle"].apply(norm_l)

    # filtra temperaturas válidas
    df = df[df["temperature"].isin(TEMPS_VALIDAS)].copy()

    # garante ints válidos 20..80
    df = df[pd.notna(df["stai_total"])]
    df["stai_total"] = pd.to_numeric(df["stai_total"], errors="coerce")
    df = df[(df["stai_total"] >= 20) & (df["stai_total"] <= 80)].copy()

    # cap por temperatura
    out_parts = []
    for t in sorted(TEMPS_VALIDAS):
        dft = df[df["temperature"] == t]
        if len(dft) > LIMS_POR_TEMP:
            dft = dft.sample(LIMS_POR_TEMP, random_state=42)
        out_parts.append(dft)
    out = pd.concat(out_parts, ignore_index=True)
    return out

# ---------- Gráficos utilitários ----------
def save_bar(x, y, title, ylabel, path):
    fig, ax = plt.subplots(figsize=(8, 5), dpi=160)
    ax.bar(x, y)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("")
    for xi, yi in zip(range(len(x)), y):
        ax.text(xi, yi, f"{yi:.2f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)

def save_boxplot(groups, data, title, ylabel, path):
    fig, ax = plt.subplots(figsize=(8, 5), dpi=160)
    ax.boxplot(data, showfliers=False)
    ax.set_xticklabels(groups)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)

def save_hist(data, bins, title, xlabel, path):
    fig, ax = plt.subplots(figsize=(8, 5), dpi=160)
    ax.hist(data, bins=bins, edgecolor="black")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Frequência")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)

def save_scatter(x, y, title, xlabel, ylabel, path):
    fig, ax = plt.subplots(figsize=(6, 6), dpi=160)
    ax.scatter(x, y, s=8, alpha=0.4)
    # regressão simples se possível
    try:
        m, b = np.polyfit(x, y, 1)
        xx = np.linspace(min(x), max(x), 100)
        yy = m*xx + b
        ax.plot(xx, yy)
        # correlação
        corr = np.corrcoef(x, y)[0,1]
        ax.text(0.02, 0.98, f"r = {corr:.3f}", transform=ax.transAxes, va="top")
    except Exception:
        pass
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", required=True, help="Padrão glob para localizar .jsonl (com aspas). Ex: \"stai_respostas*.jsonl\"")
    args = ap.parse_args()

    log(f"INÍCIO – padrão glob: {args.glob}")
    df_raw = carregar_jsonls(args.glob)
    if df_raw.empty:
        log("Nada carregado. Encerrando.")
        return
    df = limpar_e_capar(df_raw)

    # salva base limpa capada
    base_csv = TAB_DIR / "00_base_limpa_capada.csv"
    df.to_csv(base_csv, index=False, encoding="utf-8-sig")
    log(f"Base limpa/capada: {base_csv} (linhas={len(df)})")

    # Tabelas resumo
    # 1) por temperatura
    resumo_temp = df.groupby("temperature")["stai_total"].agg(["count", "mean", "std", "min", "max"]).reset_index()
    resumo_temp.to_csv(TAB_DIR / "01_resumo_por_temperatura.csv", index=False, encoding="utf-8-sig")

    # 2) por temperatura x lifestyle
    resumo_tl = df.groupby(["temperature", "lifestyle"])["stai_total"].agg(["count", "mean", "std"]).reset_index()
    resumo_tl.to_csv(TAB_DIR / "02_resumo_temp_x_lifestyle.csv", index=False, encoding="utf-8-sig")

    # 3) distribuição de lifestyle por temp
    dist_life = (df
                 .groupby(["temperature", "lifestyle"])["id"]
                 .count()
                 .reset_index()
                 .rename(columns={"id":"n"}))
    dist_life.to_csv(TAB_DIR / "03_distribuicao_lifestyle_por_temp.csv", index=False, encoding="utf-8-sig")

    # 4) se existir sed_ratio, correlação por temp
    if "sed_ratio" in df.columns and df["sed_ratio"].notna().any():
        corr_rows = []
        for t in sorted(TEMPS_VALIDAS):
            dft = df[(df["temperature"] == t) & pd.notna(df["sed_ratio"])]
            if len(dft) >= 10:
                r = np.corrcoef(dft["sed_ratio"], dft["stai_total"])[0,1]
                corr_rows.append({"temperature": t, "pearson_r": r, "n": len(dft)})
                save_scatter(
                    dft["sed_ratio"].values, dft["stai_total"].values,
                    title=f"Sedentarismo × STAI-S (temp={t})",
                    xlabel="sed_ratio (0–1)", ylabel="STAI-S",
                    path=IMG_DIR / f"scatter_sed_vs_stai_temp_{str(t).replace('.','_')}.png"
                )
        pd.DataFrame(corr_rows).to_csv(TAB_DIR / "04_correlacoes_sed_stai.csv", index=False, encoding="utf-8-sig")
    else:
        log("Aviso: sed_ratio ausente; gráficos/correlações de dispersão não serão gerados.")

    # Gráficos principais
    # A) média STAI por temperatura (barra)
    save_bar(
        x=[str(t) for t in resumo_temp["temperature"]],
        y=resumo_temp["mean"].tolist(),
        title="Média do STAI-S por temperatura",
        ylabel="STAI-S (média)",
        path=IMG_DIR / "bar_media_stai_por_temperatura.png"
    )

    # B) boxplots por temperatura
    grupos = []
    dados = []
    for t in sorted(TEMPS_VALIDAS):
        dft = df[df["temperature"] == t]["stai_total"].values
        if len(dft):
            grupos.append(str(t))
            dados.append(dft)
    if dados:
        save_boxplot(
            groups=grupos,
            data=dados,
            title="Distribuição do STAI-S por temperatura",
            ylabel="STAI-S",
            path=IMG_DIR / "box_stai_por_temperatura.png"
        )

    # C) média STAI por estilo de vida dentro de cada temperatura
    for t in sorted(TEMPS_VALIDAS):
        dft = df[df["temperature"] == t]
        if dft.empty:
            continue
        g = dft.groupby("lifestyle")["stai_total"].mean().reset_index()
        save_bar(
            x=g["lifestyle"].tolist(),
            y=g["stai_total"].tolist(),
            title=f"Média do STAI-S por estilo de vida (temp={t})",
            ylabel="STAI-S (média)",
            path=IMG_DIR / f"bar_media_stai_por_lifestyle_temp_{str(t).replace('.','_')}.png"
        )

    # D) histogramas por temp
    for t in sorted(TEMPS_VALIDAS):
        dft = df[df["temperature"] == t]["stai_total"].values
        if len(dft):
            save_hist(
                data=dft, bins=15,
                title=f"Histograma STAI-S (temp={t})",
                xlabel="STAI-S",
                path=IMG_DIR / f"hist_stai_temp_{str(t).replace('.','_')}.png"
            )

    # E) tabela “Médias por temp x lifestyle” em CSV já foi gerada (02_resumo_temp_x_lifestyle.csv)

    # README explicando saídas
    readme = textwrap.dedent(f"""
    Resultados gerados em: {OUT_DIR.resolve()}

    Pastas:
      - figuras/  -> PNGs prontos para o TCC
      - tabelas/  -> CSVs com resumos para anexar/analisar

    Limites e regras:
      - Cada temperatura foi limitada a no máximo {LIMS_POR_TEMP} linhas (0.60, 0.75, 0.90).
      - Foram mantidas apenas linhas com STAI-S entre 20 e 80.
      - 'sed_ratio' só é usado se existir nos JSONLs (senão correlação/dispensões são pulados).

    Principais arquivos:
      figuras/bar_media_stai_por_temperatura.png
      figuras/box_stai_por_temperatura.png
      figuras/bar_media_stai_por_lifestyle_temp_0_6.png
      figuras/bar_media_stai_por_lifestyle_temp_0_75.png
      figuras/bar_media_stai_por_lifestyle_temp_0_9.png
      figuras/hist_stai_temp_0_6.png, hist_stai_temp_0_75.png, hist_stai_temp_0_9.png
      figuras/scatter_sed_vs_stai_temp_*.png (se 'sed_ratio' estiver presente)

      tabelas/00_base_limpa_capada.csv
      tabelas/01_resumo_por_temperatura.csv
      tabelas/02_resumo_temp_x_lifestyle.csv
      tabelas/03_distribuicao_lifestyle_por_temp.csv
      tabelas/04_correlacoes_sed_stai.csv (apenas se houver 'sed_ratio')

    """).strip()
    (OUT_DIR / "README.txt").write_text(readme, encoding="utf-8")
    log("OK – análise concluída.")

if __name__ == "__main__":
    # Evita problemas de permissão do matplotlib em Windows
    os.environ.setdefault("MPLCONFIGDIR", str((OUT_DIR / ".mplcache").resolve()))
    (OUT_DIR / ".mplcache").mkdir(parents=True, exist_ok=True)
    main()
