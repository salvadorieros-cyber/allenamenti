import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
import numpy as np
from datetime import timedelta

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="Laboratorio Efficienza", layout="wide")
st.title("🧪 Laboratorio Efficienza – Analisi dei Progressi nel Tempo")

# ==========================================================
# LOAD DATA
# ==========================================================
@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect("Allenamenti.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        table = cursor.fetchone()
        if table is None:
            return pd.DataFrame()

        df = pd.read_sql_query(f"SELECT * FROM '{table[0]}'", conn)
        conn.close()

        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")

        # Conversioni numeriche
        numeric_cols = ["FC Media", "Distanza", "Ascesa totale", "Calorie", "TE aerobico"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(".", "", regex=False)
                    .str.replace(",", ".", regex=False)
                )
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Tempo in minuti e ore
        if "Tempo" in df.columns:
            df["Tempo_TD"] = pd.to_timedelta(df["Tempo"], errors="coerce")
            df["Tempo_Minuti"] = df["Tempo_TD"].dt.total_seconds() / 60
            df["Tempo_Ore"] = df["Tempo_TD"].dt.total_seconds() / 3600

        # Passo decimale
        if "Passo medio" in df.columns:
            def passo_dec(p):
                try:
                    m, s = str(p).split(":")
                    return int(m) + int(s)/60
                except:
                    return None
            df["Passo_Decimale"] = df["Passo medio"].apply(passo_dec)

        return df.dropna(subset=["Data"])

    except Exception as e:
        st.error(f"Errore caricamento dati: {e}")
        return pd.DataFrame()


df = load_data()
if df.empty:
    st.warning("Database non trovato o vuoto.")
    st.stop()

# ==========================================================
# SIDEBAR – FILTRI
# ==========================================================
st.sidebar.header("🎯 Filtri")

sport = st.sidebar.multiselect(
    "Tipo di attività",
    sorted(df["Tipo di attivita"].dropna().unique()),
    default=df["Tipo di attivita"].dropna().unique()
)

date_range = st.sidebar.date_input(
    "Intervallo temporale",
    [df["Data"].min().date(), df["Data"].max().date()]
)

df = df[
    (df["Tipo di attivita"].isin(sport)) &
    (df["Data"].dt.date >= date_range[0]) &
    (df["Data"].dt.date <= date_range[1])
].copy()

if df.empty:
    st.warning("Nessun dato corrispondente ai filtri.")
    st.stop()

# ==========================================================
# CALCOLO METRICHE DI EFFICIENZA
# ==========================================================

# Efficienza FC → velocità / FC
df["Velocità_kmh"] = df["Distanza"] / df["Tempo_Ore"]
df["Eff_FC"] = df["Velocità_kmh"] / df["FC Media"]

# Velocità equivalente (per trail)
df["Vel_eq"] = (df["Distanza"] + df["Ascesa totale"] / 100) / df["Tempo_Ore"]

# Efficienza metabolica
df["Eff_TE"] = df["TE aerobico"] / df["Tempo_Minuti"]

# ==========================================================
# FUNZIONE TRENDLINE
# ==========================================================
def trendline(x, y):
    X = np.array(x).reshape(-1, 1)
    model = LinearRegression()
    model.fit(X, y)
    return model.predict(X)

# ==========================================================
# GRAFICO 1 – Efficienza FC nel tempo
# ==========================================================
st.subheader("📈 Efficienza FC (Velocità / FC)")

df["Trend_Eff_FC"] = trendline(
    (df["Data"] - df["Data"].min()).dt.days,
    df["Eff_FC"]
)

fig1 = go.Figure()
fig1.add_trace(go.Scatter(x=df["Data"], y=df["Eff_FC"], mode="markers+lines", name="Efficienza FC"))
fig1.add_trace(go.Scatter(x=df["Data"], y=df["Trend_Eff_FC"], name="Trend", line=dict(color="yellow", dash="dash")))
fig1.update_layout(template="plotly_dark")
st.plotly_chart(fig1, width="stretch")

# ==========================================================
# GRAFICO 2 – Passo vs FC (efficienza aerobica)
# ==========================================================
st.subheader("💓 Efficienza Aerobica (Passo vs FC)")

fig2 = px.scatter(
    df,
    x="FC Media",
    y="Passo_Decimale",
    color="Data",
    trendline="ols",
    template="plotly_dark"
)
fig2.update_yaxes(autorange="reversed")
st.plotly_chart(fig2, width="stretch")


# ==========================================================
# GRAFICO 3 – Velocità equivalente nel tempo
# ==========================================================
st.subheader("⛰️ Velocità Equivalente (per trail)")

# Pulizia dati per evitare crash nella regressione
df = df.dropna(subset=["Vel_eq"])
df = df[df["Vel_eq"].replace([np.inf, -np.inf], np.nan).notna()]

if len(df) > 1:
    df["Trend_Vel_eq"] = trendline(
        (df["Data"] - df["Data"].min()).dt.days,
        df["Vel_eq"]
    )

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=df["Data"],

# ==========================================================
# GRAFICO 4 – Efficienza metabolica (TE / Tempo)
# ==========================================================
st.subheader("🔥 Efficienza Metabolica (TE / Tempo)")

df["Trend_Eff_TE"] = trendline(
    (df["Data"] - df["Data"].min()).dt.days,
    df["Eff_TE"]
)

fig4 = go.Figure()
fig4.add_trace(go.Scatter(x=df["Data"], y=df["Eff_TE"], mode="markers+lines", name="Efficienza TE"))
fig4.add_trace(go.Scatter(x=df["Data"], y=df["Trend_Eff_TE"], name="Trend", line=dict(color="green", dash="dash")))
fig4.update_layout(template="plotly_dark")
st.plotly_chart(fig4, width="stretch")

# ==========================================================
# TABELLA FINALE
# ==========================================================
st.subheader("📋 Tabella completa delle metriche")
st.dataframe(df[[
    "Data", "Tipo di attivita", "Distanza", "Ascesa totale",
    "Tempo_Minuti", "FC Media", "Velocità_kmh", "Eff_FC",
    "Vel_eq", "Eff_TE"
]], use_container_width=True)
