import streamlit as st
import requests
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Дождь в Уфе — Метео-Ансамбль", layout="wide", page_icon="🌧️")

st.title("🌧️ Система микролокального прогноза дождей в Уфе")
st.subheader("Анализ данных Яндекс.Погода, AccuWeather и Apple WeatherKit")

# ЗАМЕНИТЕ ЭТУ ССЫЛКУ НА ВАШУ ССЫЛКУ ИЗ RENDER (Обязательно оставьте /api/v1/forecast на конце)
API_URL = "https://ufa-rain-backend.onrender.com/api/v1/forecast"

DISTRICT_COORDS = {
    "chernikovka": [54.8122, 56.0915],
    "sipalovo": [54.7678, 56.0621],
    "center": [54.7348, 55.9579],
    "dema": [54.6983, 55.8115],
    "zaton": [54.7621, 55.8944]
}

try:
    response = requests.get(API_URL)
    if response.status_code == 200:
        forecast_data = response.json()
        col1, col2 = st.columns()
        
        with col1:
            st.markdown("### 🗺️ Карта рисков по районам")
            m = folium.Map(location=[54.735, 55.958], zoom_start=11, tiles="cartodbpositron")
            for dist in forecast_data:
                d_id = dist["district_id"]
                prob = dist["rain_probability_percent"]
                color = "darkblue" if prob > 70 else ("blue" if prob > 40 else "lightblue")
                folium.CircleMarker(
                    location=DISTRICT_COORDS[d_id],
                    radius=25,
                    popup=f"<b>{dist['district_name']}</b><br>Риск: {prob}%",
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.6
                ).add_to(m)
            st_folium(m, width=700, height=500, returned_objects=[])

        with col2:
            st.markdown("### 📊 Точные метрики")
            for dist in forecast_data:
                with st.expander(f"📍 {dist['district_name']} — **{dist['rain_probability_percent']}%**"):
                    st.write(f"**Рекомендация:** {dist['recommendation']}")
                    st.json(dist['sources_raw'])
except Exception:
    st.warning("⏳ Сервер Уфы просыпается... Пожалуйста, обновите страницу через 30-50 секунд.")
