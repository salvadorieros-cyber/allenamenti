import streamlit as st
import plotly.express as px
from funzioni_dati import load_data, calcola_zona
from interfaccia import check_password, render_sidebar

if check_password():
    st.set_page_config(page_title="Fitness Pro", layout="wide")
    df = load_data()

    if not df.empty:
        # 1. Filtri
        sport, date_range, fc_max = render_sidebar(df)
        
        # 2. Elaborazione Zone
        df['Zona Cardio'] = df['FC Media'].apply(lambda x: calcola_zona(x, fc_max))
        
        # 3. Maschera dati
        mask = (df['Tipo di attivita'].isin(sport)) & \
               (df['Data'].dt.date >= date_range[0]) & \
               (df['Data'].dt.date <= (date_range[1] if len(date_range)>1 else date_range[0]))
        df_f = df.loc[mask]

        # 4. Impaginazione
        st.title("🏃 Dashboard Fitness")
        t1, t2, t3 = st.tabs(["🚀 Performance", "🔥 Zone", "📋 Dati"])
        
        with t1:
            fig = px.line(df_f.sort_values('Data'), x='Data', y='Passo_Decimale', color='Tipo di attivita', template="plotly_dark")
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
            
        with t2:
            fig_z = px.box(df_f, x='Zona Cardio', y='Passo_Decimale', color='Zona Cardio', template="plotly_dark")
            fig_z.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_z, use_container_width=True)

        with t3:
            st.dataframe(df_f.drop(columns=['Tempo_TD', 'Passo_Decimale']), use_container_width=True)