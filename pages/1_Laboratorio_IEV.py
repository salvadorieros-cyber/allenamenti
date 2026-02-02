import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import timedelta

st.set_page_config(page_title="Laboratorio IEV", layout="wide")

# --- FUNZIONE CARICAMENTO DATI ---
def load_data_lab():
    try:
        conn = sqlite3.connect('Allenamenti.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        if not tables: return pd.DataFrame()
        
        df = pd.read_sql_query(f"SELECT * FROM '{tables[0][0]}'", conn)
        conn.close()
        
        # Pulizia Date
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        
        # Pulizia Numerica (punti e virgole)
        for col in ['Distanza', 'Ascesa totale', 'FC Media']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
        
        # Calcolo Tempi
        if 'Tempo' in df.columns:
            td = pd.to_timedelta(df['Tempo'].astype(str), errors='coerce')
            df['Tempo_Ore'] = td.dt.total_seconds() / 3600
            
        if 'Passo medio' in df.columns:
            def p_to_d(p):
                try:
                    parts = str(p).split(':')
                    return int(parts[0]) + int(parts[1])/60 if len(parts)==2 else None
                except: return None
            df['Passo_Decimale'] = df['Passo medio'].apply(p_to_d)
        
        return df.dropna(subset=['Data', 'FC Media', 'Tempo_Ore'])
    except Exception as e:
        st.error(f"Errore nel laboratorio: {e}")
        return pd.DataFrame()

# --- INTERFACCIA ---
st.title("🏔️ Laboratorio Efficienza Verticale")
st.markdown("Usa questa pagina per testare l'impatto del dislivello sui tuoi indici di performance.")

df_raw = load_data_lab()

if not df_raw.empty:
    # --- SIDEBAR: FILTRI ---
    st.sidebar.header("🎯 Filtri di Analisi")
    
    # 1. Filtro Attività
    tipi_sport = sorted(df_raw['Tipo di attivita'].dropna().unique())
    sport_selezionati = st.sidebar.multiselect("Seleziona Sport", tipi_sport, default=tipi_sport)
    
    # 2. Filtro Date
    data_min = df_raw['Data'].min().date()
    data_max = df_raw['Data'].max().date()
    range_date = st.sidebar.date_input("Periodo Temporale", [data_min, data_max])
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🧪 Parametri Formula")
    # Questo slider ci serve per capire quanto "pesare" il dislivello
    peso_dislivello = st.sidebar.slider("Fattore Correzione D+ (Standard = 100)", 10, 200, 100)

    # --- APPLICAZIONE FILTRI ---
    if len(range_date) == 2:
        mask = (
            (df_raw['Tipo di attivita'].isin(sport_selezionati)) &
            (df_raw['Data'].dt.date >= range_date[0]) &
            (df_raw['Data'].dt.date <= range_date[1])
        )
        df = df_raw.loc[mask].copy()
    else:
        df = df_raw.copy() # In attesa che l'utente selezioni la seconda data

    if not df.empty:
        # --- CALCOLI LAB ---
        # IE Standard: Velocità / FC
        df['IE_std'] = (1 / df['Passo_Decimale'].replace(0, 1)) / df['FC Media'] * 1000
        
        # IEV: (Km + (D+ / Fattore)) / (FC * Ore) * 100
        df['IEV_test'] = ((df['Distanza'] + (df['Ascesa totale'] / peso_dislivello)) / 
                          (df['FC Media'] * df['Tempo_Ore'])) * 100

        # --- GRAFICO COMPARATIVO ---
        st.subheader("Confronto Indici Filtrati")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['Data'], y=df['IE_std'], name="Eff. Velocità (Standard)", line=dict(color='cyan')))
        fig.add_trace(go.Scatter(x=df['Data'], y=df['IEV_test'], name="Eff. Verticale (Test)", yaxis="y2", line=dict(color='orange', width=3)))
        
        fig.update_layout(
            template="plotly_dark",
            yaxis=dict(title="Indice Standard", titlefont=dict(color="cyan"), tickfont=dict(color="cyan")),
            yaxis2=dict(title="Indice Verticale (IEV)", overlaying="y", side="right", titlefont=dict(color="orange"), tickfont=dict(color="orange")),
            legend=dict(orientation="h", y=1.1),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- TABELLA DETTAGLI ---
        st.subheader("Analisi di dettaglio")
        st.dataframe(
            df[['Data', 'Tipo di attivita', 'Distanza', 'Ascesa totale', 'FC Media', 'IE_std', 'IEV_test']]
            .sort_values('Data', ascending=False),
            use_container_width=True
        )
    else:
        st.info("Nessun dato corrispondente ai filtri selezionati.")
else:
    st.error("Dati non disponibili nel database.")