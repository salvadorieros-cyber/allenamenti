import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
from google import genai  # Import per la nuova libreria 0.3.0

# ==========================================
# 1. CONFIGURAZIONE PAGINA (Deve essere il primo comando)
# ==========================================
st.set_page_config(page_title="Fitness AI Dashboard", layout="wide")

# Costanti
API_KEY = "AIzaSyBqTzfLFJOxtNaMs9DzVQfNFDLGWztzVVY"

# ==========================================
# 2. LOGICA DATI & UTILITY
# ==========================================

@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect('Allenamenti.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        if not tables:
            return pd.DataFrame()
            
        table_name = tables[0][0]
        df = pd.read_sql_query(f"SELECT * FROM '{table_name}'", conn)
        conn.close()
        
        # Pulizia Date
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        
        # Conversione Numerica (gestione virgole e punti)
        cols_num = ['Calorie', 'FC Media', 'FC max', 'TE aerobico', 'Cadenza media', 'Distanza', 'Ascesa totale']
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
        
        # Correzione Training Effect (se in scala 0-50 invece di 0-5)
        if 'TE aerobico' in df.columns and df['TE aerobico'].mean() > 10:
            df['TE aerobico'] = df['TE aerobico'] / 10

        # Calcolo Minuti
        if 'Tempo' in df.columns:
            df['Tempo_TD'] = pd.to_timedelta(df['Tempo'].astype(str), errors='coerce')
            df['Tempo_Minuti'] = df['Tempo_TD'].dt.total_seconds() / 60
        
        # Conversione Passo (da "5:30" a 5.5)
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
        # Nuova inizializzazione client (versione 0.3.0)
        client = genai.Client(api_key=API_KEY)
        prompt = f"""
        Sei un coach sportivo esperto. Analizza questi dati di un atleta:
        {sintesi_dati}
        
        Fornisci in italiano un'analisi tecnica su:
        1. Stato di forma e trend di efficienza.
        2. Bilanciamento delle zone cardio.
        3. Consigli pratici per i prossimi allenamenti.
        Sii sintetico ma professionale.
        """
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"Il Coach AI è momentaneamente offline: {e}"

# ==========================================
# 3. AUTENTICAZIONE
# ==========================================
if "password_correct" not in st.session_state:
    st.session_state.password_correct = False

if not st.session_state.password_correct:
    st.title("🔐 Accesso Riservato")
    pw = st.text_input("Inserisci Password", type="password")
    if st.button("Sblocca Dashboard"):
        if pw == "elgnaro":
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("Password errata")
else:
    # ==========================================
    # 4. DASHBOARD PRINCIPALE
    # ==========================================
    df = load_data()

    if df.empty:
        st.warning("Database non trovato o vuoto. Carica il file Allenamenti.db nella cartella.")
    else:
        # --- SIDEBAR: FILTRI ---
        st.sidebar.header("🎯 Filtri Attività")
        
        # Sport e Date
        sport = st.sidebar.multiselect("Tipo Sport", sorted(df['Tipo di attivita'].unique()), default=df['Tipo di attivita'].unique())
        date_range = st.sidebar.date_input("Periodo Temporale", [df['Data'].min().date(), df['Data'].max().date()])
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚙️ Soglie Cardio (BPM)")
        z1 = st.sidebar.number_input("Fine Z1 (Recupero)", value=130)
        z2 = st.sidebar.number_input("Fine Z2 (Lento)", value=145)
        z3 = st.sidebar.number_input("Fine Z3 (Medio)", value=160)
        z4 = st.sidebar.number_input("Fine Z4 (Soglia)", value=175)
        
        zone_labels = ["Z1 (Recupero)", "Z2 (Fondo)", "Z3 (Tempo)", "Z4 (Soglia)", "Z5 (Massimale)"]
        scelta_zone = st.sidebar.multiselect("Filtra per Zone", zone_labels, default=zone_labels)

        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 Filtri Performance")
        
        # Funzione veloce per creare slider
        def q_slider(label, col, key):
            val_min = float(df[col].min())
            val_max = float(df[col].max())
            if val_min == val_max: val_max += 1.0
            return st.sidebar.slider(label, val_min, val_max, (val_min, val_max), key=key)

        f_cal = q_slider("🔥 Calorie", 'Calorie', "s_cal")
        f_disl = q_slider("⛰️ Dislivello (m)", 'Ascesa totale', "s_disl")
        f_te = q_slider("📈 TE Aerobico", 'TE aerobico', "s_te")

        # --- APPLICAZIONE FILTRI ---
        df['Zona Cardio'] = df['FC Media'].apply(lambda x: assegna_zona_custom(x, z1, z2, z3, z4))
        
        # Logica della maschera
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

        # --- INTERFACCIA A TAB ---
        tabs = st.tabs(["🚀 Trend", "📈 Performance", "🔥 Zone Cardio", "🤖 COACH AI", "📋 Lista Dati"])
        
        with tabs[0]:
            st.subheader("Relazione Passo vs Frequenza Cardiaca")
            df_p = df_f.dropna(subset=['Passo_Decimale', 'FC Media'])
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_p['Data'], y=df_p['Passo_Decimale'], name="Passo (min/km)", yaxis="y1", line=dict(color='#00CC96')))
            fig.add_trace(go.Scatter(x=df_p['Data'], y=df_p['FC Media'], name="BPM Medi", yaxis="y2", line=dict(color='#EF553B', dash='dot')))
            fig.update_layout(
                template="plotly_dark",
                yaxis=dict(title="Passo", autorange="reversed"),
                yaxis2=dict(title="Battiti", side="right", overlaying="y", showgrid=False),
                legend=dict(orientation="h", y=1.1)
            )
            st.plotly_chart(fig, width='stretch')

        with tabs[1]:
            st.subheader("Training Effect vs Durata Allenamento")
            fig_te = px.scatter(df_f, x='Tempo_Minuti', y='TE aerobico', color='Tipo di attivita', 
                               size='Calorie', trendline="ols", template="plotly_dark")
            st.plotly_chart(fig_te, width='stretch')

        with tabs[2]:
            st.subheader("Distribuzione Passo per Zona Cardio")
            fig_z = px.box(df_f, x='Zona Cardio', y='Passo_Decimale', color='Zona Cardio', 
                          category_orders={"Zona Cardio": zone_labels}, template="plotly_dark")
            fig_z.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_z, width='stretch')

        with tabs[3]:
            st.header("🤖 Analisi Avanzata Coach AI")
            
            # Calcolo Indice Efficienza (Velocità / FC)
            df_f['Indice_Eff'] = (1 / df_f['Passo_Decimale'].replace(0, 1)) / df_f['FC Media'] * 1000
            
            # Confronto ultimi 30 giorni
            data_taglio = df_f['Data'].max() - timedelta(days=30)
            recenti = df_f[df_f['Data'] >= data_taglio]
            storici = df_f[df_f['Data'] < data_taglio]
            
            if not recenti.empty:
                eff_r = recenti['Indice_Eff'].mean()
                delta = ((eff_r - storici['Indice_Eff'].mean()) / storici['Indice_Eff'].mean() * 100) if not storici.empty else 0
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Efficienza Recente", f"{eff_r:.2f}", f"{delta:.1f}% vs storico")
                col2.metric("Allenamenti (30gg)", len(recenti))
                col3.metric("FC Media Periodo", f"{int(recenti['FC Media'].mean())} bpm")

                if st.button("🚀 Genera Analisi con Gemini AI"):
                    sintesi = {
                        "efficienza": round(eff_r, 2),
                        "variazione": f"{delta:.1f}%",
                        "zone_cardio": recenti['Zona Cardio'].value_counts().to_dict(),
                        "sport": recenti['Tipo di attivita'].unique().tolist()
                    }
                    with st.spinner("Il Coach sta analizzando i tuoi sforzi..."):
                        analisi = chiedi_a_gemini(str(sintesi))
                        st.markdown("---")
                        st.success("### 💬 Resoconto del Coach")
                        st.write(analisi)
                
                st.plotly_chart(px.scatter(df_f, x='Data', y='Indice_Eff', trendline="ols", 
                                          title="Andamento Efficienza Aerobica", template="plotly_dark"), width='stretch')
            else:
                st.info("Esegui degli allenamenti negli ultimi 30 giorni per attivare l'analisi AI.")

        with tabs[4]:
            st.subheader("Tabella Dati Filtrati")
            st.dataframe(df_f, width='stretch')