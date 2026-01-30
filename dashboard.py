import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
import google.generativeai as genai

# Configurazione API Gemini
GOOGLE_API_KEY = "AIzaSyBqTzfLFJOxtNaMs9DzVQfNFDLGWztzVVY"
genai.configure(api_key=GOOGLE_API_KEY)

# ==========================================
# 1. LOGICA DATI
# ==========================================
@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect('Allenamenti.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        table_name = tables[0][0]
        df = pd.to_sql_query = pd.read_sql_query(f"SELECT * FROM '{table_name}'", conn)
        conn.close()
        
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        cols_num = ['Calorie', 'FC Media', 'FC max', 'TE aerobico', 'Cadenza media', 'Distanza', 'Ascesa totale']
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
        
        if 'TE aerobico' in df.columns and df['TE aerobico'].mean() > 10:
            df['TE aerobico'] = df['TE aerobico'] / 10

        if 'Tempo' in df.columns:
            df['Tempo_TD'] = pd.to_timedelta(df['Tempo'].astype(str), errors='coerce')
            df['Tempo_Minuti'] = df['Tempo_TD'].dt.total_seconds() / 60
        
        if 'Passo medio' in df.columns:
            def passo_a_decimale(p):
                try:
                    parts = str(p).split(':')
                    return int(parts[0]) + int(parts[1])/60 if len(parts) == 2 else None
                except: return None
            df['Passo_Decimale'] = df['Passo medio'].apply(passo_a_decimale)
            
        return df.dropna(subset=['Data'])
    except Exception as e:
        st.error(f"Errore caricamento: {e}")
        return pd.DataFrame()

def assegna_zona_custom(fc, z1, z2, z3, z4):
    if fc <= z1: return "Z1 (Recupero)"
    elif fc <= z2: return "Z2 (Fondo)"
    elif fc <= z3: return "Z3 (Tempo)"
    elif fc <= z4: return "Z4 (Soglia)"
    else: return "Z5 (Massimale)"

# ==========================================
# 2. FUNZIONE ANALISI AI
# ==========================================
def chiedi_a_gemini(sintesi_dati):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Sei un esperto coach sportivo. Analizza i seguenti dati di allenamento di un atleta e fornisci:
        1. Un commento sullo stato di forma attuale.
        2. Un consiglio tecnico specifico per migliorare l'efficienza.
        3. Eventuali segnali di allarme (overtraining o stallo).
        
        Dati dell'atleta (ultimi 30 giorni vs storico):
        {sintesi_dati}
        
        Sii conciso, professionale e motivante. Rispondi in italiano.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"L'AI sta riposando... (Errore: {e})"

# ==========================================
# 3. DASHBOARD
# ==========================================
if "password_correct" not in st.session_state:
    st.session_state.password_correct = False

if not st.session_state.password_correct:
    st.title("🔐 Accesso Riservato")
    pw = st.text_input("Password", type="password")
    if st.button("Sblocca"):
        if pw == "elgnaro":
            st.session_state.password_correct = True
            st.rerun()
else:
    st.set_page_config(page_title="Fitness AI Dashboard", layout="wide")
    df = load_data()

    if not df.empty:
        # SIDEBAR
        st.sidebar.header("🎯 Filtri")
        sport = st.sidebar.multiselect("Sport", sorted(df['Tipo di attivita'].unique()), default=df['Tipo di attivita'].unique())
        date_range = st.sidebar.date_input("Periodo", [df['Data'].min().date(), df['Data'].max().date()])
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚙️ Zone BPM")
        z1 = st.sidebar.number_input("Fine Z1", value=130)
        z2 = st.sidebar.number_input("Fine Z2", value=145)
        z3 = st.sidebar.number_input("Fine Z3", value=160)
        z4 = st.sidebar.number_input("Fine Z4", value=175)
        
        # ELABORAZIONE
        df['Zona Cardio'] = df['FC Media'].apply(lambda x: assegna_zona_custom(x, z1, z2, z3, z4))
        mask = (df['Tipo di attivita'].isin(sport)) & (df['Data'].dt.date >= date_range[0]) & (df['Data'].dt.date <= (date_range[1] if len(date_range)>1 else date_range[0]))
        df_f = df.loc[mask].sort_values(by='Data')

        st.title("🏃 Analisi Performance con AI")
        
        tabs = st.tabs(["🚀 Trend", "📊 Analisi TE", "❤️ Cuore", "🔥 Zone", "🤖 COACH AI PROGRESSI", "📋 Dati"])
        
        with tabs[0]:
            df_p = df_f.dropna(subset=['Passo_Decimale', 'FC Media'])
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_p['Data'], y=df_p['Passo_Decimale'], name="Passo", yaxis="y1", line=dict(color='#00CC96')))
            fig.add_trace(go.Scatter(x=df_p['Data'], y=df_p['FC Media'], name="FC Media", yaxis="y2", line=dict(color='#EF553B', dash='dot')))
            fig.update_layout(template="plotly_dark", yaxis=dict(title="Passo", autorange="reversed"), yaxis2=dict(title="FC", side="right", overlaying="y", showgrid=False))
            st.plotly_chart(fig, use_container_width=True)

        with tabs[3]:
            fig_z = px.box(df_f, x='Zona Cardio', y='Passo_Decimale', color='Zona Cardio', template="plotly_dark")
            fig_z.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_z, use_container_width=True)

        # --- TAB 4: IL CUORE DELL'INTEGRAZIONE AI ---
        with tabs[4]:
            st.header("🤖 Analisi Intelligente Gemini AI")
            
            df_f['Indice_Eff'] = (1 / df_f['Passo_Decimale']) / df_f['FC Media'] * 1000
            data_taglio = df_f['Data'].max() - timedelta(days=30)
            recenti = df_f[df_f['Data'] >= data_taglio]
            storici = df_f[df_f['Data'] < data_taglio]
            
            if not recenti.empty and not storici.empty:
                eff_r, eff_s = recenti['Indice_Eff'].mean(), storici['Indice_Eff'].mean()
                delta = ((eff_r - eff_s) / eff_s) * 100
                
                # Prepariamo la sintesi per l'AI
                sintesi = f"""
                - Sport analizzati: {sport}
                - Numero attività recenti: {len(recenti)}
                - Efficienza Aerobica attuale: {eff_r:.2f} (Variazione: {delta:.1f}%)
                - Tempo totale recente: {int(recenti['Tempo_Minuti'].sum())} minuti
                - Distribuzione Zone: {recenti['Zona Cardio'].value_counts(normalize=True).to_dict()}
                - FC Media recente: {recenti['FC Media'].mean():.0f} bpm
                """
                
                if st.button("Genera Analisi Coach AI"):
                    with st.spinner("Gemini sta analizzando i tuoi progressi..."):
                        risposta = chiedi_a_gemini(sintesi)
                        st.markdown("---")
                        st.subheader("📋 Il responso del Coach")
                        st.write(risposta)
                
                st.markdown("---")
                st.metric("Indice Efficienza (Salire = Migliorare)", f"{eff_r:.2f}", f"{delta:.1f}%")
                fig_eff = px.scatter(df_f, x='Data', y='Indice_Eff', trendline="ols", template="plotly_dark")
                st.plotly_chart(fig_eff, use_container_width=True)
            else:
                st.info("Carica almeno 30 giorni di dati per attivare l'analisi AI.")

        with tabs[5]:
            st.dataframe(df_f.drop(columns=['Tempo_TD', 'Passo_Decimale', 'Indice_Eff']), use_container_width=True)