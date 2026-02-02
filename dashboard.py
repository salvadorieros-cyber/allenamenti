import streamlit as st
import subprocess
import sys

# --- PROTEZIONE IMPORTAZIONE LIBRERIA ---
try:
    from google import genai
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-genai==0.3.0"])
    from google import genai

import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta

# ==========================================
# 1. CONFIGURAZIONE & COSTANTI
# ==========================================
st.set_page_config(page_title="Fitness AI Dashboard 2026", layout="wide")
API_KEY = "AIzaSyBqTzfLFJOxtNaMs9DzVQfNFDLGWztzVVY"

# ==========================================
# 2. FUNZIONI CORE (DATI & AI)
# ==========================================

@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect('Allenamenti.db')
        # Trova automaticamente la prima tabella disponibile
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        if not tables: return pd.DataFrame()
        
        df = pd.read_sql_query(f"SELECT * FROM '{tables[0][0]}'", conn)
        conn.close()
        
        # Pulizia Date
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        
        # Pulizia Numerica (gestione virgole e punti)
        cols_num = ['Calorie', 'FC Media', 'FC max', 'TE aerobico', 'Distanza', 'Ascesa totale']
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
        
        # Normalizzazione Training Effect
        if 'TE aerobico' in df.columns and df['TE aerobico'].mean() > 10:
            df['TE aerobico'] = df['TE aerobico'] / 10

        # Calcolo Tempi
        if 'Tempo' in df.columns:
            df['Tempo_TD'] = pd.to_timedelta(df['Tempo'].astype(str), errors='coerce')
            df['Tempo_Minuti'] = df['Tempo_TD'].dt.total_seconds() / 60
            df['Tempo_Ore'] = df['Tempo_Minuti'] / 60
        
        # Conversione Passo (es. "5:30" -> 5.5)
        if 'Passo medio' in df.columns:
            def p_to_d(p):
                try:
                    parts = str(p).split(':')
                    return int(parts[0]) + int(parts[1])/60 if len(parts)==2 else None
                except: return None
            df['Passo_Decimale'] = df['Passo medio'].apply(p_to_d)
            
        return df.dropna(subset=['Data'])
    except Exception as e:
        st.error(f"Errore nel caricamento del database: {e}")
        return pd.DataFrame()

def chiedi_a_gemini(sintesi_testo):
    try:
        client = genai.Client(api_key=API_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"Sei un coach esperto. Commenta questi dati sulla variazione di efficienza e dai consigli pratici in italiano: {sintesi_testo}"
        )
        return response.text
    except Exception as e:
        return f"Il Coach è in pausa caffè (Errore: {e})"

# ==========================================
# 3. SICUREZZA & ACCESSO
# ==========================================
if "password_correct" not in st.session_state:
    st.session_state.password_correct = False

if not st.session_state.password_correct:
    st.title("🔐 Fitness Dashboard")
    pw = st.text_input("Inserisci la password per sbloccare i dati", type="password")
    if st.button("Sblocca"):
        if pw == "elgnaro":
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Accesso negato.")
else:
    # ==========================================
    # 4. DASHBOARD ATTIVA
    # ==========================================
    df = load_data()

    if df.empty:
        st.info("Carica il file 'Allenamenti.db' nel repository per iniziare.")
    else:
        # --- CALCOLO INDICI ---
        # 1. Efficienza Standard (Velocità / Battiti)
        df['IE_std'] = (1 / df['Passo_Decimale'].replace(0,1)) / df['FC Media'] * 1000
        
        # 2. Efficienza Verticale (Compensata col Dislivello)
        # Formula: (Km + (D+/100)) / (FC * Ore)
        df['IEV'] = ((df['Distanza'] + (df['Ascesa totale']/100)) / (df['FC Media'] * df['Tempo_Ore'])) * 100

        # --- SIDEBAR FILTRI ---
        st.sidebar.header("🎯 Filtra Allenamenti")
        sport_list = sorted(df['Tipo di attivita'].unique())
        sport = st.sidebar.multiselect("Tipo Sport", sport_list, default=sport_list)
        
        df_f = df[df['Tipo di attivita'].isin(sport)].copy()

        # --- INTERFACCIA TABS ---
        t1, t2, t3, t4 = st.tabs(["📊 Performance", "🏔️ Efficienza Verticale", "🤖 COACH AI", "📋 Tabella"])

        with t1:
            st.subheader("Trend Efficienza Standard (Pianura)")
            fig_std = px.scatter(df_f, x='Data', y='IE_std', color='Tipo di attivita', 
                               trendline="ols", template="plotly_dark", title="Velocità relativa allo sforzo")
            st.plotly_chart(fig_std, use_container_width=True)

        with t2:
            st.subheader("Confronto: Quanto ti penalizza la salita?")
            st.markdown("Il grafico confronta l'efficienza pura (blu) con quella corretta per il dislivello (arancio).")
            
            fig_v = go.Figure()
            fig_v.add_trace(go.Scatter(x=df_f['Data'], y=df_f['IE_std'], name="Efficienza Standard", line=dict(color='#00d4ff')))
            fig_v.add_trace(go.Scatter(x=df_f['Data'], y=df_f['IEV'], name="Efficienza Verticale (IEV)", 
                                     yaxis="y2", line=dict(color='#ff9100', width=3)))
            
            fig_v.update_layout(
                template="plotly_dark",
                yaxis=dict(title="Standard"),
                yaxis2=dict(title="Verticale (IEV)", overlaying="y", side="right"),
                legend=dict(orientation="h", y=1.1)
            )
            st.plotly_chart(fig_v, use_container_width=True)

        with t3:
            st.header("🤖 Analisi Avanzata Coach AI")
            
            # Calcolo Variazione (Delta)
            data_30 = df_f['Data'].max() - timedelta(days=30)
            recenti = df_f[df_f['Data'] >= data_30]
            storici = df_f[df_f['Data'] < data_30]
            
            if not recenti.empty and not storici.empty:
                m_recente = recenti['IEV'].mean()
                m_storica = storici['IEV'].mean()
                delta = ((m_recente - m_storica) / m_storica) * 100
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Indice IEV (30gg)", f"{m_recente:.2f}", f"{delta:.1f}% vs storico")
                col2.metric("Allenamenti", len(recenti))
                col3.metric("Km totali (30gg)", f"{recenti['Distanza'].sum():.1f}")

                if st.button("🚀 Genera Report Coach AI"):
                    sintesi = {
                        "Trend": "Miglioramento" if delta > 0 else "Calo",
                        "Variazione": f"{delta:.1f}%",
                        "IEV_Medio": round(m_recente, 2),
                        "Sport": recenti['Tipo di attivita'].unique().tolist()
                    }
                    with st.spinner("Analizzando i tuoi battiti..."):
                        risposta = chiedi_a_gemini(str(sintesi))
                        st.markdown("---")
                        st.success("### 💬 Il verdetto del Coach")
                        st.write(risposta)
            else:
                st.info("Servono almeno 30 giorni di storico per calcolare la variazione di performance.")

        with t4:
            st.subheader("Dati Integrali")
            st.dataframe(df_f.sort_values(by='Data', ascending=False), use_container_width=True)