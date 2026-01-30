import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
import google.generativeai as genai

# ==========================================
# 1. CONFIGURAZIONE PAGINA (PRIMA DI TUTTO)
# ==========================================
st.set_page_config(page_title="Fitness AI Dashboard", layout="wide")

# ==========================================
# 2. CONFIGURAZIONE GEMINI (STREAMLIT CLOUD)
# ==========================================
API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=API_KEY)

# ==========================================
# 3. CARICAMENTO E PREPARAZIONE DATI
# ==========================================
@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect("Allenamenti.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        table_name = cursor.fetchone()[0]

        df = pd.read_sql_query(f"SELECT * FROM '{table_name}'", conn)
        conn.close()

        # Date
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")

        # Conversioni numeriche
        cols_num = [
            "Calorie", "FC Media", "FC max", "TE aerobico",
            "Cadenza media", "Distanza", "Ascesa totale"
        ]

        for col in cols_num:
            if col in df.columns:
                df[col] = (
                    df[col].astype(str)
                    .str.replace(".", "", regex=False)
                    .str.replace(",", ".", regex=False)
                    .astype(float)
                )

        # Training Effect scala 0–50 → 0–5
        if "TE aerobico" in df.columns and df["TE aerobico"].mean() > 10:
            df["TE aerobico"] /= 10

        # Tempo in minuti
        df["Tempo_TD"] = pd.to_timedelta(df["Tempo"], errors="coerce")
        df["Tempo_Minuti"] = df["Tempo_TD"].dt.total_seconds() / 60

        # Passo "5:30" → 5.5
        def passo_dec(p):
            try:
                m, s = str(p).split(":")
                return int(m) + int(s) / 60
            except:
                return None

        df["Passo_Decimale"] = df["Passo medio"].apply(passo_dec)

        return df.dropna(subset=["Data"])

    except Exception as e:
        st.error(f"Errore DB: {e}")
        return pd.DataFrame()

# ==========================================
# 4. ZONE CARDIO
# ==========================================
def assegna_zona(fc, z1, z2, z3, z4):
    if fc <= z1: return "Z1 (Recupero)"
    elif fc <= z2: return "Z2 (Fondo)"
    elif fc <= z3: return "Z3 (Tempo)"
    elif fc <= z4: return "Z4 (Soglia)"
    else: return "Z5 (Massimale)"

# ==========================================
# 5. GEMINI – COACH AI
# ==========================================
def chiedi_a_gemini(sintesi):
    try:
        model = genai.GenerativeModel("models/text-bison-002")

        prompt = f"""
Sei un coach di endurance esperto.

Dati sintetici atleta:
{sintesi}

Analizza:
1. Stato di forma ed efficienza aerobica
2. Distribuzione delle zone cardiache
3. Suggerimenti pratici per i prossimi allenamenti

Rispondi in italiano, in modo tecnico ma chiaro.
"""

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return f"❌ Coach AI non disponibile: {e}"

# ==========================================
# 6. AUTENTICAZIONE
# ==========================================
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Accesso Riservato")
    pw = st.text_input("Password", type="password")
    if st.button("Accedi"):
        if pw == "elgnaro":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Password errata")

# ==========================================
# 7. DASHBOARD
# ==========================================
else:
    df = load_data()

    if df.empty:
        st.warning("Database non trovato o vuoto")
        st.stop()

    # SIDEBAR
    st.sidebar.header("🎯 Filtri")

    sport = st.sidebar.multiselect(
        "Sport",
        df["Tipo di attivita"].unique(),
        default=df["Tipo di attivita"].unique()
    )

    date_range = st.sidebar.date_input(
        "Periodo",
        [df["Data"].min().date(), df["Data"].max().date()]
    )

    z1 = st.sidebar.number_input("Z1", 120)
    z2 = st.sidebar.number_input("Z2", 140)
    z3 = st.sidebar.number_input("Z3", 155)
    z4 = st.sidebar.number_input("Z4", 170)

    df["Zona Cardio"] = df["FC Media"].apply(
        lambda x: assegna_zona(x, z1, z2, z3, z4)
    )

    mask = (
        df["Tipo di attivita"].isin(sport) &
        (df["Data"].dt.date >= date_range[0]) &
        (df["Data"].dt.date <= date_range[1])
    )

    df_f = df.loc[mask].sort_values("Data")

    tabs = st.tabs(["📉 Trend", "📊 Performance", "🔥 Zone", "🤖 Coach AI", "📋 Dati"])

    # ---------- TREND ----------
    with tabs[0]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_f["Data"], y=df_f["Passo_Decimale"],
            name="Passo", yaxis="y1"
        ))
        fig.add_trace(go.Scatter(
            x=df_f["Data"], y=df_f["FC Media"],
            name="FC", yaxis="y2"
        ))
        fig.update_layout(
            yaxis=dict(autorange="reversed", title="Passo"),
            yaxis2=dict(overlaying="y", side="right", title="FC"),
            template="plotly_dark"
        )
        st.plotly_chart(fig, use_container_width=True)

    # ---------- PERFORMANCE ----------
    with tabs[1]:
        fig = px.scatter(
            df_f, x="Tempo_Minuti", y="TE aerobico",
            color="Tipo di attivita", size="Calorie",
            trendline="ols", template="plotly_dark"
        )
        st.plotly_chart(fig, use_container_width=True)

    # ---------- ZONE ----------
    with tabs[2]:
        fig = px.box(
            df_f, x="Zona Cardio", y="Passo_Decimale",
            template="plotly_dark"
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

    # ---------- COACH AI ----------
    with tabs[3]:
        df_f["Indice_Eff"] = (1 / df_f["Passo_Decimale"]) / df_f["FC Media"] * 1000

        recenti = df_f[df_f["Data"] >= df_f["Data"].max() - timedelta(days=30)]

        if not recenti.empty:
            eff = recenti["Indice_Eff"].mean()

            st.metric("Efficienza Aerobica (30gg)", f"{eff:.2f}")

            if st.button("🚀 Analisi Coach AI"):
                sintesi = {
                    "efficienza_media": round(eff, 2),
                    "zone": recenti["Zona Cardio"].value_counts().to_dict(),
                    "sport": recenti["Tipo di attivita"].unique().tolist()
                }
                with st.spinner("Il coach sta analizzando..."):
                    st.write(chiedi_a_gemini(sintesi))
        else:
            st.info("Dati insufficienti ultimi 30 giorni")

    # ---------- DATI ----------
    with tabs[4]:
        st.dataframe(df_f, use_container_width=True)
