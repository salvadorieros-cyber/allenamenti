import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. FUNZIONI LOGICHE
# ==========================================
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
        st.error(f"Errore caricamento database: {e}")
        return pd.DataFrame()

def assegna_zona_custom(fc, z1, z2, z3, z4):
    if fc <= z1: return "Z1 (Recupero)"
    elif fc <= z2: return "Z2 (Fondo)"
    elif fc <= z3: return "Z3 (Tempo)"
    elif fc <= z4: return "Z4 (Soglia)"
    else: return "Z5 (Massimale)"

# ==========================================
# 2. SICUREZZA
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False
    if not st.session_state.password_correct:
        st.title("🔐 Accesso Riservato")
        pw = st.text_input("Password", type="password")
        if st.button("Accedi"):
            if pw == "elgnaro":
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("Password errata")
        return False
    return True

# ==========================================
# 3. DASHBOARD
# ==========================================
if check_password():
    st.set_page_config(page_title="Fitness Dashboard Pro", layout="wide")
    df = load_data()

    if not df.empty:
        # --- SIDEBAR ---
        st.sidebar.header("🎯 Filtri")
        sport = st.sidebar.multiselect("Sport", sorted(df['Tipo di attivita'].unique()), default=df['Tipo di attivita'].unique())
        date_range = st.sidebar.date_input("Periodo", [df['Data'].min().date(), df['Data'].max().date()])
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚙️ Zone Cardio (BPM)")
        z1 = st.sidebar.number_input("Fine Z1", value=130, key="z1")
        z2 = st.sidebar.number_input("Fine Z2", value=145, key="z2")
        z3 = st.sidebar.number_input("Fine Z3", value=160, key="z3")
        z4 = st.sidebar.number_input("Fine Z4", value=175, key="z4")
        
        zone_labels = ["Z1 (Recupero)", "Z2 (Fondo)", "Z3 (Tempo)", "Z4 (Soglia)", "Z5 (Massimale)"]
        scelta_zone = st.sidebar.multiselect("Mostra Zone", zone_labels, default=zone_labels)

        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 Performance")
        def q_slider(label, col, key):
            m1, m2 = float(df[col].min()), float(df[col].max())
            if m1 == m2: m2 = m1 + 1.0
            return st.sidebar.slider(label, m1, m2, (m1, m2), key=key)

        f_cal = q_slider("🔥 Calorie", 'Calorie', "cal")
        f_disl = q_slider("⛰️ Dislivello", 'Ascesa totale', "disl")
        f_te = q_slider("📈 TE Aerobico", 'TE aerobico', "te")

        # --- FILTRAGGIO ---
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

        st.title("🏃 Dashboard Analisi Fitness")
        
        if not df_f.empty:
            # Metriche
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Attività", len(df_f))
            c2.metric("Dislivello Tot", f"{int(df_f['Ascesa totale'].sum())} m")
            c3.metric("Kcal Totali", f"{int(df_f['Calorie'].sum())}")
            c4.metric("Tempo Tot", f"{df_f['Tempo_Minuti'].sum()/60:.1f} h")

            tabs = st.tabs(["🚀 Trend Passo & FC", "📊 Analisi TE", "❤️ Cuore", "🔥 Zone Cardio", "📋 Dati"])
            
            with tabs[0]:
                st.subheader("Relazione tra Passo e Frequenza Cardiaca")
                df_plot = df_f.dropna(subset=['Passo_Decimale', 'FC Media'])
                
                if not df_plot.empty:
                    fig = go.Figure()
                    # Linea Passo
                    fig.add_trace(go.Scatter(x=df_plot['Data'], y=df_plot['Passo_Decimale'], name="Passo",
                                            mode='lines+markers', line=dict(color='#00CC96', width=2), yaxis="y"))
                    # Linea FC
                    fig.add_trace(go.Scatter(x=df_plot['Data'], y=df_plot['FC Media'], name="FC Media",
                                            mode='lines+markers', line=dict(color='#EF553B', width=2, dash='dot'), yaxis="y2"))

                    fig.update_layout(
                        template="plotly_dark",
                        xaxis=dict(title="Data"),
                        yaxis=dict(title="Passo (min/km)", autorange="reversed", side="left"),
                        yaxis2=dict(title="FC Media (bpm)", side="right", overlaying="y", showgrid=False),
                        legend=dict(orientation="h", y=1.1),
                        margin=dict(l=20, r=20, t=50, b=20)
                    )
                    st.plotly_chart(fig, use_container_width=True)

            with tabs[1]:
                fig_te = px.scatter(df_f, x='Tempo_Minuti', y='TE aerobico', color='Tipo di attivita', size='Calorie', trendline="ols", template="plotly_dark")
                st.plotly_chart(fig_te, use_container_width=True)

            with tabs[2]:
                fig_fc = px.line(df_f, x='Data', y=['FC Media', 'FC max'], markers=True, template="plotly_dark")
                st.plotly_chart(fig_fc, use_container_width=True)

            with tabs[3]:
                fig_z = px.box(df_f, x='Zona Cardio', y='Passo_Decimale', color='Zona Cardio', 
                              category_orders={"Zona Cardio": zone_labels}, template="plotly_dark")
                fig_z.update_yaxes(autorange="reversed")
                st.plotly_chart(fig_z, use_container_width=True)

            with tabs[4]:
                st.dataframe(df_f.drop(columns=['Tempo_TD', 'Passo_Decimale']), use_container_width=True, hide_index=True)
        else:
            st.warning("Nessun dato trovato.")