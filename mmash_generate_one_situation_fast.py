#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAST MODE — Geração de STAI-S (Y-1, 20 itens 1..4) para uma situação cotidiana,
usando base_personas.csv como entrada. Foco em velocidade e robustez:
- prompt mínimo
- JSON estrito (force_json=True)
- batches pequenos
- resume até fechar 3.000 por temperatura
- progresso em tempo real
- opção de rodar temperaturas em paralelo (--workers N)

Saídas: ./saida_sintetico_one_situation/temp_*/{stai_respostas.csv,jsonl,progress.json,calls.log,summary.json}
"""

import argparse
import json
import math
import os
import random
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from query import query_openai  # seu wrapper com force_json=True

# ===================== CONFIG =====================
BASE_DIR = Path(".")
PERSONAS_CSV = BASE_DIR / "base_personas.csv"
OUT_DIR = BASE_DIR / "saida_sintetico_one_situation"
OUT_DIR.mkdir(exist_ok=True, parents=True)

TEMPS = [0.6, 0.75, 0.9]
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")  # precisa suportar 'temperature'

# Tuning de velocidade
BATCH_SIZE = 12
MAX_RETRIES_BATCH = 3
MAX_RETRIES_SINGLE = 2
TIMEOUT_BATCH = 45.0
TIMEOUT_SINGLE = 35.0
MIN_DELAY_SEC = 0.25

CAP_PER_TEMP = 3000
HEARTBEAT_SEC = 60

# Itens invertidos Y-1
REVERSE_STAI = {1, 2, 5, 8, 10, 11, 15, 16, 19}

# Situação do dia a dia — leve/moderada
SITUATION_TEXT = (
    "Fim de tarde em transporte público moderadamente cheio. O aplicativo informa uma mudança de rota "
    "que deve aumentar a viagem em ~25 minutos. Você tinha planejado passar na farmácia antes de fechar "
    "e talvez não consiga. Responda como você se sente AGORA (estado), não em geral."
)

GLOBAL_SEED = 1337
random.seed(GLOBAL_SEED)
# ==================================================


def compute_stai_sum_from_items(items: Dict[str, int]) -> int:
    total = 0
    for sidx, v in items.items():
        idx = int(sidx)
        vi = int(v)
        total += (5 - vi) if idx in REVERSE_STAI else vi
    return total


def classify_lifestyle(sed_ratio: float) -> str:
    if sed_ratio >= 0.50:
        return "sedentário"
    if sed_ratio >= 0.40:
        return "moderado"
    if sed_ratio >= 0.33:
        return "ativo"
    return "muito ativo"


def load_personas(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"{path} não encontrado. Rode primeiro o prepare_base_personas.py")
    df = pd.read_csv(path)
    if "id" not in df.columns or "sed_ratio" not in df.columns:
        raise SystemExit("base_personas.csv precisa ter colunas 'id' e 'sed_ratio'.")
    if "perfil" not in df.columns:
        df["perfil"] = ""
    return df


def build_batch_prompt_min(persona_list: List[Dict], situation: str) -> str:
    """
    Prompt mínimo: JSON estrito, sem comentário, sem perfil textual.
    Pede apenas: id e itens {1..20}=1..4 (inteiros).
    """
    # compacta persona para reduzir tokens
    comp = [
        {
            "id": p["id"],
            "sr": round(float(p["sed_ratio"]), 3),
            "life": p["lifestyle"],
        }
        for p in persona_list
    ]
    pj = json.dumps(comp, ensure_ascii=False)
    # instruções simples e objetivas:
    return f"""
Você receberá um ARRAY JSON de personas (id, sr, life) e UMA SITUAÇÃO (abaixo).
Para CADA persona, responda o STAI-S (Y-1, 20 itens, cada item inteiro 1..4) para como ela se sente AGORA.
RETORNE SOMENTE UM ARRAY JSON com o MESMO comprimento, onde cada objeto contém:
- "id": o mesmo id da persona
- "itens": objeto com as chaves "1".."20" mapeando para inteiros 1..4
NÃO retorne comentários, textos explicativos nem soma.
Itens invertidos (referência): {sorted(list(REVERSE_STAI))}

