import streamlit as st
import requests
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Радар Уфы", layout="wide", page_icon="🌧️")

st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Контурный анализ рисков осадков по районам города")

# Укажите вашу ссылку из Render (с хвостиком /api/v1/forecast на конце!)
API_URL = "https://ufa-rain-backend-1.onrender.com/api/v1/forecast"

DISTRICT_POLYGONS = {
    "chernikovka": [[54.795, 56.050], [54.835, 56.050], [54.845, 56.120], [54.795, 56.140]],
    "sipalovo": [[54.755, 56.030], [54.780, 56.030], [54.780, 56.090], [54.755, 56.080]],
    "center": [[54.710, 55.930], [54.750, 55.930], [54.750, 56.020], [54.710, 56.020]],
    "dema": [[54.670, 55.780], [54.710, 55.780], [54.710, 55.840], [54.670, 55.840]],
    "zaton": [[54.740, 55.860], [54.780, 55.860], [54.780, 55.920], [54.740, 55.920]]
}

# Краткий встроенный мониторинг прямо по центру страницы
status_placeholder = st.info("⏳ Подключение к метеоспутникам Уфы...")

try:
    # Запрашиваем данные (с ограничением времени ожидания в 6 секунд)
    response = requests.get(API_URL, timeout=6)
    
    if response.status_code == 200:
        forecast_data = response.json()
        status_placeholder.success(f"🟢 УСПЕШНО: Данные обновлены! Секторов в обработке: {len(forecast_data)}")
        
        st.markdown("### 🗺️ Интерактивная карта осадков")
        m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="cartodbpositron")
        
        for dist in forecast_data:
            d_id = dist["district_id"]
            prob = dist["rain_probability_percent"]
            
            if prob > 70:
                fill_color, line_color = "#2b2bd6", "#1a1a99"
            elif prob > 40:
                fill_color, line_color = "#73a5ff", "#4a7acc"
            else:
                fill_color, line_color = "#70e087", "#439953"
            
            if d_id in DISTRICT_POLYGONS:
                folium.Polygon(
                    locations=DISTRICT_POLYGONS[d_id],
                    popup=f"<b>{dist['district_name']}</b><br>Вероятность: {prob}%",
                    color=line_color,
                    weight=3,
                    fill=True,
                    fill_color=fill_color,
                    fill_opacity=0.4
                ).add_to(m)
        
        # Выводим карту
        st_folium(m, width=900, height=500, key="ufa_radar_final")
        
        st.markdown("### 📊 Детальная метеосводка")
        for dist in forecast_data:
            with st.expander(f"📍 {dist['district_name']} — **{dist['rain_probability_percent']}%**"):
                st.write(f"**Анализ:** {dist['recommendation']}")
                st.json(dist['sources_raw'])
    else:
        status_placeholder.error(f"🔴 ОШИБКА: Сервер вернул код {response.status_code}")
except Exception as e:
    status_placeholder.warning(f"⏳ Сервер на Render просыпается... Пожалуйста, обновите страницу через 30 секунд. (Тех. инфо: {e})")
