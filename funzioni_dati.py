import streamlit as st
import sqlite3
import pandas as pd

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
        
        # Pulizia numerica universale
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
        st.error(f"Errore caricamento: {e}")
        return pd.DataFrame()

def assegna_zona_custom(fc, z1, z2, z3, z4):
    if fc <= z1: return "Z1 (Recupero)"
    elif fc <= z2: return "Z2 (Fondo)"
    elif fc <= z3: return "Z3 (Tempo)"
    elif fc <= z4: return "Z4 (Soglia)"
    else: return "Z5 (Massimale)"