import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import timedelta

st.set_page_config(page_title="Laboratorio IEV", layout="wide")

# --- FUNZIONE CARICAMENTO DATI AGGIORNATA ---
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
        
        # PULIZIA NUMERICA COMPLETA (Cruciale per evitare l'errore che hai visto)
        cols_da_pulire = ['Distanza', 'Ascesa totale', 'FC Media', 'Cadenza media', 'FC max']
        for col in cols_da_pulire:
            if col in df.columns:
                # Trasforma in stringa, toglie punti delle migliaia, cambia virgole in punti, forza in numero
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace('.', '').str.replace(',', '.'), 
                    errors='coerce'
                )
        
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
        
        # Riempiamo i valori mancanti della cadenza con la media per non bloccare i calcoli
        if 'Cadenza media' in df.columns:
            media_cad = df['Cadenza media'].mean()
            df['Cadenza media'] = df['Cadenza media'].fillna(media_cad if pd.notna(media_cad) else 170)

        return df.dropna(subset=['Data', 'FC Media', 'Tempo_Ore'])
    except Exception as e:
        st.error(f"Errore nel caricamento dati: {e}")
        return pd.DataFrame()

# --- INTERFACCIA ---
st.title("🏔️ Laboratorio Efficienza Verticale PRO")

df_raw = load_data_lab()

if not df_raw.empty:
    # --- SIDEBAR: FILTRI ---
    st.sidebar.header("🎯 Filtri")
    tipi_sport = sorted(df_raw['Tipo di attivita'].dropna().unique())
    sport_selezionati = st.sidebar.multiselect("Sport", tipi_sport, default=tipi_sport)
    
    data_min, data_max = df_raw['Data'].min().date(), df_raw['Data'].max().date()
    range_date = st.sidebar.date_input("Periodo", [data_min, data_max])
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🧪 Parametri Formula")
    peso_dislivello = st.sidebar.slider("Peso Dislivello (D+/X)", 10, 200, 100)
    target_cadenza = st.sidebar.number_input("Target Cadenza (Ottimale)", value=175)

    # --- APPLICAZIONE FILTRI ---
    if len(range_date) == 2:
        mask = (df_raw['Tipo di attivita'].isin(sport_selezionati)) & \
               (df_raw['Data'].dt.date >= range_date[0]) & \
               (df_raw['Data'].dt.date <= range_date[1])
        df = df_raw.loc[mask].copy()
    else:
        df = df_raw.copy()

    if not df.empty:
        # --- CALCOLI LAB AVANZATI (Con gestione errori) ---
        
        # 1. Efficienza Cadenza (ora protetta da errori di tipo)
        df['Efficienza_Cadenza'] = df['Cadenza media'] / target_cadenza
        
        # 2. Intensità Relativa (FC Media / 180 o FC Max se disponibile)
        df['Intensita_Relativa'] = df['FC Media'] / 180
        
        # 3. Indice Standard (per confronto)
        df['IE_std'] = (1 / df['Passo_Decimale'].replace(0, 1)) / df['FC Media'] * 1000
        
        # 4. FORMULA IEV PRO
        # Normalizzata: [(Km + D+/Peso) * Eff_Cadenza] / [Intensità * Ore]
        df['IEV_test'] = (
            ((df['Distanza'] + (df['Ascesa totale'] / peso_dislivello)) * df['Efficienza_Cadenza']) / 
            (df['Intensita_Relativa'] * df['Tempo_Ore'])
        ) / 10

        # --- GRAFICO ---
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['Data'], y=df['IE_std'], name="Eff. Standard", line=dict(color='cyan', dash='dot')))
        fig.add_trace(go.Scatter(x=df['Data'], y=df['IEV_test'], name="Eff. Verticale PRO", yaxis="y2", line=dict(color='orange', width=3)))
        
        fig.update_layout(
            template="plotly_dark",
            yaxis=dict(title="Standard"),
            yaxis2=dict(title="Verticale PRO", overlaying="y", side="right"),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- ANALISI TECNICA ---
        st.subheader("🕵️ Analisi Biomeccanica")
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Top 5 Allenamenti Efficienti (IEV)**")
            st.dataframe(df.nlargest(5, 'IEV_test')[['Data', 'Distanza', 'Ascesa totale', 'Cadenza media', 'IEV_test']])
        with c2:
            st.write("**Relazione Cadenza/Pendenza**")
            fig_cad = go.Figure(go.Scatter(x=df['Ascesa totale'], y=df['Cadenza media'], mode='markers', marker=dict(color='orange')))
            fig_cad.update_layout(template="plotly_dark", xaxis_title="Dislivello (m)", yaxis_title="Cadenza (ppm)")
            st.plotly_chart(fig_cad, use_container_width=True)
            
    else:
        st.info("Filtra i dati per vedere i risultati.")
else:
    st.error("Nessun dato trovato nel database.")