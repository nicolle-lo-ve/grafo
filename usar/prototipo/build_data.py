#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_data.py — Motor de datos del prototipo "Contrataciones — Espacio de Riesgo".

Acepta CUALQUIERA de las dos salidas del notebook fase1_Preprocesamiento.ipynb:
  • adjudicaciones_procesadas.parquet  (tabla rica, 38 cols: fecha, proveedor,
                                        departamento, alertas...)  → experiencia completa
  • matriz_modelo.parquet              (matriz ML, 20 cols: SIN fecha/proveedor/
                                        departamento/alertas)       → versión reducida

Completa la limpieza pendiente, construye el vector PCA-ready (log montos +
Min-Max) y lo serializa a  data/cp_data.js  (window.CP_DATA).

Adaptaciones automáticas según el esquema disponible:
  - Los flags de riesgo (sobrecosto / sin competencia / plazo corto) se
    RECALCULAN desde porc_adjudicado, num_licitantes_final y dias_plazo
    (columnas presentes en ambas tablas), aunque no existan las columnas alerta_*.
  - Si no hay `fecha_adjudicacion`  -> meta.has_time = False (el cuadrante D del
    prototipo muestra el histograma de nº de postores en lugar de la serie).
  - Si no hay `nombre_proveedor` / `dept_entidad` -> el tooltip los omite.

Ejecutar:  python build_data.py [ruta_al_parquet]
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

HERE = Path(__file__).resolve().parent
OUT_JS = HERE / "data" / "cp_data.js"

PARQUET_NAMES = ["adjudicaciones_procesadas.parquet", "matriz_modelo.parquet"]
CANDIDATES = [d / n for d in (HERE, HERE.parent, HERE.parent.parent, HERE / "data")
              for n in PARQUET_NAMES]

FEATURE_DEF = [
    ("monto_adjudicado_pen",   "log"),
    ("monto_referencial_pen",  "log"),
    ("monto_contrato",         "log"),
    ("monto_promedio_previo",  "log"),
    ("num_licitantes_final",   "lin"),
    ("num_contratos_previos",  "log"),
    ("dias_plazo",             "lin"),
    ("duracion_contrato_dias", "lin"),
    ("porc_adjudicado",        "lin"),
    ("es_consorcio",           "lin"),
    ("tiene_contrato",         "lin"),
    ("metodo_desconocido",     "lin"),
]
FEATURES = [f for f, _ in FEATURE_DEF]
JUNK_COL = "Entrega compilada:Adjudicaciones:Valor:Nombre de Moneda"


def log(m=""):
    print(m, flush=True)


def find_parquet() -> Path:
    if len(sys.argv) > 1:
        p = Path(sys.argv[1])
        if p.exists():
            return p
        sys.exit(f"ERROR: no existe el parquet indicado: {p}")
    for c in CANDIDATES:
        if c.exists():
            return c
    sys.exit(
        "ERROR: no se encontró el parquet de entrada.\n"
        "  Esperaba 'adjudicaciones_procesadas.parquet' o 'matriz_modelo.parquet'.\n"
        "  Ejecuta el notebook fase1_Preprocesamiento.ipynb o pasa la ruta:\n"
        "    python build_data.py C:/ruta/adjudicaciones_procesadas.parquet"
    )


def encode(df, col, fillna="(s/d)"):
    if col not in df.columns:
        return [0] * len(df), ["(no disponible)"], False
    s = df[col].astype("object").where(df[col].notna(), fillna).astype(str)
    levels = sorted(s.unique().tolist())
    idx = s.map({v: i for i, v in enumerate(levels)}).astype(int)
    return idx.tolist(), levels, True


