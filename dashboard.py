import streamlit as st
import plotly.express as px
from funzioni_dati import load_data, assegna_zona
from interfaccia import check_password, render_sidebar



if check_password():
    st.set_page_config(page_title="Fitness Dashboard Pro", layout="wide")
    df = load_data()

    if not df.empty:
        f = render_sidebar(df)
        
        # ELABORAZIONE ZONE CON I TUOI VALORI
        df['Zona Cardio'] = df['FC Media'].apply(lambda x: assegna_zona_custom(x, f["zone_custom"]))
        
        # APPLICAZIONE FILTRI
        mask = (
            (df['Tipo di attivita'].isin(f["sport"])) &
            (df['Zona Cardio'].isin(f["zone_scelte"])) &
            (df['Data'].dt.date >= f["date_range"][0]) &
            (df['Data'].dt.date <= (f["date_range"][1] if len(f["date_range"])>1 else f["date_range"][0])) &
            (df['Calorie'].between(f["cal"][0], f["cal"][1])) &
            (df['Ascesa totale'].between(f["disl"][0], f["disl"][1])) &
            (df['TE aerobico'].between(f["te"][0], f["te"][1]))
        )
        
        # ... tutto il resto del codice rimane uguale ...
        df['Zona Cardio'] = df['FC Media'].apply(lambda x: assegna_zona(x, f["fc_max"]))
        
        # 3. Applicazione Filtri (Maschera)
        mask = (
            (df['Tipo di attivita'].isin(f["sport"])) &
            (df['Zona Cardio'].isin(f["zone"])) &
            (df['Data'].dt.date >= f["date_range"][0]) &
            (df['Data'].dt.date <= (f["date_range"][1] if len(f["date_range"])>1 else f["date_range"][0])) &
            (df['Calorie'].between(f["cal"][0], f["cal"][1])) &
            (df['Ascesa totale'].between(f["disl"][0], f["disl"][1])) &
            (df['TE aerobico'].between(f["te"][0], f["te"][1]))
        )
        df_f = df.loc[mask].sort_values(by='Data', ascending=False)

        # 4. Impaginazione Grafica
        st.title("🏃 Dashboard Analisi Fitness")
        
        if not df_f.empty:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Attività", len(df_f))
            c2.metric("Dislivello Tot", f"{int(df_f['Ascesa totale'].sum())} m")
            c3.metric("Kcal Totali", f"{int(df_f['Calorie'].sum())}")
            c4.metric("Tempo Totale", f"{df_f['Tempo_Minuti'].sum()/60:.1f} h")

            tabs = st.tabs(["🚀 Trend Passo", "📊 Analisi TE", "❤️ Cuore", "🔥 Zone Cardio", "📋 Dati"])
            
            with tabs[0]:
                fig = px.line(df_f.sort_values('Data'), x='Data', y='Passo_Decimale', color='Tipo di attivita', markers=True, template="plotly_dark")
                fig.update_yaxes(autorange="reversed", title="Passo (min/km)")
                st.plotly_chart(fig, use_container_width=True)
                
            with tabs[1]:
                fig_te = px.scatter(df_f, x='Tempo_Minuti', y='TE aerobico', color='Tipo di attivita', size='Calorie', trendline="ols", template="plotly_dark")
                st.plotly_chart(fig_te, use_container_width=True)

            with tabs[2]:
                fig_fc = px.line(df_f.sort_values('Data'), x='Data', y=['FC Media', 'FC max'], markers=True, template="plotly_dark")
                st.plotly_chart(fig_fc, use_container_width=True)

            with tabs[3]:
                st.subheader("Performance per Zona Cardio")
                fig_z = px.box(df_f, x='Zona Cardio', y='Passo_Decimale', color='Zona Cardio', template="plotly_dark",
                              category_orders={"Zona Cardio": ["Z1 (Recupero)", "Z2 (Fondo)", "Z3 (Tempo)", "Z4 (Soglia)", "Z5 (Massimale)"]})
                fig_z.update_yaxes(autorange="reversed")
                st.plotly_chart(fig_z, use_container_width=True)

            with tabs[4]:
                cols_view = ['Data', 'Tipo di attivita', 'Zona Cardio', 'Titolo', 'Tempo', 'Distanza', 'Ascesa totale', 'Calorie', 'FC Media', 'TE aerobico', 'Passo medio']
                st.dataframe(df_f[cols_view], use_container_width=True, hide_index=True)
        else:
            st.warning("Nessun dato trovato con questi filtri.")