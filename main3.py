import streamlit as st
from streamlit_extras.card import card
import streamlit_authenticator as stauth

st.set_page_config(
    layout="wide",
    page_title="Хадисите на Мухаммед(С.А.С) нов адрес",
    page_icon='logo.png',
    initial_sidebar_state='collapsed',
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
.stActionButton {visibility: hidden;}
.block-container {
    padding-top: 0;
    padding-left: 2rem;
    padding-right: 2rem;}
footer {visibility: hidden;}
header {visibility: hidden;}
[data-testid="stSidebarUserContent"] {
    margin-top: 10px;
    padding-top: 0rem;
}
@media (max-width: 640px) {
    .block-container {
    padding-top: 1px;
    padding-left: 1rem;
    padding-right: 1rem;
    }
}
}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

col1, col2, col3 = st.columns([1,2,1])
with col1:
    st.empty()
with col2:
    st.image("logo.png", width=200, use_column_width="never")
    st.title("Хадисите на Мухаммед(С.А.С)")
    st.title("нов адрес")
    st.write("За да, посетете новия адрес натиснете линка.")
    st.header("https://hadisi.kidn3y.com/")
    
with col3:
    st.empty()