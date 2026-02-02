import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="Laboratorio IEV", layout="wide")

# ==========================================================
# LOAD DATA FROM SQLITE
# ==========================================================
@st.cache_data
def load_data():
    try:
        base_path = Path(__file__).resolve().parent.parent
        db_path = base_path / "Allenamenti.db"

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        table = cursor.fetchone()
        if table is None:
            return pd.DataFrame()

        df = pd.read_sql_query(f"SELECT * FROM '{table[0]}'", conn)
        conn.close()

        # --- DATE ---
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")

        # --- NUMERIC CLEAN ---
        numeric_cols = [
            "FC Media", "Distanza", "Ascesa totale",
            "Calorie", "TE aerobico"
        ]

        for col in numeric_cols:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(".", "", regex=False)
                    .str.replace(",", ".", regex=False)
                )
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # --- TIME ---
        if "Tempo" in df.columns:
            df["Tempo_TD"] = pd.to_timedelta(df["Tempo"], errors="coerce")
            df["Tempo_Ore"] = df["Tempo_TD"].dt.total_seconds() / 3600

        # --- PACE ---
        if "Passo medio" in df.columns:
            def pace_to_float(p):
                try:
                    m, s = str(p).split(":")
                    return int(m) + int(s) / 60
                except:
                    return None

            df["Passo_Decimale"] = df["Passo medio"].apply(pace_to_float)

        return df.dropna(subset=["Data"])

    except Exception as e:
        st.error(f"Errore caricamento dati: {e}")
        return pd.DataFrame()


# ==========================================================
# APP
# ==========================================================
st.title("🧪 Laboratorio IEV – Efficienza Reale")

df = load_data()
if df.empty:
    st.warning("Database non trovato o vuoto.")
    st.stop()

# ==========================================================
# SIDEBAR – PESO
# ==========================================================
st.sidebar.header("⚖️ Peso atleta")

col1, col2 = st.sidebar.columns(2)

with col1:
    peso_start = st.number_input(
        "Peso iniziale (kg)", 40.0, 120.0, 75.0, 0.1
    )
    data_start = st.date_input(
        "Data peso iniziale", df["Data"].min().date()
    )

with col2:
    peso_end = st.number_input(
        "Peso finale (kg)", 40.0, 120.0, 72.0, 0.1
    )
    data_end = st.date_input(
        "Data peso finale", df["Data"].max().date()
    )

# ==========================================================
# PESO INTERPOLATO
# ==========================================================
days_total = max(
    (pd.to_datetime(data_end) - pd.to_datetime(data_start)).days, 1
)

df["Peso"] = peso_start + (
    (df["Data"] - pd.to_datetime(data_start)).dt.days / days_total
) * (peso_end - peso_start)

df["Peso"] = df["Peso"].clip(40, 120)

# ==========================================================
# FORMULA IEV (CORRETTA E NON PIATTA)
# ==========================================================
"""
IEV = ( Velocità_equivalente ) / ( FC * Peso )

Velocità_equivalente = (Distanza + Dislivello/100) / Ore
"""

df = df.dropna(subset=[
    "Distanza", "Ascesa totale", "Tempo_Ore",
    "FC Media", "Peso"
])

df["Vel_eq"] = (df["Distanza"] + df["Ascesa totale"] / 100) / df["Tempo_Ore"]

df["IEV"] = df["Vel_eq"] / (df["FC Media"] * df["Peso"]) * 1000

# ==========================================================
# GRAFICO
# ==========================================================
st.subheader("📈 Andamento Efficienza (IEV)")

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df["Data"],
    y=df["IEV"],
    mode="lines+markers",
    name="IEV",
    line=dict(width=3)
))

fig.add_trace(go.Scatter(
    x=df["Data"],
    y=df["Peso"],
    name="Peso (kg)",
    yaxis="y2",
    line=dict(dash="dot")
))

fig.update_layout(
    template="plotly_dark",
    yaxis=dict(title="Indice Efficienza IEV"),
    yaxis2=dict(
        title="Peso (kg)",
        overlaying="y",
        side="right",
        showgrid=False
    ),
    legend=dict(orientation="h", y=1.15)
)

st.plotly_chart(fig, use_container_width=True)

# ==========================================================
# DEBUG TABLE
# ==========================================================
with st.expander("📋 Dati di calcolo"):
    st.dataframe(df[[
        "Data", "Distanza", "Ascesa totale",
        "Tempo_Ore", "FC Media", "Peso",
        "Vel_eq", "IEV"
    ]])
