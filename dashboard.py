import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

# --- PROTEZIONE ACCESSO ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if not st.session_state.password_correct:
        st.title("🔐 Accesso Riservato")
        pw = st.text_input("Inserisci la password", type="password")
        if st.button("Accedi"):
            if pw == "elgnaro": # <--- CAMBIA QUESTA
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("Password errata")
        st.stop()

check_password()

st.set_page_config(page_title="Dashboard Fitness Completa", layout="wide")

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

        cols_num = ['Calorie', 'FC Media', 'FC max', 'TE aerobico', 'Cadenza media', 'Distanza', 'Ascesa totale']
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
        
        return df.dropna(subset=['Data'])
    except Exception as e:
        st.error(f"Errore caricamento: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # --- SIDEBAR: TUTTI I FILTRI RIPRISTINATI ---
    st.sidebar.header("🎯 Filtri Globali")
    sport_list = sorted(df['Tipo di attivita'].unique().tolist())
    scelta_sport = st.sidebar.multiselect("Sport", sport_list, default=sport_list)
    date_range = st.sidebar.date_input("Periodo", [df['Data'].min(), df['Data'].max()])

    st.sidebar.subheader("Parametri Performance")
    def q_slider(label, col):
        m1, m2 = float(df[col].min()), float(df[col].max())
        if m1 == m2: m2 = m1 + 1.0
        return st.sidebar.slider(label, m1, m2, (m1, m2))

    f_cal = q_slider("🔥 Calorie", 'Calorie')
    f_disl = q_slider("⛰️ Dislivello (m)", 'Ascesa totale')
    f_fc_med = q_slider("💓 FC Media", 'FC Media')
    f_te = q_slider("📈 TE Aerobico", 'TE aerobico')
    f_tempo = q_slider("⏱️ Minuti", 'Tempo_Minuti')

    mask = (
        (df['Tipo di attivita'].isin(scelta_sport)) &
        (df['Data'].dt.date >= date_range[0]) & (df['Data'].dt.date <= (date_range[1] if len(date_range)>1 else date_range[0])) &
        (df['Calorie'].between(f_cal[0], f_cal[1])) &
        (df['Ascesa totale'].between(f_disl[0], f_disl[1])) &
        (df['FC Media'].between(f_fc_med[0], f_fc_med[1])) &
        (df['TE aerobico'].between(f_te[0], f_te[1])) &
        (df['Tempo_Minuti'].between(f_tempo[0], f_tempo[1]))
    )
    df_f = df.loc[mask].sort_values(by='Data')

    # --- VISUALIZZAZIONE ---
    if not df_f.empty:
        st.subheader("Riepilogo Selezione")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Attività", len(df_f))
        c2.metric("Dislivello Tot", f"{int(df_f['Ascesa totale'].sum())} m")
        c3.metric("Kcal Totali", f"{int(df_f['Calorie'].sum())}")
        c4.metric("Tempo Tot", f"{df_f['Tempo_Minuti'].sum()/60:.1f} h")

        st.markdown("---")
        t1, t2, t3, t4 = st.tabs(["🚀 Passo & Trend", "📊 TE vs Tempo", "❤️ Cuore", "📋 Dati"])

        with t1:
            fig_p = px.line(df_f, x='Data', y='Passo_Decimale', color='Tipo di attivita',
                            markers=True, hover_data=['Passo medio', 'Ascesa totale'],
                            template="plotly_dark", title="Evoluzione Passo (min/km)")
            fig_p.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_p, use_container_width=True)

        with t2:
            st.subheader("Analisi Efficacia Allenamento")
            fig_te = px.scatter(df_f, x='Tempo_Minuti', y='TE aerobico', color='Tipo di attivita',
                                size='Calorie', trendline="ols", template="plotly_dark",
                                title="Training Effect in relazione alla durata")
            st.plotly_chart(fig_te, use_container_width=True)

        with t3:
            fig_fc = px.line(df_f, x='Data', y=['FC Media', 'FC max'], markers=True, template="plotly_dark")
            st.plotly_chart(fig_fc, use_container_width=True)

        with t4:
            st.dataframe(df_f[['Data', 'Tipo di attivita', 'Titolo', 'Ascesa totale', 'Tempo', 'Distanza', 'Calorie', 'FC Media', 'TE aerobico', 'Passo medio']])
    else:
        st.warning("Nessun dato trovato con questi filtri.")