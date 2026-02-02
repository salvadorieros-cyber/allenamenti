import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Laboratorio IEV", layout="wide")

# --- FUNZIONE CARICAMENTO (Identica alla principale per coerenza) ---
def load_data_lab():
    conn = sqlite3.connect('Allenamenti.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    if not tables: return pd.DataFrame()
    df = pd.read_sql_query(f"SELECT * FROM '{tables[0][0]}'", conn)
    conn.close()
    
    # Pulizia minima necessaria
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
    for col in ['Distanza', 'Ascesa totale', 'FC Media']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
    
    if 'Tempo' in df.columns:
        df['Tempo_Ore'] = pd.to_timedelta(df['Tempo'].astype(str), errors='coerce').dt.total_seconds() / 3600
        
    if 'Passo medio' in df.columns:
        def p_to_d(p):
            try:
                parts = str(p).split(':')
                return int(parts[0]) + int(parts[1])/60 if len(parts)==2 else None
            except: return None
        df['Passo_Decimale'] = df['Passo medio'].apply(p_to_d)
    
    return df.dropna(subset=['Data', 'FC Media', 'Tempo_Ore'])

# --- LOGICA DEL LABORATORIO ---
st.title("🏔️ Laboratorio Efficienza Verticale")
st.markdown("""
In questa pagina testiamo la formula: 
$$IEV = \\frac{\\text{Km} + (\\text{D+} / 100)}{\\text{FC Media} \\times \\text{Ore}} \\times 100$$
""")

df = load_data_lab()

if not df.empty:
    # Sidebar specifica per i test
    st.sidebar.header("Parametri di Test")
    peso_dislivello = st.sidebar.slider("Peso Dislivello (D+/X)", 10, 200, 100)
    
    # Ricalcolo IEV dinamico basato sul laboratorio
    df['IE_std'] = (1 / df['Passo_Decimale'].replace(0, 1)) / df['FC Media'] * 1000
    df['IEV_test'] = ((df['Distanza'] + (df['Ascesa totale'] / peso_dislivello)) / 
                      (df['FC Media'] * df['Tempo_Ore'])) * 100

    # Grafico di analisi
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Data'], y=df['IE_std'], name="Efficienza Velocità", line=dict(color='cyan')))
    fig.add_trace(go.Scatter(x=df['Data'], y=df['IEV_test'], name="Efficienza Verticale (Test)", yaxis="y2", line=dict(color='orange', width=3)))
    
    fig.update_layout(
        template="plotly_dark",
        yaxis=dict(title="Standard"),
        yaxis2=dict(title="Verticale", overlaying="y", side="right"),
        legend=dict(orientation="h", y=1.1)
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # Analisi dei dati estremi
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top 5 Allenamenti (Verticali)")
        st.write(df.nlargest(5, 'IEV_test')[['Data', 'Tipo di attivita', 'Distanza', 'Ascesa totale', 'IEV_test']])
    
    with col2:
        st.subheader("Osservazioni Laboratorio")
        st.info(f"Stai usando un fattore di correzione di {peso_dislivello}. Più abbassi questo valore, più il dislivello 'premia' il tuo indice finale.")

else:
    st.error("Dati non caricati. Verifica Allenamenti.db")