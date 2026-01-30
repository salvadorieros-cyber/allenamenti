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
    st.sidebar.header("🎯 Filtri")
    sport = st.sidebar.multiselect("Sport", sorted(df['Tipo di attivita'].unique()), default=df['Tipo di attivita'].unique())
    date_range = st.sidebar.date_input("Periodo", [df['Data'].min().date(), df['Data'].max().date()])
    
    st.sidebar.markdown("---")
    metodo = st.sidebar.radio("FC Max", ["Manuale", "Età"])
    fc_max = 185
    if metodo == "Età":
        eta = st.sidebar.number_input("Età", 5, 100, 35)
        fc_max = 220 - eta
    else:
        fc_max = st.sidebar.number_input("FC Max reale", value=185)
        
    return sport, date_range, fc_max