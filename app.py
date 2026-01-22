import streamlit as st

# Configuração global da página
st.set_page_config(
    page_title="Gestão de Aluguéis",
    page_icon="🏢",
    layout="wide"
)

# Definição das páginas
pages = {
    "Principal": [
        st.Page("views/disponibilidade.py", title="Disponibilidade", icon="📅"),
        st.Page("pages/1_Detalhes_Reservas.py", title="Detalhes Reservas", icon="📋"),
    ],
}

pg = st.navigation(pages)

pg.run()
