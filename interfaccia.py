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
    
    # Sport e Date
    sport = st.sidebar.multiselect("Sport", sorted(df['Tipo di attivita'].unique()), default=df['Tipo di attivita'].unique())
    
    min_date = df['Data'].min().date()
    max_date = df['Data'].max().date()
    date_range = st.sidebar.date_input("Periodo", [min_date, max_date])
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Zone Cardio (BPM)")
    
    # Campi di input per le zone con chiavi uniche per evitare reset
    z1 = st.sidebar.number_input("Fine Z1 (Recupero)", value=130, key="val_z1")
    z2 = st.sidebar.number_input("Fine Z2 (Fondo)", value=145, key="val_z2")
    z3 = st.sidebar.number_input("Fine Z3 (Tempo)", value=160, key="val_z3")
    z4 = st.sidebar.number_input("Fine Z4 (Soglia)", value=175, key="val_z4")
    
    zone_labels = ["Z1 (Recupero)", "Z2 (Fondo)", "Z3 (Tempo)", "Z4 (Soglia)", "Z5 (Massimale)"]
    scelta_zone = st.sidebar.multiselect("Mostra Zone", zone_labels, default=zone_labels)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Performance")
    
    def q_slider(label, col, key):
        m1, m2 = float(df[col].min()), float(df[col].max())
        if m1 == m2: m2 = m1 + 1.0
        return st.sidebar.slider(label, m1, m2, (m1, m2), key=key)

    f_cal = q_slider("🔥 Calorie", 'Calorie', "slide_cal")
    f_disl = q_slider("⛰️ Dislivello (m)", 'Ascesa totale', "slide_disl")
    f_te = q_slider("📈 TE Aerobico", 'TE aerobico', "slide_te")
    
    return {
        "sport": sport,
        "date_range": date_range,
        "z1": z1, "z2": z2, "z3": z3, "z4": z4,
        "zone_scelte": scelta_zone,
        "cal": f_cal,
        "disl": f_disl,
        "te": f_te
    }