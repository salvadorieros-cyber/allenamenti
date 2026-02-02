import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title="Laboratorio IEV", layout="wide")

st.title("🧪 Laboratorio IEV – Efficienza con Peso")

# ======================================================
# 1. LETTURA DATABASE (MULTIPAGE SAFE)
# ======================================================
@st.cache_data
def load_data():
    try:
        base_path = Path(__file__).resolve().parent.parent
        db_path = base_path / "allenamenti.db"

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_name = cursor.fetchone()[0]

        df = pd.read_sql(f"SELECT * FROM '{table_name}'", conn)
        conn.close()

        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")

        # Pulizia numerica
        num_cols = ["FC Media", "FC max", "Distanza", "Ascesa totale"]
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        # Tempo
        df["Tempo_TD"] = pd.to_timedelta(df["Tempo"], errors="coerce")
        df["Tempo_min"] = df["Tempo_TD"].dt.total_seconds() / 60

        # Passo mm:ss → decimale
        def passo_to_dec(p):
            try:
                m, s = str(p).split(":")
                return int(m) + int(s) / 60
            except:
                return None

        df["Passo_dec"] = df["Passo medio"].apply(passo_to_dec)

        return df.dropna(subset=["Data", "Passo_dec", "FC Media", "Tempo_min"])

    except Exception as e:
        st.error(f"Errore caricamento dati: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.stop()

# ======================================================
# 2. INPUT PESO (INTERPOLAZIONE)
# ======================================================
st.sidebar.header("⚖️ Peso Atleta")

peso_start = st.sidebar.number_input("Peso iniziale (kg)", value=75.0)
data_start = st.sidebar.date_input("Data peso iniziale", df["Data"].min())

peso_end = st.sidebar.number_input("Peso finale (kg)", value=72.0)
data_end = st.sidebar.date_input("Data peso finale", df["Data"].max())

# interpolazione lineare peso nel tempo
df["peso"] = peso_start + (
    (df["Data"] - pd.to_datetime(data_start)).dt.days /
    max((pd.to_datetime(data_end) - pd.to_datetime(data_start)).days, 1)
) * (peso_end - peso_start)

df["peso"] = df["peso"].clip(lower=40, upper=120)

# ======================================================
# 3. FORMULA IEV CON PESO (NUOVA)
# ======================================================
"""
IEV_peso =
    velocità (m/s)
    -------------------------
    FC_relativa × peso × carico verticale
"""

df["vel_ms"] = 1000 / (df["Passo_dec"] * 60)
df["FC_rel"] = df["FC Media"] / df["FC max"]
df["carico_vert"] = 1 + (df["Ascesa totale"] / df["Tempo_min"]) / 10

df["IEV_peso"] = df["vel_ms"] / (df["FC_rel"] * df["peso"] * df["carico_vert"])
df["IEV_plot"] = df["IEV_peso"] * 1000  # scala visiva

# ======================================================
# 4. GRAFICO
# ======================================================
st.subheader("📈 Andamento IEV (normalizzato per Peso)")

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df["Data"],
    y=df["IEV_plot"],
    mode="lines+markers",
    name="IEV peso"
))

fig.update_layout(
    template="plotly_dark",
    yaxis_title="Indice Efficienza (peso-normalizzato)",
    xaxis_title="Data"
)

st.plotly_chart(fig, use_container_width=True)

# ======================================================
# 5. DEBUG VISIVO
# ======================================================
with st.expander("🔍 Dettaglio calcolo"):
    st.dataframe(
        df[[
            "Data", "Passo_dec", "FC Media", "peso",
            "vel_ms", "FC_rel", "carico_vert", "IEV_plot"
        ]].sort_values("Data"),
        use_container_width=True
    )
