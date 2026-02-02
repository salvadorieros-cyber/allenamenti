import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
import google.generativeai as genai

# ==========================================
# 1. CONFIGURAZIONE PAGINA
# ==========================================
st.set_page_config(page_title="Fitness AI Dashboard", layout="wide")

# ==========================================
# 2. FUNZIONI UTILITY
# ==========================================

@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect("Allenamenti.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        table = cursor.fetchone()
        if not table:
            st.warning("Database vuoto")
            return pd.DataFrame()
        table_name = table[0]

        df = pd.read_sql_query(f"SELECT * FROM '{table_name}'", conn)
        conn.close()

        # Pulizia valori e conversioni
        cols_num = ["Calorie", "FC Media", "FC max", "TE aerobico", "Cadenza media", "Distanza", "Ascesa totale"]
        for col in cols_num:
            if col in df.columns:
                df[col] = df[col].replace(["--", "", None], pd.NA)
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')

        # Data
        if "Data" in df.columns:
            df["Data"] = pd.to_datetime(df["Data"], errors='coerce')
        else:
            return pd.DataFrame()

        # TE correzione scala 0-50 → 0-5
        if "TE aerobico" in df.columns and df["TE aerobico"].mean(skipna=True) > 10:
            df["TE aerobico"] = df["TE aerobico"] / 10

        # Tempo in minuti e ore
        if "Tempo" in df.columns:
            df["Tempo_TD"] = pd.to_timedelta(df["Tempo"].astype(str), errors='coerce')
            df["Tempo_Minuti"] = df["Tempo_TD"].dt.total_seconds() / 60
            df["Tempo_Ore"] = df["Tempo_Minuti"] / 60

        # Passo medio decimale
        if "Passo medio" in df.columns:
            def passo_a_decimale(p):
                try:
                    parts = str(p).split(":")
                    if len(parts) == 2:
                        return int(parts[0]) + int(parts[1])/60
                    return None
                except:
                    return None
            df["Passo_Decimale"] = df["Passo medio"].apply(passo_a_decimale)

        return df.dropna(subset=["Data", "Passo_Decimale"])
    except Exception as e:
        st.error(f"Errore caricamento database: {e}")
        return pd.DataFrame()

# ==========================================
# Zone cardio personalizzate
# ==========================================
def assegna_zona(fc, z1, z2, z3, z4):
    if fc <= z1: return "Z1 (Recupero)"
    elif fc <= z2: return "Z2 (Fondo)"
    elif fc <= z3: return "Z3 (Tempo)"
    elif fc <= z4: return "Z4 (Soglia)"
    else: return "Z5 (Massimale)"

# ==========================================
# Funzione Coach AI
# ==========================================
def chiedi_a_gemini(sintesi):
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)

        prompt = f"""
Sei un coach di endurance esperto. Analizza questi dati:
{sintesi}

Fornisci in italiano:
1. Stato di forma ed efficienza aerobica.
2. Distribuzione delle zone cardiache.
3. Suggerimenti per i prossimi allenamenti.
"""

        model = genai.GenerativeModel("models/text-bison-002")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Errore AI: {e}"

# ==========================================
# 3. AUTENTICAZIONE
# ==========================================
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

