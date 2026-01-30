import streamlit as st

def check_password():
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
        return False
    return True

def render_sidebar(df):
    st.sidebar.header("🎯 Filtri Attività")
    
    # Filtri base: Sport e Date
    sport = st.sidebar.multiselect("Sport", sorted(df['Tipo di attivita'].unique()), default=df['Tipo di attivita'].unique())
    date_range = st.sidebar.date_input("Periodo", [df['Data'].min().date(), df['Data'].max().date()])
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Configurazione Zone (BPM)")
    st.sidebar.caption("Inserisci i limiti superiori per ogni zona")
    
    # Campi per inserire i valori delle tue analisi
    limite_z1 = st.sidebar.number_input("Fine Z1 (Recupero)", value=130)
    limite_z2 = st.sidebar.number_input("Fine Z2 (Fondo)", value=145)
    limite_z3 = st.sidebar.number_input("Fine Z3 (Tempo)", value=160)
    limite_z4 = st.sidebar.number_input("Fine Z4 (Soglia)", value=175)
    
    zone_custom = {
        "Z1": limite_z1,
        "Z2": limite_z2,
        "Z3": limite_z3,
        "Z4": limite_z4
    }

    zone_labels = ["Z1 (Recupero)", "Z2 (Fondo)", "Z3 (Tempo)", "Z4 (Soglia)", "Z5 (Massimale)"]
    scelta_zone = st.sidebar.multiselect("Filtra Zone", zone_labels, default=zone_labels)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Filtri Performance")
    
    def q_slider(label, col):
        m1, m2 = float(df[col].min()), float(df[col].max())
        if m1 == m2: m2 = m1 + 1.0
        return st.sidebar.slider(label, m1, m2, (m1, m2))

    f_cal = q_slider("🔥 Calorie", 'Calorie')
    f_disl = q_slider("⛰️ Dislivello (m)", 'Ascesa totale')
    f_te = q_slider("📈 TE Aerobico", 'TE aerobico')
    
    return {
        "sport": sport,
        "date_range": date_range,
        "zone_custom": zone_custom,
        "zone_scelte": scelta_zone,
        "cal": f_cal,
        "disl": f_disl,
        "te": f_te
    }