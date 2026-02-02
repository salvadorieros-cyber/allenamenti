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
      # --- CALCOLI LAB AVANZATI ---
        
        # 1. Fattore Efficienza di Passo (Cadenza)
        # Più la cadenza è vicina a quella ottimale (es. 170-180), più sei efficiente
        if 'Cadenza media' in df.columns:
             df['Efficienza_Cadenza'] = df['Cadenza media'] / 175 # Rapporto rispetto a cadenza target
        else:
             df['Efficienza_Cadenza'] = 1.0

        # 2. Rapporto di Intensità (FC Media vs FC Max se disponibile, altrimenti vs 180)
        # Serve a capire quanto "motore" stai usando
        df['Intensita_Relativa'] = df['FC Media'] / 180

        # 3. FORMULA IEV PRO
        # [ (Distanza_Km + (D+/Peso)) * Efficienza_Cadenza ] / (Intensità_Relativa * Tempo_Ore)
        df['IEV_test'] = (
            ((df['Distanza'] + (df['Ascesa totale'] / peso_dislivello)) * df['Efficienza_Cadenza']) / 
            (df['Intensita_Relativa'] * df['Tempo_Ore'])
        ) / 10 # Normalizziamo il valore finale

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