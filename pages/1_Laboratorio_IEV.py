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
        # --- CALCOLI LAB AVANZATI ---
        df['Efficienza_Cadenza'] = df['Cadenza media'] / target_cadenza
        df['Intensita_Relativa'] = df['FC Media'] / 180
        
        # Formula IEV PRO
        df['IEV_test'] = (
            ((df['Distanza'] + (df['Ascesa totale'] / peso_dislivello)) * df['Efficienza_Cadenza']) / 
            (df['Intensita_Relativa'] * df['Tempo_Ore'])
        ) / 10

        # --- CALCOLO TREND E MIGLIORAMENTO ---
        df = df.sort_values('Data')
        # Media mobile su 5 attività per pulire il grafico
        df['IEV_Trend'] = df['IEV_test'].rolling(window=5, min_periods=1).mean()

        # Calcolo % miglioramento ultimi 30 giorni
        oggi = pd.Timestamp.now()
        ultimi_30 = df[df['Data'] >= (oggi - pd.Timedelta(days=30))]['IEV_test'].mean()
        precedenti_30 = df[(df['Data'] < (oggi - pd.Timedelta(days=30))) & 
                           (df['Data'] >= (oggi - pd.Timedelta(days=60)))]['IEV_test'].mean()

        # --- VISUALIZZAZIONE KPI ---
        st.subheader("📈 Analisi del Miglioramento")
        col_kpi1, col_kpi2 = st.columns(2)
        
        if pd.notna(ultimi_30) and pd.notna(precedenti_30) and precedenti_30 > 0:
            diff = ((ultimi_30 - precedenti_30) / precedenti_30) * 100
            col_kpi1.metric("Media IEV (Ultimi 30gg)", f"{ultimi_30:.2f}", f"{diff:.1f}% vs mese prec.")
        else:
            col_kpi1.metric("Media IEV (Ultimi 30gg)", f"{ultimi_30:.2f}" if pd.notna(ultimi_30) else "N/D")
            col_kpi1.info("Dati insufficienti per il confronto mensile")

        col_kpi2.metric("Miglior IEV nel periodo", f"{df['IEV_test'].max():.2f}")

        # --- GRAFICO CON LINEA DI TENDENZA ---
        fig = go.Figure()
        
        # Punti reali (Scatter)
        fig.add_trace(go.Scatter(
            x=df['Data'], y=df['IEV_test'], 
            mode='markers', name="IEV Singola Uscita",
            marker=dict(color='orange', opacity=0.4)
        ))
        
        # Linea di Trend (Media Mobile)
        fig.add_trace(go.Scatter(
            x=df['Data'], y=df['IEV_Trend'], 
            name="Trend (Media Mobile)",
            line=dict(color='red', width=4)
        ))
        
        fig.update_layout(
            template="plotly_dark",
            title="Evoluzione Efficienza Verticale",
            yaxis=dict(title="Indice IEV PRO"),
            hovermode="x unified",
            legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Nessun dato trovato nel database.")