SITUAÇÃO:
{situation}

PERSONAS:
{pj}
""".strip()


def build_single_prompt_min(persona: Dict, situation: str) -> str:
    comp = {
        "id": persona["id"],
        "sr": round(float(persona["sed_ratio"]), 3),
        "life": persona["lifestyle"],
    }
    pj = json.dumps(comp, ensure_ascii=False)
    return f"""
Para a persona abaixo (JSON compacto) e a SITUAÇÃO, responda o STAI-S (Y-1, 20 itens, cada item inteiro 1..4).
RETORNE SOMENTE JSON com: "id" e "itens" (objeto "1".."20" -> 1..4). Sem comentários.

SITUAÇÃO:
{situation}

PERSONA:
{pj}
""".strip()


def validate_items(obj: Dict) -> Optional[Dict[str, int]]:
    items = obj.get("itens", {})
    if not isinstance(items, dict) or len(items) != 20:
        return None
    fixed = {}
    for i in range(1, 21):
        v = items.get(str(i))
        try:
            vi = int(v)                                                                                         # type: ignore
            if 1 <= vi <= 4:
                fixed[str(i)] = vi
            else:
                return None
        except Exception:
            return None
    return fixed


def parse_json_array_strict(txt: str) -> Optional[List[Dict]]:
    if not txt:
        return None
    try:
        data = json.loads(txt)
        return data if isinstance(data, list) else None
    except Exception:
        return None


def write_progress(progress_path: Path, done: int, cap: int, batch_idx: int, batches_total: int):
    remaining = max(0, cap - done)
    percent = (done / cap) * 100.0 if cap > 0 else 0.0
    payload = {
        "done": int(done),
        "remaining": int(remaining),
        "percent": round(percent, 2),
        "batch_idx": int(batch_idx),
        "batches_total": int(batches_total),
        "cap": int(cap),
    }
    progress_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_rows(csv_out: Path, jsonl_out: Path, rows: List[Dict], header_written: bool) -> bool:
    if not rows:
        return header_written
    df_chunk = pd.DataFrame(rows)
    df_chunk.to_csv(csv_out, mode="a", index=False, header=not header_written, encoding="utf-8")
    with open(jsonl_out, "a", encoding="utf-8") as fj:
        for r in rows:
            fj.write(json.dumps(r, ensure_ascii=False) + "\n")
    return True


def run_one_temperature(temp: float, personas: List[Dict], workers_hint: int = 1):
    out_temp = OUT_DIR / f"temp_{str(temp).replace('.', '_')}"
    out_temp.mkdir(exist_ok=True, parents=True)

    csv_out = out_temp / "stai_respostas.csv"
    jsonl_out = out_temp / "stai_respostas.jsonl"
    log_out = out_temp / "calls.log"
    progress_out = out_temp / "progress.json"

    done_ids = set()
    if csv_out.exists():
        try:
            done_ids = set(pd.read_csv(csv_out)["id_persona"].astype(str).tolist())
        except Exception:
            done_ids = set()

    if len(done_ids) >= CAP_PER_TEMP:
        print(f"[temp {temp}] CAP já atingido ({len(done_ids)}).")
        write_progress(progress_out, len(done_ids), CAP_PER_TEMP, 0, 0)
        return

    to_do_all = [p for p in personas if p["id"] not in done_ids]
    remaining = CAP_PER_TEMP - len(done_ids)
    if remaining <= 0:
        write_progress(progress_out, len(done_ids), CAP_PER_TEMP, 0, 0)
        return

    # corta exatamente o que falta (amostragem determinística p/ reprodutibilidade)
    if len(to_do_all) > remaining:
        random.seed(GLOBAL_SEED + int(temp * 100))
        to_do = random.sample(to_do_all, remaining)
    else:
        to_do = to_do_all

    total_batches = math.ceil(len(to_do) / BATCH_SIZE) if len(to_do) else 0
    try:
        current_done = len(pd.read_csv(csv_out)) if csv_out.exists() else len(done_ids)
    except Exception:
        current_done = len(done_ids)
    write_progress(progress_out, current_done, CAP_PER_TEMP, 0, total_batches)
    print(f"[temp {temp}] START | existentes={len(done_ids)}; faltam {len(to_do)} para CAP={CAP_PER_TEMP}; "
          f"batches ≈ {total_batches} | done={current_done} ({current_done/CAP_PER_TEMP*100:.2f}%)")

    header_written = csv_out.exists()
    last_hb = time.time()

    batches = [to_do[i:i + BATCH_SIZE] for i in range(0, len(to_do), BATCH_SIZE)]
    for b_idx, batch in enumerate(batches, start=1):
        random.shuffle(batch)

        # ---------- tentativa em batch (JSON estrito) ----------
        parsed = None
        ok = False
        for attempt in range(1, MAX_RETRIES_BATCH + 1):
            try:
                prompt = build_batch_prompt_min(batch, SITUATION_TEXT)
                raw = query_openai(
                    prompt,
                    model=MODEL,
                    temperature=float(temp),
                    force_json=True,     # JSON estrito
                    timeout=TIMEOUT_BATCH
                )
                parsed = parse_json_array_strict(raw or "")
                if parsed is not None and len(parsed) == len(batch):
                    ok = True
                    break
            except Exception as e:
                with open(log_out, "a", encoding="utf-8") as flog:
                    flog.write(json.dumps({
                        "temp": temp, "batch": b_idx, "attempt": attempt,
                        "status": "error", "err": str(e)
                    }, ensure_ascii=False) + "\n")
            time.sleep(MIN_DELAY_SEC * attempt)

        rows_ok: List[Dict] = []
        fallback_needed: List[Dict] = []

        if ok and parsed:
            by_id = {str(o.get("id", "")).strip(): o for o in parsed if isinstance(o, dict)}
            for p in batch:
                pid = p["id"]
                obj = by_id.get(pid)
                items = validate_items(obj or {})
                if not items:
                    fallback_needed.append(p)
                    continue
                stai_total = compute_stai_sum_from_items(items)
                row = {
                    "id_persona": pid,
                    "temperature": temp,
                    "situacao": "padrao_1",
                    "lifestyle": p["lifestyle"],
                    "stai_total": int(stai_total),
                }
                for i in range(1, 21):
                    row[f"stai_{i}"] = int(items[str(i)])
                rows_ok.append(row)
        else:
            # se o batch falhou inteiro, manda todos para fallback
            fallback_needed = list(batch)

        header_written = append_rows(csv_out, jsonl_out, rows_ok, header_written)

        # progresso após batch
        try:
            current_done = len(pd.read_csv(csv_out)) if csv_out.exists() else 0
        except Exception:
            current_done = 0
        write_progress(progress_out, current_done, CAP_PER_TEMP, b_idx, total_batches)
        print(f"[temp {temp}][batch {b_idx}/{total_batches}] partial done={current_done} / cap={CAP_PER_TEMP} "
              f"({current_done/CAP_PER_TEMP*100:.2f}%) | faltam={max(0, CAP_PER_TEMP - current_done)}")

        # ---------- fallback individual minimalista ----------
        for p in fallback_needed:
            single_ok = False
            for s_attempt in range(1, MAX_RETRIES_SINGLE + 1):
                try:
                    sprompt = build_single_prompt_min(p, SITUATION_TEXT)
                    raw = query_openai(
                        sprompt,
                        model=MODEL,
                        temperature=float(temp),
                        force_json=True,
                        timeout=TIMEOUT_SINGLE
                    )
                    cand = None
                    try:
                        obj = json.loads(raw or "")
                        if isinstance(obj, dict):
                            cand = obj
                        elif isinstance(obj, list) and obj:
                            cand = obj[0]
                    except Exception:
                        cand = None
                    items = validate_items(cand or {})
                    if not items:
                        time.sleep(MIN_DELAY_SEC * s_attempt)
                        continue
                    stai_total = compute_stai_sum_from_items(items)
                    row = {
                        "id_persona": p["id"],
                        "temperature": temp,
                        "situacao": "padrao_1",
                        "lifestyle": p["lifestyle"],
                        "stai_total": int(stai_total),
                    }
                    for i in range(1, 21):
                        row[f"stai_{i}"] = int(items[str(i)])
                    header_written = append_rows(csv_out, jsonl_out, [row], header_written)

                    # progresso após cada fallback
                    try:
                        current_done = len(pd.read_csv(csv_out)) if csv_out.exists() else 0
                    except Exception:
                        current_done = 0
                    write_progress(progress_out, current_done, CAP_PER_TEMP, b_idx, total_batches)

                    single_ok = True
                    break
                except Exception as e:
                    with open(log_out, "a", encoding="utf-8") as flog:
                        flog.write(json.dumps({
                            "temp": temp, "batch": b_idx, "id": p["id"],
                            "status": "single_error", "err": str(e)
                        }, ensure_ascii=False) + "\n")
                    time.sleep(MIN_DELAY_SEC * s_attempt)

            if not single_ok:
                with open(log_out, "a", encoding="utf-8") as flog:
                    flog.write(json.dumps({
                        "temp": temp, "batch": b_idx, "id": p["id"],
                        "status": "single_failed"
                    }, ensure_ascii=False) + "\n")

        # heartbeat
        now = time.time()
        if now - last_hb >= HEARTBEAT_SEC:
            try:
                current_done = len(pd.read_csv(csv_out)) if csv_out.exists() else 0
            except Exception:
                current_done = 0
            write_progress(progress_out, current_done, CAP_PER_TEMP, b_idx, total_batches)
            print(f"[temp {temp}][batch {b_idx}/{total_batches}] HEARTBEAT | "
                  f"done={current_done} / cap={CAP_PER_TEMP} ({current_done/CAP_PER_TEMP*100:.2f}%)")
            last_hb = now

        time.sleep(MIN_DELAY_SEC)

    # resumo final
    try:
        df_all = pd.read_csv(csv_out)
        if len(df_all) > CAP_PER_TEMP:
            df_all = df_all.iloc[:CAP_PER_TEMP].copy()
            df_all.to_csv(csv_out, index=False, encoding="utf-8")
        sm = float(df_all["stai_total"].mean())
        sd = float(df_all["stai_total"].std(ddof=1))
        (out_temp / "summary.json").write_text(
            json.dumps({"n": len(df_all), "stai_mean": sm, "stai_sd": sd}, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        write_progress(progress_out, len(df_all), CAP_PER_TEMP, total_batches, total_batches)
        print(f"[temp {temp}] total={len(df_all)} (CAP={CAP_PER_TEMP}); média STAI={sm:.2f} (dp={sd:.2f})")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1,
                    help="Temperaturas em paralelo (1=sequencial, 2-3 paralelos).")
    args = ap.parse_args()
    workers = max(1, min(3, int(args.workers)))

    df = load_personas(PERSONAS_CSV)
    df["lifestyle"] = df["sed_ratio"].apply(classify_lifestyle)
    personas = [
        {"id": str(r["id"]), "sed_ratio": float(r["sed_ratio"]), "lifestyle": str(r["lifestyle"])}
        for _, r in df.iterrows()
    ]
    random.seed(GLOBAL_SEED)
    random.shuffle(personas)

    temps = TEMPS[:]

    if workers == 1:
        for t in temps:
            run_one_temperature(t, personas, workers_hint=1)
    else:
        print(f"Executando temperaturas em paralelo: workers={workers}")
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(run_one_temperature, t, personas, workers): t for t in temps}
            for fut in as_completed(futs):
                t = futs[fut]
                try:
                    fut.result()
                except Exception as e:
                    print(f"[temp {t}] erro em worker: {e}")


if __name__ == "__main__":
    main()
