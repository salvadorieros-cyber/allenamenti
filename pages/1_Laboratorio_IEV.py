import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Laboratorio IEV", layout="wide")

st.title("🧪 Laboratorio Indice Efficienza Verticale (IEV)")

# =====================================================
# PARAMETRI PESO (MODIFICABILI PER TEST)
# =====================================================
peso_iniziale = 78.0   # kg all'inizio periodo
peso_finale   = 74.5   # kg alla fine periodo
peso_riferimento = 70  # kg di riferimento fisiologico

# =====================================================
# CARICAMENTO DATI
# =====================================================
@st.cache_data
def load_data():
    return pd.read_csv("allenamenti.csv", parse_dates=["Data"])

try:
    df = load_data()
except Exception as e:
    st.error(f"Errore caricamento dati: {e}")
    st.stop()

if df.empty:
    st.warning("Database vuoto")
    st.stop()

# =====================================================
# FILTRI DATA
# =====================================================
col1, col2 = st.columns(2)

with col1:
    data_start = st.date_input(
        "Data inizio",
        df["Data"].min().date()
    )

with col2:
    data_end = st.date_input(
        "Data fine",
        df["Data"].max().date()
    )

df_f = df[
    (df["Data"] >= pd.to_datetime(data_start)) &
    (df["Data"] <= pd.to_datetime(data_end))
].copy()

if df_f.empty:
    st.warning("Nessun allenamento nel periodo selezionato")
    st.stop()

# =====================================================
# PULIZIA DATI NUMERICI
# =====================================================
numeric_cols = [
    "Passo_Decimale",
    "FC Media",
    "FC max",
    "Ascesa totale",
    "Tempo_Minuti"
]

for col in numeric_cols:
    df_f[col] = pd.to_numeric(df_f[col], errors="coerce")

df_f.dropna(subset=numeric_cols, inplace=True)

# =====================================================
# INTERPOLAZIONE PESO SU BASE TEMPORALE
# =====================================================
data_min = df_f["Data"].min()
data_max = df_f["Data"].max()

durata_giorni = max((data_max - data_min).days, 1)

df_f["Peso_interp"] = peso_iniziale + (
    (df_f["Data"] - data_min).dt.days / durata_giorni
) * (peso_finale - peso_iniziale)

df_f["fattore_peso"] = df_f["Peso_interp"] / peso_riferimento

# =====================================================
# CALCOLI IEV
# =====================================================
# Velocità m/s
df_f["vel_ms"] = 1000 / df_f["Passo_Decimale"] / 60

# Frequenza cardiaca relativa
df_f["FC_rel"] = df_f["FC Media"] / df_f["FC max"]

# Lavoro verticale (m/min)
df_f["Lavoro_vert"] = df_f["Ascesa totale"] / df_f["Tempo_Minuti"]

# IEV con peso
df_f["IEV_peso"] = (
    df_f["vel_ms"] /
    (
        df_f["FC_rel"] *
        (1 + df_f["Lavoro_vert"] / 10) *
        df_f["fattore_peso"]
    )
)

df_f["IEV_peso_plot"] = df_f["IEV_peso"] * 100

# =====================================================
# GRAFICO
# =====================================================
fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=df_f["Data"],
        y=df_f["IEV_peso_plot"],
        mode="lines+markers",
        name="IEV (con peso)",
        line=dict(width=3)
    )
)

fig.add_trace(
    go.Scatter(
        x=df_f["Data"],
        y=df_f["Peso_interp"],
        mode="lines",
        name="Peso stimato (kg)",
        yaxis="y2",
        line=dict(dash="dot")
    )
)

fig.update_layout(
    title="Indice di Efficienza vs Peso nel tempo",
    xaxis_title="Data",
    yaxis=dict(title="IEV"),
    yaxis2=dict(
        title="Peso (kg)",
        overlaying="y",
        side="right"
    ),
    height=500
)

st.plotly_chart(fig, use_container_width=True)

# =====================================================
# TABELLA DI CONTROLLO
# =====================================================
with st.expander("📊 Dati calcolati"):
    st.dataframe(
        df_f[
            [
                "Data",
                "Passo_Decimale",
                "FC Media",
                "Ascesa totale",
                "Peso_interp",
                "IEV_peso_plot"
            ]
        ].sort_values("Data", ascending=False),
        use_container_width=True
    )
