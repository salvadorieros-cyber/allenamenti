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
    st.sidebar.subheader("⚙️ Zone Cardio")
    metodo = st.sidebar.radio("Calcolo FC Max", ["Manuale", "Età"])
    fc_max = 185
    if metodo == "Età":
        eta = st.sidebar.number_input("Età", 5, 100, 35)
        fc_max = 220 - eta
    else:
        fc_max = st.sidebar.number_input("FC Max reale", value=185)
    
    zone_list = ["Z1 (Recupero)", "Z2 (Fondo)", "Z3 (Tempo)", "Z4 (Soglia)", "Z5 (Massimale)"]
    scelta_zone = st.sidebar.multiselect("Filtra Zone", zone_list, default=zone_list)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Filtri Performance")
    
    # Funzione interna per creare slider sicuri
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
        "fc_max": fc_max,
        "zone": scelta_zone,
        "cal": f_cal,
        "disl": f_disl,
        "te": f_te
    }