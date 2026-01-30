import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
import google.generativeai as genai

# ==========================================
# 1. CONFIGURAZIONE & LOGICA DATI
# ==========================================
GOOGLE_API_KEY = "AIzaSyBqTzfLFJOxtNaMs9DzVQfNFDLGWztzVVY"
genai.configure(api_key=GOOGLE_API_KEY)

@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect('Allenamenti.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        table_name = tables[0][0]
        df = pd.read_sql_query(f"SELECT * FROM '{table_name}'", conn)
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

def chiedi_a_gemini(sintesi_dati):
    try:
        # Usiamo il nome del modello specifico per la versione Free stabile
        model = genai.GenerativeModel(model_name='gemini-1.5-flash-latest')
        
        prompt = f"""
        Sei un esperto coach sportivo e analista dati. 
        Analizza questi parametri di allenamento dell'atleta:
        {sintesi_dati}
        
        Fornisci:
        1. Stato di forma (Miglioramento/Stallo/Affaticamento).
        2. Un consiglio tecnico pratico basato sulla distribuzione delle zone cardio.
        3. Un commento sull'efficienza aerobica.
        
        Rispondi in italiano, sii breve ma molto tecnico.
        """
        # Configurazione per evitare blocchi di sicurezza standard su dati tecnici
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        # Se fallisce ancora, proviamo il fallback sul modello base pro
        try:
            model_fallback = genai.GenerativeModel('gemini-1.5-pro')
            return model_fallback.generate_content(prompt).text
        except:
            return f"Errore di connessione API: {e}. Verifica che la chiave sia attiva su AI Studio."

# ==========================================
# 2. ACCESSO
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
    # --- DASHBOARD ATTIVA ---
    st.set_page_config(page_title="Fitness AI Dashboard", layout="wide")
    df = load_data()

    if not df.empty:
        # --- SIDEBAR (RIPRISTINATA) ---
        st.sidebar.header("🎯 Filtri Attività")
        sport = st.sidebar.multiselect("Sport", sorted(df['Tipo di attivita'].unique()), default=df['Tipo di attivita'].unique())
        date_range = st.sidebar.date_input("Periodo", [df['Data'].min().date(), df['Data'].max().date()])
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚙️ Soglie Cardio (BPM)")
        z1 = st.sidebar.number_input("Fine Z1", value=130)
        z2 = st.sidebar.number_input("Fine Z2", value=145)
        z3 = st.sidebar.number_input("Fine Z3", value=160)
        z4 = st.sidebar.number_input("Fine Z4", value=175)
        
        zone_labels = ["Z1 (Recupero)", "Z2 (Fondo)", "Z3 (Tempo)", "Z4 (Soglia)", "Z5 (Massimale)"]
        scelta_zone = st.sidebar.multiselect("Mostra Zone", zone_labels, default=zone_labels)

        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 Filtri Performance")
        def q_slider(label, col, key):
            m1, m2 = float(df[col].min()), float(df[col].max())
            if m1 == m2: m2 = m1 + 1.0
            return st.sidebar.slider(label, m1, m2, (m1, m2), key=key)

        f_cal = q_slider("🔥 Calorie", 'Calorie', "f_cal")
        f_disl = q_slider("⛰️ Dislivello (m)", 'Ascesa totale', "f_disl")
        f_te = q_slider("📈 TE Aerobico", 'TE aerobico', "f_te")

        # --- ELABORAZIONE DATI ---
        df['Zona Cardio'] = df['FC Media'].apply(lambda x: assegna_zona_custom(x, z1, z2, z3, z4))
        
        mask = (
            (df['Tipo di attivita'].isin(sport)) &
            (df['Zona Cardio'].isin(scelta_zone)) &
            (df['Data'].dt.date >= date_range[0]) &
            (df['Data'].dt.date <= (date_range[1] if len(date_range)>1 else date_range[0])) &
            (df['Calorie'].between(f_cal[0], f_cal[1])) &
            (df['Ascesa totale'].between(f_disl[0], f_disl[1])) &
            (df['TE aerobico'].between(f_te[0], f_te[1]))
        )
        df_f = df.loc[mask].sort_values(by='Data')

        # --- TABS ---
        tabs = st.tabs(["🚀 Trend Passo & FC", "📊 Analisi TE", "❤️ Cuore", "🔥 Zone", "🤖 COACH AI", "📋 Dati"])
        
        with tabs[0]:
            st.subheader("Relazione tra Velocità e Sforzo")
            df_p = df_f.dropna(subset=['Passo_Decimale', 'FC Media'])
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_p['Data'], y=df_p['Passo_Decimale'], name="Passo", yaxis="y1", line=dict(color='#00CC96')))
            fig.add_trace(go.Scatter(x=df_p['Data'], y=df_p['FC Media'], name="FC Media", yaxis="y2", line=dict(color='#EF553B', dash='dot')))
            fig.update_layout(template="plotly_dark", yaxis=dict(title="Passo", autorange="reversed"), yaxis2=dict(title="FC", side="right", overlaying="y", showgrid=False))
            st.plotly_chart(fig, use_container_width=True)

        with tabs[1]:
            st.plotly_chart(px.scatter(df_f, x='Tempo_Minuti', y='TE aerobico', color='Tipo di attivita', size='Calorie', trendline="ols", template="plotly_dark"), use_container_width=True)

        with tabs[3]:
            fig_z = px.box(df_f, x='Zona Cardio', y='Passo_Decimale', color='Zona Cardio', category_orders={"Zona Cardio": zone_labels}, template="plotly_dark")
            fig_z.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_z, use_container_width=True)

        with tabs[4]:
            st.header("🤖 Analisi Coach Gemini AI")
            df_f['Indice_Eff'] = (1 / df_f['Passo_Decimale'].replace(0, 1)) / df_f['FC Media'] * 1000
            
            data_taglio = df_f['Data'].max() - timedelta(days=30)
            recenti = df_f[df_f['Data'] >= data_taglio]
            storici = df_f[df_f['Data'] < data_taglio]
            
            if not recenti.empty:
                eff_r = recenti['Indice_Eff'].mean()
                delta = ((eff_r - storici['Indice_Eff'].mean()) / storici['Indice_Eff'].mean() * 100) if not storici.empty else 0
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Efficienza", f"{eff_r:.2f}", f"{delta:.1f}%")
                c2.metric("Attività (30gg)", len(recenti))
                c3.metric("FC Media", f"{int(recenti['FC Media'].mean())}")

                if st.button("🚀 Chiedi parere al Coach AI"):
                    sintesi = f"Efficienza: {eff_r:.2f}, Delta: {delta:.1f}%, Zone: {recenti['Zona Cardio'].value_counts().to_dict()}"
                    with st.spinner("Analisi in corso..."):
                        st.info(chiedi_a_gemini(sintesi))
                
                st.plotly_chart(px.scatter(df_f, x='Data', y='Indice_Eff', trendline="ols", template="plotly_dark"), use_container_width=True)
            else:
                st.info("Dati insufficienti per il report AI.")

        with tabs[5]:
            st.dataframe(df_f.drop(columns=['Indice_Eff']) if 'Indice_Eff' in df_f.columns else df_f, use_container_width=True)