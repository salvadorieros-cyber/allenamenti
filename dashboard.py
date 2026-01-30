import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

# --- 1. PROTEZIONE ACCESSO ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if not st.session_state.password_correct:
        st.title("🔐 Accesso Riservato")
        pw = st.text_input("Inserisci la password", type="password")
        if st.button("Accedi"):
            if pw == "elgnaro": 
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("Password errata")
        st.stop()

check_password()

# --- 2. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Dashboard Fitness Pro", layout="wide")

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
        
        # Conversione Data
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        
        # Conversione Numerica
        cols_num = ['Calorie', 'FC Media', 'FC max', 'TE aerobico', 'Cadenza media', 'Distanza', 'Ascesa totale']
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
        
        # Correzione automatica TE aerobico (es. 42 -> 4.2)
        if 'TE aerobico' in df.columns and df['TE aerobico'].mean() > 10:
            df['TE aerobico'] = df['TE aerobico'] / 10

        # Calcolo Tempo in minuti
        if 'Tempo' in df.columns:
            df['Tempo_TD'] = pd.to_timedelta(df['Tempo'].astype(str), errors='coerce')
            df['Tempo_Minuti'] = df['Tempo_TD'].dt.total_seconds() / 60
        
        # Calcolo Passo Decimale
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

df = load_data()

if not df.empty:
    # --- 3. SIDEBAR: FILTRI E ZONE CARDIO ---
    st.sidebar.header("🎯 Filtri Globali")
    sport_list = sorted(df['Tipo di attivita'].unique().tolist())
    scelta_sport = st.sidebar.multiselect("Sport", sport_list, default=sport_list)
    date_range = st.sidebar.date_input("Periodo", [df['Data'].min().date(), df['Data'].max().date()])

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Impostazioni Zone Cardio")
    metodo_fc = st.sidebar.radio("Metodo FC Max", ["Inserimento Manuale", "Calcolo per Età"])
    
    if metodo_fc == "Calcolo per Età":
        eta = st.sidebar.number_input("Tua Età", min_value=5, max_value=100, value=35)
        fc_max_ref = 220 - eta
    else:
        fc_max_ref = st.sidebar.number_input("Inserisci FC Max reale", value=185)

    # Funzione calcolo zone
    def get_zona(fc):
        perc = (fc / fc_max_ref) * 100
        if perc < 60: return "Z1 (Recupero)"
        elif 60 <= perc < 70: return "Z2 (Fondo)"
        elif 70 <= perc < 80: return "Z3 (Tempo)"
        elif 80 <= perc < 90: return "Z4 (Soglia)"
        else: return "Z5 (Massimale)"

    df['Zona Cardio'] = df['FC Media'].apply(get_zona)
    
    zone_list = ["Z1 (Recupero)", "Z2 (Fondo)", "Z3 (Tempo)", "Z4 (Soglia)", "Z5 (Massimale)"]
    scelta_zone = st.sidebar.multiselect("Filtra Zone Cardio", zone_list, default=zone_list)

    # Altri filtri
    def q_slider(label, col):
        m1, m2 = float(df[col].min()), float(df[col].max())
        if m1 == m2: m2 = m1 + 1.0
        return st.sidebar.slider(label, m1, m2, (m1, m2))

    f_cal = q_slider("🔥 Calorie", 'Calorie')
    f_te = q_slider("📈 TE Aerobico", 'TE aerobico')

    # Applicazione maschera
    mask = (
        (df['Tipo di attivita'].isin(scelta_sport)) &
        (df['Zona Cardio'].isin(scelta_zone)) &
        (df['Data'].dt.date >= date_range[0]) & 
        (df['Data'].dt.date <= (date_range[1] if len(date_range)>1 else date_range[0])) &
        (df['Calorie'].between(f_cal[0], f_cal[1])) &
        (df['TE aerobico'].between(f_te[0], f_te[1]))
    )
    df_f = df.loc[mask].sort_values(by='Data', ascending=False)

    # --- 4. VISUALIZZAZIONE ---
    st.title("🏃 Dashboard Fitness Avanzata")
    
    if not df_f.empty:
        # Metriche
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Attività", len(df_f))
        c2.metric("Dislivello Tot", f"{int(df_f['Ascesa totale'].sum())} m")
        c3.metric("Kcal Totali", f"{int(df_f['Calorie'].sum())}")
        c4.metric("Tempo Totale", f"{df_f['Tempo_Minuti'].sum()/60:.1f} h")

        st.markdown("---")
        t1, t2, t3, t4, t5 = st.tabs(["🚀 Passo & Trend", "📊 Analisi TE", "❤️ Cuore", "🔥 Zone Cardio", "📋 Dati"])

        with t1:
            fig_p = px.line(df_f.sort_values('Data'), x='Data', y='Passo_Decimale', color='Tipo di attivita',
                            markers=True, template="plotly_dark", title="Andamento Passo Medio")
            fig_p.update_yaxes(autorange="reversed", title="Passo (min/km)")
            st.plotly_chart(fig_p, use_container_width=True)

        with t2:
            fig_te = px.scatter(df_f, x='Tempo_Minuti', y='TE aerobico', color='Tipo di attivita',
                                size='Calorie', trendline="ols", template="plotly_dark",
                                title="Training Effect vs Durata")
            st.plotly_chart(fig_te, use_container_width=True)

        with t3:
            fig_fc = px.line(df_f.sort_values('Data'), x='Data', y=['FC Media', 'FC max'], 
                             markers=True, template="plotly_dark", title="Carico Cardiaco")
            st.plotly_chart(fig_fc, use_container_width=True)

        with t4:
            st.subheader("Rapporto tra Intensità (Zona) e Velocità (Passo)")
            fig_zone = px.box(df_f, x='Zona Cardio', y='Passo_Decimale', color='Zona Cardio',
                              category_orders={"Zona Cardio": zone_list},
                              points="all", template="plotly_dark")
            fig_zone.update_yaxes(autorange="reversed", title="Passo (min/km)")
            st.plotly_chart(fig_zone, use_container_width=True)
            
            st.subheader("Distribuzione Sforzo")
            fig_pie = px.pie(df_f, names='Zona Cardio', hole=0.4, template="plotly_dark")
            st.plotly_chart(fig_pie, use_container_width=True)

        with t5:
            st.subheader("Dettaglio Sessioni")
            cols = ['Data', 'Tipo di attivita', 'Zona Cardio', 'Titolo', 'Ascesa totale', 'Tempo', 'Distanza', 'Calorie', 'FC Media', 'TE aerobico', 'Passo medio']
            st.dataframe(df_f[cols], use_container_width=True, hide_index=True)
    else:
        st.warning("Nessun dato trovato con i filtri attuali.")