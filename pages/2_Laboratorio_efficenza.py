import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(page_title="Laboratorio Efficienza", layout="wide")
st.title("🧪 Laboratorio Efficienza – Analisi dei Progressi nel Tempo")
with st.expander("📘 Mostra spiegazione dei grafici e delle formule"):
    st.markdown("""
    ## 📘 Come leggere i grafici – Formule e significato

    Questa pagina analizza la tua efficienza di corsa nel tempo usando quattro indicatori chiave.
    Ogni metrica è costruita per isolare un aspetto diverso della performance.

    ---

    ### 🟦 1) Efficienza FC (solo pianura)
    Misura **quanto vai veloce per ogni battito cardiaco**.  
    È un indicatore diretto dell’efficienza aerobica.

    Formula:

    \

\[
    Eff_{FC} = \\frac{Velocità_{km/h}}{FC_{media}}
    \\]



    Calcolata **solo per dislivello ≤ 50 m** per evitare distorsioni.

    Interpretazione:
    - aumenta → stai diventando più efficiente  
    - diminuisce → stesso sforzo, meno velocità  

    ---

    ### 🟩 2) Passo vs FC (efficienza aerobica)
    Relazione tra:

    - **X:** FC media  
    - **Y:** passo (min/km)  

    La regressione mostra come cambia il passo al variare della FC.

    Interpretazione:
    - la curva scende nel tempo → miglioramento aerobico  
    - la curva sale → peggioramento o fatica residua  

    ---

    ### 🟧 3) Velocità Equivalente (per trail)
    Serve per confrontare allenamenti con dislivello diverso.  
    Aggiunge 1 km ogni 100 m di salita.

    Formula:

    \

\[
    Vel_{eq} = \\frac{Distanza_{km} + \\frac{Dislivello_{m}}{100}}{Tempo_{ore}}
    \\]



    Interpretazione:
    - aumenta → miglioramento in salita  
    - diminuisce → affaticamento o percorso impegnativo  

    ---

    ### 🟥 4) Efficienza Metabolica (TE / Tempo)
    Misura **quanto Training Effect produci per minuto**.

    Formula:

    \

\[
    Eff_{TE} = \\frac{TE}{Tempo_{minuti}}
    \\]



    Interpretazione:
    - alto → allenamento molto efficace  
    - basso → stimolo ridotto  

    ---

    ### 📈 Trendline (Regressione Lineare)
    Usata per mostrare l’evoluzione nel tempo.

    \

\[
    Trend(t) = a \\cdot t + b
    \\]



    Interpretazione:
    - **a > 0** → miglioramento  
    - **a < 0** → peggioramento  
    - **a = 0** → stabilità  

    ---
    """)

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

        # Date
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

        # Tempo
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

# Velocità km/h
df["Velocità_kmh"] = df["Distanza"] / df["Tempo_Ore"]

# Velocità equivalente (per trail)
df["Vel_eq"] = (df["Distanza"] + df["Ascesa totale"] / 100) / df["Tempo_Ore"]

# Efficienza metabolica
df["Eff_TE"] = df["TE aerobico"] / df["Tempo_Minuti"]

# ==========================================================
# FUNZIONE TRENDLINE SICURA
# ==========================================================
def safe_trendline(x, y):
    x = np.array(x)
    y = np.array(y)

    mask = (~np.isnan(x)) & (~np.isnan(y)) & (~np.isinf(y))
    x = x[mask]
    y = y[mask]

    if len(x) < 2:
        return None

    X = x.reshape(-1, 1)
    model = LinearRegression()
    model.fit(X, y)
    return model.predict(X)

# ==========================================================
# GRAFICO 1 – Efficienza FC (solo pianura)
# ==========================================================
st.subheader("📈 Efficienza FC (solo corse pianeggianti, dislivello ≤ 50 m)")

df_eff = df[df["Ascesa totale"] <= 50].copy()

if df_eff.empty or len(df_eff) < 2:
    st.info("Dati insufficienti per calcolare l'efficienza FC su percorsi pianeggianti.")
else:
    df_eff["Eff_FC"] = df_eff["Velocità_kmh"] / df_eff["FC Media"]

    x_days = (df_eff["Data"] - df_eff["Data"].min()).dt.days.values
    trend = safe_trendline(x_days, df_eff["Eff_FC"].values)

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=df_eff["Data"],
        y=df_eff["Eff_FC"],
        mode="markers+lines",
        name="Efficienza FC",
        line=dict(width=2)
    ))

    if trend is not None:
        fig1.add_trace(go.Scatter(
            x=df_eff["Data"],
            y=trend,
            name="Trend",
            line=dict(color="yellow", dash="dash", width=3)
        ))

    fig1.update_layout(template="plotly_dark")
    st.plotly_chart(fig1, width="stretch")

# ==========================================================
# GRAFICO 2 – Passo vs FC
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
# GRAFICO 3 – Velocità equivalente
# ==========================================================
st.subheader("⛰️ Velocità Equivalente (per trail)")

x_days = (df["Data"] - df["Data"].min()).dt.days.values
trend_vel = safe_trendline(x_days, df["Vel_eq"].values)

fig3 = go.Figure()
fig3.add_trace(go.Scatter(
    x=df["Data"],
    y=df["Vel_eq"],
    mode="markers+lines",
    name="Vel_eq"
))

if trend_vel is not None:
    fig3.add_trace(go.Scatter(
        x=df["Data"],
        y=trend_vel,
        name="Trend",
        line=dict(color="orange", dash="dash")
    ))

fig3.update_layout(template="plotly_dark")
st.plotly_chart(fig3, width="stretch")

# ==========================================================
# GRAFICO 4 – Efficienza metabolica
# ==========================================================
st.subheader("🔥 Efficienza Metabolica (TE / Tempo)")

trend_te = safe_trendline(x_days, df["Eff_TE"].values)

fig4 = go.Figure()
fig4.add_trace(go.Scatter(
    x=df["Data"],
    y=df["Eff_TE"],
    mode="markers+lines",
    name="Efficienza TE"
))

if trend_te is not None:
    fig4.add_trace(go.Scatter(
        x=df["Data"],
        y=trend_te,
        name="Trend",
        line=dict(color="green", dash="dash")
    ))

fig4.update_layout(template="plotly_dark")
st.plotly_chart(fig4, width="stretch")

# ==========================================================
# TABELLA FINALE
# ==========================================================
st.subheader("📋 Tabella completa delle metriche")
st.dataframe(df[[
    "Data", "Tipo di attivita", "Distanza", "Ascesa totale",
    "Tempo_Minuti", "FC Media", "Velocità_kmh", "Vel_eq", "Eff_TE"
]], use_container_width=True)
