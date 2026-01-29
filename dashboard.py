import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

# --- PROTEZIONE ACCESSO (Opzionale ma consigliata) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if not st.session_state.password_correct:
        st.title("🔐 Accesso Riservato")
        pw = st.text_input("Inserisci la password", type="password")
        if st.button("Accedi"):
            if pw == "elgnaro": # Sostituisci con la tua pass
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("Password errata")
        st.stop()

check_password()

st.set_page_config(page_title="Analisi Fitness Totale", layout="wide")
st.title("📈 Dashboard Performance: Focus TE Aerobico")

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
        
        # Conversione TEMPO in Minuti
        if 'Tempo' in df.columns:
            df['Tempo_TD'] = pd.to_timedelta(df['Tempo'].astype(str), errors='coerce')
            df['Tempo_Minuti'] = df['Tempo_TD'].dt.total_seconds() / 60
        
        # Pulizia Colonne Numeriche
        cols_numeriche = ['Calorie', 'FC Media', 'FC max', 'TE aerobico', 'Cadenza media', 'Distanza', 'Ascesa totale']
        for col in cols_numeriche:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
        
        return df.dropna(subset=['Data'])
    except Exception as e:
        st.error(f"Errore caricamento: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # --- SIDEBAR FILTRI ---
    st.sidebar.header("🎯 Filtri")
    sport_list = sorted(df['Tipo di attivita'].unique().tolist())
    scelta_sport = st.sidebar.multiselect("Sport", sport_list, default=sport_list)
    date_range = st.sidebar.date_input("Periodo", [df['Data'].min(), df['Data'].max()])

    # Filtri numerici slider
    f_te = st.sidebar.slider("TE Aerobico", 0.0, 5.0, (0.0, 5.0))
    f_tempo = st.sidebar.slider("Tempo (Minuti)", 0, int(df['Tempo_Minuti'].max()), (0, int(df['Tempo_Minuti'].max())))

    mask = (df['Tipo di attivita'].isin(scelta_sport)) & \
           (df['Data'].dt.date >= date_range[0]) & (df['Data'].dt.date <= (date_range[1] if len(date_range)>1 else date_range[0])) & \
           (df['TE aerobico'].between(f_te[0], f_te[1])) & \
           (df['Tempo_Minuti'].between(f_tempo[0], f_tempo[1]))
    
    df_f = df.loc[mask].sort_values(by='Data')

    # --- LAYOUT DASHBOARD ---
    if not df_f.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Attività", len(df_f))
        c2.metric("Media TE Aerobico", f"{df_f['TE aerobico'].mean():.1f}")
        c3.metric("Tempo Totale", f"{df_f['Tempo_Minuti'].sum()/60:.1f} h")
        c4.metric("Kcal Medie", f"{int(df_f['Calorie'].mean())}")

        st.markdown("---")

        t1, t2, t3 = st.tabs(["📊 Analisi TE vs Tempo", "❤️ Cuore & Passo", "📋 Dati"])

        with t1:
            st.subheader("Relazione tra Durata e Training Effect")
            # Grafico a dispersione con linea di trend per vedere la correlazione
            fig_te_tempo = px.scatter(df_f, x='Tempo_Minuti', y='TE aerobico', 
                                     color='Tipo di attivita', size='Calorie',
                                     hover_data=['Data', 'Titolo', 'FC Media'],
                                     trendline="ols", # Aggiunge una linea di tendenza statistica
                                     template="plotly_dark",
                                     title="Efficacia (TE) in funzione della Durata (Minuti)")
            st.plotly_chart(fig_te_tempo, use_container_width=True)
            
            st.subheader("Evoluzione TE nel tempo")
            fig_te_line = px.line(df_f, x='Data', y='TE aerobico', color='Tipo di attivita',
                                 markers=True, template="plotly_dark")
            st.plotly_chart(fig_te_line, use_container_width=True)

        with t2:
            st.subheader("Analisi Cardiaca")
            fig_fc = px.line(df_f, x='Data', y=['FC Media', 'FC max'], 
                             markers=True, template="plotly_dark")
            st.plotly_chart(fig_fc, use_container_width=True)

        with t3:
            st.dataframe(df_f[['Data', 'Tipo di attivita', 'Titolo', 'TE aerobico', 'Tempo', 'Tempo_Minuti', 'Calorie', 'FC Media']])
    else:
        st.warning("Nessun dato con questi filtri.")