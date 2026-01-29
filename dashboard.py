import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Analisi Fitness Totale", layout="wide")
st.title("📈 Dashboard Completa: Focus Dislivello & Performance")

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
        
        # Conversione TEMPO
        if 'Tempo' in df.columns:
            df['Tempo_TD'] = pd.to_timedelta(df['Tempo'].astype(str), errors='coerce')
            df['Tempo_Minuti'] = df['Tempo_TD'].dt.total_seconds() / 60
        
        # Conversione PASSO MEDIO
        if 'Passo medio' in df.columns:
            def passo_a_decimale(p):
                try:
                    parts = str(p).split(':')
                    if len(parts) == 2:
                        return int(parts[0]) + int(parts[1])/60
                    return None
                except: return None
            df['Passo_Decimale'] = df['Passo medio'].apply(passo_a_decimale)

        # Pulizia NUMERICI (Aggiunta Ascesa Totale)
        cols_numeriche = ['Calorie', 'FC Media', 'FC max', 'TE aerobico', 'Cadenza media', 'Distanza', 'Ascesa totale']
        for col in cols_numeriche:
            if col in df.columns:
                # Rimuove eventuali punti delle migliaia e cambia virgola in punto
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
        
        return df.dropna(subset=['Data'])
    except Exception as e:
        st.error(f"Errore caricamento: {e}")
        return pd.DataFrame()

df = load_data()

if not df.empty:
    # --- SIDEBAR: FILTRI ---
    st.sidebar.header("🎯 Filtri Globali")

    sport_list = sorted(df['Tipo di attivita'].unique().tolist())
    scelta_sport = st.sidebar.multiselect("Sport", sport_list, default=sport_list)
    date_range = st.sidebar.date_input("Periodo", [df['Data'].min(), df['Data'].max()])

    st.sidebar.markdown("---")
    st.sidebar.subheader("Parametri di Performance")

    def quick_slider(label, col):
        m1, m2 = float(df[col].min()), float(df[col].max())
        # Gestione se i valori sono uguali (es. tutti zero)
        if m1 == m2: m2 = m1 + 1.0
        return st.sidebar.slider(label, m1, m2, (m1, m2))

    f_cal = quick_slider("🔥 Calorie", 'Calorie')
    f_disl = quick_slider("⛰️ Dislivello (m)", 'Ascesa totale')
    f_fc_med = quick_slider("💓 FC Media", 'FC Media')
    f_fc_max = quick_slider("⚡ FC Max", 'FC max')
    f_te = quick_slider("📈 TE Aerobico", 'TE aerobico')
    f_tempo = quick_slider("⏱️ Minuti", 'Tempo_Minuti')

    # Applicazione Filtri
    mask = (
        (df['Tipo di attivita'].isin(scelta_sport)) &
        (df['Data'].dt.date >= date_range[0]) & (df['Data'].dt.date <= (date_range[1] if len(date_range)>1 else date_range[0])) &
        (df['Calorie'].between(f_cal[0], f_cal[1])) &
        (df['Ascesa totale'].between(f_disl[0], f_disl[1])) &
        (df['FC Media'].between(f_fc_med[0], f_fc_med[1])) &
        (df['FC max'].between(f_fc_max[0], f_fc_max[1])) &
        (df['TE aerobico'].between(f_te[0], f_te[1])) &
        (df['Tempo_Minuti'].between(f_tempo[0], f_tempo[1]))
    )
    df_f = df.loc[mask].sort_values(by='Data')

    # --- LAYOUT DASHBOARD ---
    if not df_f.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Attività", len(df_f))
        c2.metric("Dislivello Totale", f"{int(df_f['Ascesa totale'].sum())} m")
        c3.metric("FC Media", f"{int(df_f['FC Media'].mean())} bpm")
        c4.metric("Distanza Tot", f"{df_f['Distanza'].sum():.1f} km")

        st.markdown("---")

        t1, t2, t3 = st.tabs(["🚀 Analisi Passo & Quota", "❤️ Cuore", "📋 Dati"])

        with t1:
            st.subheader("Relazione Passo vs Dislivello")
            # Grafico a due assi o combinato
            fig_p = px.line(df_f, x='Data', y='Passo_Decimale', color='Tipo di attivita',
                            markers=True, hover_data=['Ascesa totale', 'Titolo'],
                            template="plotly_dark")
            fig_p.update_yaxes(autorange="reversed", title="Passo (min/km)")
            st.plotly_chart(fig_p, use_container_width=True)
            
            st.subheader("Dislivello per Sessione")
            fig_disl = px.bar(df_f, x='Data', y='Ascesa totale', color='Tipo di attivita',
                              template="plotly_dark", title="Metri di ascesa positiva")
            st.plotly_chart(fig_disl, use_container_width=True)

        with t2:
            st.subheader("Carico Cardiaco")
            fig_fc = px.line(df_f, x='Data', y=['FC Media', 'FC max'], 
                             markers=True, template="plotly_dark")
            st.plotly_chart(fig_fc, use_container_width=True)

        with t3:
            st.dataframe(df_f[['Data', 'Tipo di attivita', 'Titolo', 'Ascesa totale', 'Tempo', 'Distanza', 
                               'Calorie', 'FC Media', 'FC max', 'TE aerobico', 'Passo medio']])
    else:
        st.warning("Nessun dato con questi filtri.")