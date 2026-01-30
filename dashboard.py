import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
import google.generativeai as genai

# ==========================================
# 1. CONFIGURAZIONE PAGINA
# ==========================================
st.set_page_config(page_title="Fitness AI Dashboard", layout="wide")

# ==========================================
# 2. CONFIGURAZIONE GEMINI AI
# ==========================================
API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=API_KEY)

# ==========================================
# 3. CARICAMENTO DATI
# ==========================================
@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect("Allenamenti.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        table = cursor.fetchone()
        if not table:
            st.warning("Database vuoto")
            return pd.DataFrame()
        table_name = table[0]

        df = pd.read_sql_query(f"SELECT * FROM '{table_name}'", conn)
        conn.close()

        # Pulizia valori non numerici e conversione
        cols_num = [
            "Calorie", "FC Media", "FC max", "TE aerobico",
            "Cadenza media", "Distanza", "Ascesa totale"
        ]

        for col in cols_num:
            if col in df.columns:
                # Sostituisci '--' o valori non numerici con NaN
                df[col] = df[col].replace(['--', '', None], pd.NA)
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce'
                )

        # Data
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')

        # TE scala 0-50 → 0-5
        if 'TE aerobico' in df.columns and df['TE aerobico'].mean(skipna=True) > 10:
            df['TE aerobico'] = df['TE aerobico'] / 10

        # Tempo in minuti
        if 'Tempo' in df.columns:
            df['Tempo_TD'] = pd.to_timedelta(df['Tempo'], errors='coerce')
            df['Tempo_Minuti'] = df['Tempo_TD'].dt.total_seconds() / 60

        # Passo "5:30" → 5.5
        if 'Passo medio' in df.columns:
            def passo_a_decimale(p):
                try:
                    parts = str(p).split(':')
                    if len(parts) == 2:
                        return int(parts[0]) + int(parts[1])/60
                    return None
                except: 
                    return None
            df['Passo_Decimale'] = df['Passo medio'].apply(passo_a_decimale)

        return df.dropna(subset=['Data', 'Passo_Decimale'])

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
# 5. GEMINI COACH AI
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
3. Suggerimenti pratici per migliorare la performance

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

    # Sidebar
    st.sidebar.header("🎯 Filtri")
    sport = st.sidebar.multiselect(
        "Tipo Sport", sorted(df['Tipo di attivita'].dropna().unique()),
        default=df['Tipo di attivita'].dropna().unique()
    )
    date_range = st.sidebar.date_input(
        "Periodo", [df['Data'].min().date(), df['Data'].max().date()]
    )

    z1 = st.sidebar.number_input("Fine Z1", 130)
    z2 = st.sidebar.number_input("Fine Z2", 145)
    z3 = st.sidebar.number_input("Fine Z3", 160)
    z4 = st.sidebar.number_input("Fine Z4", 175)

    df['Zona Cardio'] = df['FC Media'].apply(lambda x: assegna_zona(x, z1, z2, z3, z4))

    mask = (
        df['Tipo di attivita'].isin(sport) &
        (df['Data'].dt.date >= date_range[0]) &
        (df['Data'].dt.date <= date_range[1])
    )
    df_f = df.loc[mask].sort_values('Data')

    # Tabs
    tabs = st.tabs(["📉 Trend", "📊 Performance", "🔥 Zone", "🤖 Coach AI", "📋 Dati"])

    # --- Trend ---
    with tabs[0]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_f['Data'], y=df_f['Passo_Decimale'], name="Passo", yaxis="y1"
        ))
        fig.add_trace(go.Scatter(
            x=df_f['Data'], y=df_f['FC Media'], name="FC", yaxis="y2"
        ))
        fig.update_layout(
            yaxis=dict(title="Passo", autorange="reversed"),
            yaxis2=dict(title="FC", side="right", overlaying="y"),
            template="plotly_dark"
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- Performance ---
    with tabs[1]:
        fig = px.scatter(
            df_f, x='Tempo_Minuti', y='TE aerobico', color='Tipo di attivita',
            size='Calorie', trendline="ols", template="plotly_dark"
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- Zone Cardio ---
    with tabs[2]:
        fig = px.box(
            df_f, x='Zona Cardio', y='Passo_Decimale', color='Zona Cardio',
            template="plotly_dark"
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

    # --- Coach AI ---
    with tabs[3]:
        df_f['Indice_Eff'] = (1 / df_f['Passo_Decimale'].replace(0,1)) / df_f['FC Media'] * 1000
        recenti = df_f[df_f['Data'] >= df_f['Data'].max() - timedelta(days=30)]

        if not recenti.empty:
            eff = recenti['Indice_Eff'].mean()
            st.metric("Efficienza (30gg)", f"{eff:.2f}")

            if st.button("🚀 Analisi Coach AI"):
                sintesi = {
                    "efficienza_media": round(eff,2),
                    "zone": recenti['Zona Cardio'].value_counts().to_dict(),
                    "sport": recenti['Tipo di attivita'].unique().tolist()
                }
                with st.spinner("Il Coach sta analizzando..."):
                    st.write(chiedi_a_gemini(sintesi))
        else:
            st.info("Esegui allenamenti negli ultimi 30 giorni per attivare l'AI")

    # --- Tabella Dati ---
    with tabs[4]:
        st.dataframe(df_f, use_container_width=True)
