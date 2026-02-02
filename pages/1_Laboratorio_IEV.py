# 1_Laboratorio_IEV.py
import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Laboratorio Efficienza IEV", layout="wide")

# ==========================================
# 1. CARICAMENTO DATABASE
# ==========================================
@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect("Allenamenti.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        table = cursor.fetchone()
        if not table:
            return pd.DataFrame()
        table_name = table[0]

        df = pd.read_sql_query(f"SELECT * FROM '{table_name}'", conn)
        conn.close()

        # Pulizia colonne numeriche
        cols_num = ["Calorie", "FC Media", "FC max", "TE aerobico", "Cadenza media", "Distanza", "Ascesa totale"]
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].replace(["--", "", None], pd.NA), errors="coerce")

        # Data
        if "Data" in df.columns:
            df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
        else:
            return pd.DataFrame()

        # Tempo in minuti e ore
        if "Tempo" in df.columns:
            df["Tempo_TD"] = pd.to_timedelta(df["Tempo"].astype(str), errors="coerce")
            df["Tempo_Minuti"] = df["Tempo_TD"].dt.total_seconds() / 60
            df["Tempo_Ore"] = df["Tempo_Minuti"] / 60

        # Passo decimale
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

        return df.dropna(subset=["Data", "Passo_Decimale", "FC Media", "FC max"])
    except Exception as e:
        st.error(f"Errore caricamento DB: {e}")
        return pd.DataFrame()

df = load_data()
if df.empty:
    st.warning("Database vuoto o non trovato")
    st.stop()

# ==========================================
# 2. FILTRI BASE
# ==========================================
st.sidebar.header("Filtri")
sport = st.sidebar.multiselect("Tipo Sport", sorted(df['Tipo di attivita'].dropna().unique()), default=df['Tipo di attivita'].dropna().unique())
date_range = st.sidebar.date_input("Periodo", [df['Data'].min().date(), df['Data'].max().date()])

start_date = date_range[0]
end_date = date_range[1] if len(date_range) > 1 else date_range[0]
mask = (
    (df['Tipo di attivita'].isin(sport)) &
    (df['Data'].dt.date >= start_date) &
    (df['Data'].dt.date <= end_date)
)
df_f = df.loc[mask].sort_values("Data").copy()

# ==========================================
# 3. CALCOLO INDICI EFFICIENZA
# ==========================================
# 1. Velocità in m/s
df_f['vel_ms'] = 1000 / df_f['Passo_Decimale'] / 60  # Passo min/km → velocità m/s

# 2. Lavoro verticale in metri/minuto
df_f['Lavoro_vert'] = df_f['Ascesa totale'] / df_f['Tempo_Minuti']  # m/min

# 3. FC relativa
df_f['FC_rel'] = df_f['FC Media'] / df_f['FC max']  # normalizzazione tra 0 e 1

# 4. Indice Efficienza Verticale migliorato
df_f['IEV_new'] = df_f['vel_ms'] / (df_f['FC_rel'] * (1 + df_f['Lavoro_vert']/10))

# 5. (Opzionale) scala visibile per il grafico
df_f['IEV_plot'] = df_f['IEV_new'] * 100

# ==========================================
# 4. VISUALIZZAZIONE
# ==========================================
st.title("💡 Laboratorio Indici Efficienza")

st.subheader("Trend Indici di Efficienza")
fig = go.Figure()
fig.add_trace(go.Scatter(x=df_f['Data'], y=df_f['IE_std'], name="IE Standard", line=dict(color="#636EFA")))
fig.add_trace(go.Scatter(x=df_f['Data'], y=df_f['IEV'], name="IE Verticale", line=dict(color="#FFA15A")))
fig.add_trace(go.Scatter(x=df_f['Data'], y=df_f['IE_GAP'], name="IE GAP", line=dict(color="#00CCFF", dash="dot")))
fig.update_layout(template="plotly_dark", xaxis_title="Data", yaxis_title="Indice Efficienza")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Tabella dati filtrati")
st.dataframe(df_f[['Data','Tipo di attivita','Passo_Decimale','FC Media','FC max','IE_std','IEV','IE_GAP']], use_container_width=True)
