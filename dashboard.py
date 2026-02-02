import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
from google import genai  # SDK google-genai 0.3.0

# ==========================================
# 1. CONFIGURAZIONE PAGINA
# ==========================================
st.set_page_config(page_title="Fitness AI Dashboard", layout="wide")

# Costanti
API_KEY = "AIzaSyBqTzfLFJOxtNaMs9DzVQfNFDLGWztzVVY"

# ==========================================
# 2. FUNZIONI DI ELABORAZIONE DATI
# ==========================================

@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect('Allenamenti.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        if not tables:
            st.error("Nessuna tabella trovata nel database.")
            return pd.DataFrame()
            
        table_name = tables[0][0]
        df = pd.read_sql_query(f"SELECT * FROM '{table_name}'", conn)
        conn.close()
        
        # Conversione Date
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        
        # Conversione Numerica (punti/virgole)
        cols_num = ['Calorie', 'FC Media', 'FC max', 'TE aerobico', 'Cadenza media', 'Distanza', 'Ascesa totale']
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
        
        # Normalizzazione Training Effect
        if 'TE aerobico' in df.columns and df['TE aerobico'].mean() > 10:
            df['TE aerobico'] = df['TE aerobico'] / 10

        # Gestione Tempi e Passo
        if 'Tempo' in df.columns:
            df['Tempo_TD'] = pd.to_timedelta(df['Tempo'].astype(str), errors='coerce')
            df['Tempo_Minuti'] = df['Tempo_TD'].dt.total_seconds() / 60
            df['Tempo_Ore'] = df['Tempo_Minuti'] / 60
        
        if 'Passo medio' in df.columns:
            def passo_a_decimale(p):
                try:
                    parts = str(p).split(':')
                    if len(parts) == 2:
                        return int(parts[0]) + int(parts[1])/60
                    return None
                except: return None
            df['Passo_Decimale'] = df['Passo medio'].apply(passo_a_decimale)
            
        return df.dropna(subset=['Data'])
    except Exception as e:
        st.error(f"Errore caricamento database: {e}")
        return pd.DataFrame()

def assegna_zona_custom(fc, z1, z2, z3, z4):
    if fc <= z1: return "Z1 (Recupero)"
    elif fc <= z2: return "Z2 (Fondo)"
    elif fc <= z3: return "Z3 (Tempo)"
    elif fc <= z4: return "Z4 (Soglia)"
    else: return "Z5 (Massimale)"

def chiedi_a_gemini(sintesi_dati):
    try:
        # Inizializzazione Client con modello aggiornato al 2026
        client = genai.Client(api_key=API_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"Sei un coach sportivo. Analizza questi dati e rispondi in italiano: {sintesi_dati}"
        )
        return response.text
    except Exception as e:
        return f"Coach AI non disponibile (Errore: {e})"

# ==========================================
# 3. AUTENTICAZIONE
# ==========================================
if "password_correct" not in st.session_state:
    st.session_state.password_correct = False

if not st.session_state.password_correct:
    st.title("🔐 Accesso Riservato")
    pw = st.text_input("Inserisci Password", type="password")
    if st.button("Sblocca"):
        if pw == "elgnaro":
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Password errata")
else:
    # ==========================================
    # 4. DASHBOARD ATTIVA
    # ==========================================
    df = load_data()

    if df.empty:
        st.warning("In attesa di dati dal database...")
    else:
        # --- SIDEBAR ---
        st.sidebar.header("🎯 Filtri Sessioni")
        sport = st.sidebar.multiselect("Sport", sorted(df['Tipo di attivita'].unique()), default=df['Tipo di attivita'].unique())
        date_range = st.sidebar.date_input("Periodo", [df['Data'].min().date(), df['Data'].max().date()])
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚙️ Zone Cardio (BPM)")
        z1 = st.sidebar.number_input("Z1 fine", value=130)
        z2 = st.sidebar.number_input("Z2 fine", value=145)
        z3 = st.sidebar.number_input("Z3 fine", value=160)
        z4 = st.sidebar.number_input("Z4 fine", value=175)
        
        zone_labels = ["Z1 (Recupero)", "Z2 (Fondo)", "Z3 (Tempo)", "Z4 (Soglia)", "Z5 (Massimale)"]
        scelta_zone = st.sidebar.multiselect("Mostra Zone", zone_labels, default=zone_labels)

        # Filtri range performance
        def q_slider(label, col, key):
            m1, m2 = float(df[col].min()), float(df[col].max())
            if m1 == m2: m2 += 1.0
            return st.sidebar.slider(label, m1, m2, (m1, m2), key=key)

        f_cal = q_slider("🔥 Calorie", 'Calorie', "s1")
        f_disl = q_slider("⛰️ Dislivello", 'Ascesa totale', "s2")
        f_te = q_slider("📈 TE Aerobico", 'TE aerobico', "s3")

        # Applicazione Filtri
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

        # --- CALCOLO INDICI ---
        # 1. Efficienza Standard: (1/Passo) / FC * 1000
        df_f['IE_std'] = (1 / df_f['Passo_Decimale'].replace(0, 1)) / df_f['FC Media'] * 1000
        
        # 2. Efficienza Verticale (IEV): (Km + (Dislivello/100)) / (FC * Ore) * 100
        df_f['IEV'] = ((df_f['Distanza'] + (df_f['Ascesa totale'] / 100)) / 
                      (df_f['FC Media'] * df_f['Tempo_Ore'])) * 100

        # --- TABS ---
        tabs = st.tabs(["🚀 Trend Passo/FC", "📈 Performance TE", "🏔️ Efficienza Comparata", "🔥 Zone Cardio", "🤖 COACH AI", "📋 Dati"])

        with tabs[0]:
            st.subheader("Andamento Velocità vs Sforzo")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_f['Data'], y=df_f['Passo_Decimale'], name="Passo (min/km)", yaxis="y1", line=dict(color='#00CC96')))
            fig.add_trace(go.Scatter(x=df_f['Data'], y=df_f['FC Media'], name="BPM Medi", yaxis="y2", line=dict(color='#EF553B', dash='dot')))
            fig.update_layout(template="plotly_dark", yaxis=dict(title="Passo", autorange="reversed"), yaxis2=dict(title="FC", side="right", overlaying="y", showgrid=False))
            st.plotly_chart(fig, width='stretch')

        with tabs[1]:
            st.subheader("Training Effect e Intensità")
            fig_te = px.scatter(df_f, x='Tempo_Minuti', y='TE aerobico', color='Tipo di attivita', size='Calorie', trendline="ols", template="plotly_dark")
            st.plotly_chart(fig_te, width='stretch')

        with tabs[2]:
            st.header("🏔️ Efficienza: Piano vs Salita")
            st.markdown("""
            Confronto tra l'**Efficienza Standard** (basata sulla velocità pura) e l'**Efficienza Verticale** (che premia il dislivello: 100m D+ = 1km extra).
            """)
            
            fig_comp = go.Figure()
            # Indice Velocità
            fig_comp.add_trace(go.Scatter(x=df_f['Data'], y=df_f['IE_std'], name="Efficienza Velocità (Standard)", line=dict(color='#636EFA')))
            # Indice Verticale
            fig_comp.add_trace(go.Scatter(x=df_f['Data'], y=df_f['IEV'], name="Efficienza Verticale (IEV)", line=dict(color='#EF553B', width=3), yaxis="y2"))
            
            fig_comp.update_layout(
                template="plotly_dark",
                yaxis=dict(title="Indice Standard", titlefont=dict(color="#636EFA")),
                yaxis2=dict(title="Indice Verticale (IEV)", titlefont=dict(color="#EF553B"), overlaying="y", side="right"),
                legend=dict(orientation="h", y=1.1)
            )
            st.plotly_chart(fig_comp, width='stretch')
            
            # Top prestazioni
            st.subheader("🏆 Le tue migliori scalate (Top IEV)")
            st.table(df_f.nlargest(5, 'IEV')[['Data', 'Distanza', 'Ascesa totale', 'FC Media', 'IEV']])

        with tabs[3]:
            st.subheader("Distribuzione Passo per Zona Cardio")
            fig_z = px.box(df_f, x='Zona Cardio', y='Passo_Decimale', color='Zona Cardio', category_orders={"Zona Cardio": zone_labels}, template="plotly_dark")
            fig_z.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_z, width='stretch')

        with tabs[4]:
            st.header("🤖 Coach Gemini AI")
            data_t = df_f['Data'].max() - timedelta(days=30)
            rec = df_f[df_f['Data'] >= data_t]
            
            if not rec.empty:
                c1, c2, c3 = st.columns(3)
                c1.metric("IEV Medio (30gg)", f"{rec['IEV'].mean():.2f}")
                c2.metric("Allenamenti", len(rec))
                c3.metric("Dislivello Totale", f"{int(rec['Ascesa totale'].sum())} m")

                if st.button("🚀 Chiedi parere al Coach"):
                    sintesi = f"IEV: {rec['IEV'].mean():.2f}, Zone: {rec['Zona Cardio'].value_counts().to_dict()}"
                    with st.spinner("Analisi in corso..."):
                        st.info(chiedi_a_gemini(sintesi))
                
                st.plotly_chart(px.scatter(df_f, x='Data', y='IEV', trendline="ols", template="plotly_dark"), width='stretch')
            else:
                st.info("Esegui attività recenti per l'analisi AI.")

        with tabs[5]:
            st.dataframe(df_f, width='stretch')