# ==========================================
# 4. DASHBOARD
# ==========================================
else:
    df = load_data()
    if df.empty:
        st.warning("Database non trovato o vuoto")
        st.stop()

    # --- Sidebar
    st.sidebar.header("🎯 Filtri Attività")
    sport = st.sidebar.multiselect("Tipo Sport", sorted(df['Tipo di attivita'].dropna().unique()), default=df['Tipo di attivita'].dropna().unique())
    date_range = st.sidebar.date_input("Periodo", [df['Data'].min().date(), df['Data'].max().date()])
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Soglie Cardio")
    z1 = st.sidebar.number_input("Fine Z1", 130)
    z2 = st.sidebar.number_input("Fine Z2", 145)
    z3 = st.sidebar.number_input("Fine Z3", 160)
    z4 = st.sidebar.number_input("Fine Z4", 175)
    
    zone_labels = ["Z1 (Recupero)", "Z2 (Fondo)", "Z3 (Tempo)", "Z4 (Soglia)", "Z5 (Massimale)"]
    scelta_zone = st.sidebar.multiselect("Filtra Zone", zone_labels, default=zone_labels)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Filtri Performance")
    def q_slider(label, col, key):
        if col not in df.columns: return (0.0, 0.0)
        minv, maxv = float(df[col].min()), float(df[col].max())
        if minv == maxv: maxv += 1.0
        return st.sidebar.slider(label, minv, maxv, (minv, maxv), key=key)
    
    f_cal = q_slider("Calorie", "Calorie", "s_cal")
    f_disl = q_slider("Dislivello", "Ascesa totale", "s_disl")
    f_te = q_slider("TE Aerobico", "TE aerobico", "s_te")

    # --- Filtraggio dati
    df['Zona Cardio'] = df['FC Media'].apply(lambda x: assegna_zona(x, z1, z2, z3, z4))
    start_date = date_range[0]
    end_date = date_range[1] if len(date_range) > 1 else date_range[0]
    mask = (
        (df['Tipo di attivita'].isin(sport)) &
        (df['Zona Cardio'].isin(scelta_zone)) &
        (df['Data'].dt.date >= start_date) &
        (df['Data'].dt.date <= end_date)
    )
    if 'Calorie' in df.columns: mask &= df['Calorie'].between(f_cal[0], f_cal[1])
    if 'Ascesa totale' in df.columns: mask &= df['Ascesa totale'].between(f_disl[0], f_disl[1])
    if 'TE aerobico' in df.columns: mask &= df['TE aerobico'].between(f_te[0], f_te[1])
    df_f = df.loc[mask].sort_values('Data').copy()

    # --- CALCOLI EFFICIENZA
    if 'Passo_Decimale' in df_f.columns and 'FC Media' in df_f.columns:
        # FC relativa
        df_f['FC_rel'] = df_f['FC Media'] / df_f['FC max']
        # Efficienza standard
        df_f['IE_std'] = (1 / df_f['Passo_Decimale'].replace(0,1)) / df_f['FC_rel']
        # Efficienza verticale
        df_f['IEV'] = ((df_f['Distanza'] + df_f['Ascesa totale']/100) / (df_f['FC_rel'] * df_f['Tempo_Ore'])) * 100
        # GAP Adjusted
        df_f['pendenza'] = df_f['Ascesa totale'] / (df_f['Distanza'] * 1000 + 0.01)
        df_f['fattore_pendenza'] = 1 + (df_f['pendenza'] * 6)
        df_f['Passo_eq'] = df_f['Passo_Decimale'] * df_f['fattore_pendenza']
        df_f['IE_GAP'] = (1 / df_f['Passo_eq']) / df_f['FC_rel']

    # --- Tabs
    tabs = st.tabs(["🚀 Trend","🏔️ Efficienza","📈 Performance","🔥 Zone Cardio","🤖 Coach AI","📋 Dati"])

    # TAB 0: Trend Passo vs FC
    with tabs[0]:
        st.subheader("Passo vs Frequenza Cardiaca")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_f['Data'], y=df_f['Passo_Decimale'], name="Passo", yaxis="y1", line=dict(color='#00CC96')))
        fig.add_trace(go.Scatter(x=df_f['Data'], y=df_f['FC Media'], name="FC", yaxis="y2", line=dict(color='#EF553B', dash='dot')))
        fig.update_layout(template="plotly_dark",
                          yaxis=dict(title="Passo", autorange="reversed"),
                          yaxis2=dict(title="BPM", side="right", overlaying="y"),
                          legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)

    # TAB 1: Efficienza comparata
    with tabs[1]:
        st.subheader("Efficienza Standard vs Verticale vs GAP")
        fig_eff = go.Figure()
        fig_eff.add_trace(go.Scatter(x=df_f['Data'], y=df_f['IE_std'], name="IE Standard", line=dict(color='#636EFA')))
        fig_eff.add_trace(go.Scatter(x=df_f['Data'], y=df_f['IEV'], name="IE Verticale", yaxis="y2", line=dict(color='#FFA15A', width=3)))
        fig_eff.add_trace(go.Scatter(x=df_f['Data'], y=df_f['IE_GAP'], name="IE GAP", yaxis="y2", line=dict(color='#00CCFF', width=2, dash='dot')))
        fig_eff.update_layout(template="plotly_dark",
                              yaxis=dict(title="IE Standard", titlefont=dict(color="#636EFA"), tickfont=dict(color="#636EFA")),
                              yaxis2=dict(title="IE Verticale / GAP", titlefont=dict(color="#FFA15A"), tickfont=dict(color="#FFA15A"),
                                          anchor="x", overlaying="y", side="right"),
                              legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_eff, use_container_width=True)

    # TAB 2: Performance
    with tabs[2]:
        st.subheader("Training Effect vs Durata")
        fig_te = px.scatter(df_f, x='Tempo_Minuti', y='TE aerobico', color='Tipo di attivita', size='Calorie', trendline="ols", template="plotly_dark")
        st.plotly_chart(fig_te, use_container_width=True)

    # TAB 3: Zone Cardio
    with tabs[3]:
        st.subheader("Distribuzione Passo per Zona Cardio")
        fig_z = px.box(df_f, x='Zona Cardio', y='Passo_Decimale', color='Zona Cardio', category_orders={"Zona Cardio": zone_labels}, template="plotly_dark")
        fig_z.update_yaxes(autorange="reversed")
        st.plotly_chart(fig_z, use_container_width=True)

    # TAB 4: Coach AI
    with tabs[4]:
        st.header("🤖 Coach AI")
        data_taglio = df_f['Data'].max() - timedelta(days=30)
        recenti = df_f[df_f['Data'] >= data_taglio]
        storici = df_f[df_f['Data'] < data_taglio]

        if not recenti.empty:
            eff_r = recenti['IEV'].mean()
            delta = ((eff_r - storici['IEV'].mean()) / storici['IEV'].mean() * 100) if not storici.empty else 0
            c1, c2, c3 = st.columns(3)
            c1.metric("IEV Medio (30gg)", f"{eff_r:.2f}", f"{delta:.1f}% vs storico")
            c2.metric("Allenamenti (30gg)", len(recenti))
            c3.metric("Dislivello Totale", f"{int(recenti['Ascesa totale'].sum())} m")

            if st.button("🚀 Genera Analisi AI"):
                sintesi = {
                    "iev_medio": round(eff_r,2),
                    "delta_percent": round(delta,1),
                    "ascesa_totale": int(recenti['Ascesa totale'].sum()),
                    "zone": recenti['Zona Cardio'].value_counts().to_dict()
                }
                with st.spinner("Analisi in corso..."):
                    st.write(chiedi_a_gemini(str(sintesi)))

            st.plotly_chart(px.scatter(df_f, x='Data', y='IEV', trendline="ols", template="plotly_dark"), use_container_width=True)

    # TAB 5: Dati
    with tabs[5]:
        st.dataframe(df_f, use_container_width=True)
