import streamlit as st
import os

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# Базовая конфигурация страницы
st.set_page_config(page_title="AudioInsight AI", layout="wide")

# Заголовок и описание
st.title("AudioInsight AI")
st.caption("Транскрибация + дообученная Gemma для саммаризации")

# Вкладки интерфейса
tab1, tab2 = st.tabs(["Загрузка аудио", "Ввод текста"])

# Заглушки для контента вкладок
with tab1:
    st.info("Загрузите аудиофайл для обработки")

with tab2:
    st.info("Вставьте текст для анализа")