def main():
    pq = find_parquet()
    log("=" * 66)
    log("  MOTOR DE DATOS — Contrataciones: Espacio de Riesgo")
    log("=" * 66)
    log(f"\n[1/5] Cargando {pq.name} ...")
    df = pd.read_parquet(pq)
    log(f"      {len(df):,} filas × {df.shape[1]} columnas")

    # ── Limpieza/finalización ────────────────────────────────────────────
    log("\n[2/5] Limpieza/finalización...")
    df = df.drop(columns=[JUNK_COL, "proveedor_fuera_region", "alerta_proveedor_lejano"],
                 errors="ignore")

    has_time = "fecha_adjudicacion" in df.columns
    n0 = len(df)
    df["monto_adjudicado_pen"] = pd.to_numeric(df["monto_adjudicado_pen"], errors="coerce")
    keep = df["monto_adjudicado_pen"].notna()
    if has_time:
        df["fecha_adjudicacion"] = pd.to_datetime(df["fecha_adjudicacion"], errors="coerce")
        keep &= df["fecha_adjudicacion"].notna()
    df = df[keep].copy()
    log(f"      Filtradas {n0 - len(df):,} filas sin monto PEN" +
        (" / sin fecha" if has_time else "") + f" -> {len(df):,} filas")
    log(f"      Fecha disponible (serie temporal): {has_time}")

    # Imputaciones razonadas
    for c in ["monto_contrato", "duracion_contrato_dias", "num_contratos_previos",
              "monto_acum_proveedor", "monto_promedio_previo",
              "es_consorcio", "tiene_contrato", "metodo_desconocido"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["dias_plazo"] = pd.to_numeric(df.get("dias_plazo"), errors="coerce")
    df["dias_plazo"] = df["dias_plazo"].fillna(df["dias_plazo"].median())
    df["porc_adjudicado"] = pd.to_numeric(df.get("porc_adjudicado"), errors="coerce")
    df["porc_adjudicado"] = df["porc_adjudicado"].fillna(df["porc_adjudicado"].median()).clip(0, 300)
    df["num_licitantes_final"] = pd.to_numeric(df.get("num_licitantes_final"), errors="coerce").fillna(1)
    for c in FEATURES:
        if c not in df.columns:
            df[c] = 0.0
            log(f"      ⚠ feature ausente '{c}' -> 0")

    # ── Riesgo: RECALCULADO desde columnas siempre presentes ─────────────
    a_sobre = (df["porc_adjudicado"] > 120).astype(int)
    a_sincomp = (df["num_licitantes_final"] == 1).astype(int)
    a_plazo = df["dias_plazo"].between(-1, 2).astype(int)
    df["riesgo"] = (a_sobre + a_sincomp + a_plazo).astype(int)
    df["alert_mask"] = (a_sobre + 2 * a_plazo + 4 * a_sincomp).astype(int)

    # ── Matriz PCA ───────────────────────────────────────────────────────
    log("\n[3/5] Transformación (log montos) + Min-Max...")
    M = np.zeros((len(df), len(FEATURE_DEF)), dtype=float)
    for j, (feat, tr) in enumerate(FEATURE_DEF):
        col = pd.to_numeric(df[feat], errors="coerce").fillna(0).to_numpy(dtype=float)
        M[:, j] = np.log1p(np.clip(col, 0, None)) if tr == "log" else col
    Xn = MinMaxScaler().fit_transform(M)
    log(f"      {len(FEATURES)} features normalizadas en [0,1]")

    # ── Categóricas + arrays de visualización ────────────────────────────
    log("\n[4/5] Codificación y arrays de visualización...")
    metodo_idx, metodo_lv, _ = encode(df, "metodo_contratacion_limpio")
    categ_idx,  categ_lv,  _ = encode(df, "categoria_principal")
    dept_idx,   dept_lv,  has_dept = encode(df, "dept_entidad")
    prov_idx,   prov_lv,  has_prov = encode(df, "nombre_proveedor")

    def disp(col, ndig=2):
        return [round(float(v), ndig) for v in pd.to_numeric(df[col], errors="coerce").fillna(0)]

    payload = {
        "meta": {
            "label": "Contrataciones Perú 2025 (OCDS / SEACE)",
            "note": f"{len(df):,} adjudicaciones · {pq.name} · features log+MinMax · riesgo 0-3",
            "features": FEATURES,
            "methods": metodo_lv, "categories": categ_lv,
            "depts": dept_lv, "providers": prov_lv,
            "alerts": ["Sobrecosto", "Plazo corto", "Sin competencia"],
            "has_time": bool(has_time), "has_prov": bool(has_prov), "has_dept": bool(has_dept),
            "n": int(len(df)),
        },
        "metodo": metodo_idx, "categoria": categ_idx, "dept": dept_idx, "prov": prov_idx,
        "riesgo": df["riesgo"].tolist(), "amask": df["alert_mask"].tolist(),
        "monto": disp("monto_adjudicado_pen", 2), "montoref": disp("monto_referencial_pen", 2),
        "porc": disp("porc_adjudicado", 1), "numlic": [int(v) for v in df["num_licitantes_final"]],
        "dias": disp("dias_plazo", 0), "dur": disp("duracion_contrato_dias", 0),
        "X": [[round(float(Xn[i, j]), 4) for i in range(Xn.shape[0])]
              for j in range(Xn.shape[1])],
    }
    if has_time:
        payload["t"] = df["fecha_adjudicacion"].values.astype("datetime64[ms]").astype("int64").tolist()

    log("\n[5/5] Serializando data/cp_data.js ...")
    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_JS.write_text("window.CP_DATA = " + json.dumps(payload, separators=(",", ":")) + ";",
                      encoding="utf-8")
    size_mb = OUT_JS.stat().st_size / (1024 * 1024)

    assert Xn.min() >= -1e-9 and Xn.max() <= 1 + 1e-9, "Min-Max fuera de [0,1]"
    assert not np.isnan(Xn).any(), "Quedan NaN en la matriz"
    log(f"      -> {OUT_JS}  ({size_mb:.2f} MB)")
    log(f"      registros={len(df):,}  has_time={has_time}  has_prov={has_prov}  has_dept={has_dept}")
    log(f"      métodos={metodo_lv}")
    log(f"      riesgo (conteo): {df['riesgo'].value_counts().sort_index().to_dict()}")
    log("\n" + "=" * 66)
    log("  LISTO. Abre cts/prototipo/index.html")
    log("=" * 66)


if __name__ == "__main__":
    main()