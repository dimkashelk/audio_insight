import streamlit as st
import requests, os

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

# Базовая конфигурация страницы
st.set_page_config(page_title="AudioInsight AI", layout="wide")

# Заголовок и описание
st.title("AudioInsight AI")
st.caption("Транскрибация + дообученная Gemma для саммаризации")

# Вкладки интерфейса
tab1, tab2 = st.tabs(["Загрузка аудио", "Ввод текста"])

with tab1:
    uploaded = st.file_uploader("Загрузите аудио (.mp3, .wav, .m4a, .mp4)", type=["mp3", "wav", "m4a", "mp4"])
    if uploaded:
        if st.button("Обработать аудио"):
            with st.spinner("Загрузка файла..."):
                files = {"file": (uploaded.name, uploaded.getvalue())}
                res = requests.post(f"{API_URL}/upload", files=files)
                if res.status_code != 200:
                    st.error(f"Ошибка: {res.text}")
                    st.stop()
                task_id = res.json()["task_id"]
                st.session_state["audio_task_id"] = task_id
                st.success("Файл отправлен в обработку")

with tab2:
    st.info("Вставьте текст для анализа")