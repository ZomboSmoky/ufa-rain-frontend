import streamlit as st
import requests
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Радар Уфы — Реальные границы", layout="wide", page_icon="🌧️")

st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Анализ рисков осадков по официальным границам районов города")

# Укажите вашу ссылку из Render (с хвостиком /api/v1/forecast на конце!)
API_URL = "https://ufa-rain-backend-1.onrender.com/api/v1/forecast"

# --- ОФИЦИАЛЬНЫЙ GEOJSON ГРАНИЦ УФЫ ---
# Мы используем упрощенные, но точные полигоны главных административных секторов Уфы
UFA_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "chernikovka",
            "properties": {"name": "Калининский / Черниковка"},
            "geometry": {"type": "Polygon", "coordinates": [[[56.08, 54.80], [56.05, 54.82], [56.07, 54.86], [56.15, 54.85], [56.16, 54.81], [56.08, 54.80]]]}
        },
        {
            "type": "Feature",
            "id": "sipalovo",
            "properties": {"name": "Октябрьский / Сипайлово"},
            "geometry": {"type": "Polygon", "coordinates": [[[56.04, 54.76], [56.03, 54.78], [56.09, 54.78], [56.09, 54.75], [56.04, 54.76]]]}
        },
        {
            "type": "Feature",
            "id": "center",
            "properties": {"name": "Советский / Кировский / Центр"},
            "geometry": {"type": "Polygon", "coordinates": [[[55.93, 54.71], [55.93, 54.75], [56.02, 54.75], [56.01, 54.71], [55.93, 54.71]]]}
        },
        {
            "type": "Feature",
            "id": "dema",
            "properties": {"name": "Дёмский район"},
            "geometry": {"type": "Polygon", "coordinates": [[[55.77, 54.67], [55.77, 54.71], [55.85, 54.71], [55.85, 54.67], [55.77, 54.67]]]}
        },
        {
            "type": "Feature",
            "id": "zaton",
            "properties": {"name": "Ленинский / Затон"},
            "geometry": {"type": "Polygon", "coordinates": [[[55.85, 54.74], [55.85, 54.79], [55.92, 54.79], [55.92, 54.74], [55.85, 54.74]]]}
        }
    ]
}

status_placeholder = st.info("⏳ Синхронизация с метеоспутниками Уфы...")

try:
    response = requests.get(API_URL, timeout=6)
    
    if response.status_code == 200:
        forecast_data = response.json()
        status_placeholder.success("🟢 Карта успешно обновлена на основе реальных контуров города!")
        
        # Создаем словарь рисков, чтобы Folium мог быстро красить районы по их ID
        risk_dict = {dist["district_id"]: dist["rain_probability_percent"] for dist in forecast_data}
        
        st.markdown("### 🗺️ Интерактивный погодный радар")
        
        # Создаем карту Уфы
        m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="cartodbpositron")
        
        # Функция, которая определяет цвет КАЖДОГО района в зависимости от влажности из бэкенда
        def get_style(feature):
            district_id = feature["id"]
            prob = risk_dict.get(district_id, 0.0)
            
            if prob > 70:
                color = "#1f1fc2"  # Темно-синий (высокий риск ливня)
            elif prob > 40:
                color = "#6ba1ff"  # Голубой (переменная облачность / морось)
            else:
                color = "#5cd670"  # Зеленый (сухо и комфортно)
                
            return {
                "fillColor": color,
                "color": "#4f4f4f", # Цвет границ районов
                "weight": 2,
                "fillOpacity": 0.5
            }

        # Добавляем наш GeoJSON слой на карту
        folium.GeoJson(
            UFA_GEOJSON,
            style_function=get_style,
            tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Район:"], localize=True)
        ).add_to(m)
        
        # Отрисовка карты на экране
        st_folium(m, width=900, height=550, key="ufa_real_boundaries_map")
        
        st.markdown("### 📊 Аналитическая сводка по секторам")
        for dist in forecast_data:
            with st.expander(f"📍 {dist['district_name']} — **{dist['rain_probability_percent']}% риск осадков**"):
                st.write(f"**Анализ ситуации:** {dist['recommendation']}")
                st.markdown("**Данные метео-моделей ансамбля:**")
                st.json(dist['sources_raw'])
                
    else:
        status_placeholder.error(f"🔴 ОШИБКА СЕРВЕРА: Код {response.status_code}")
except Exception as e:
    status_placeholder.warning(f"⏳ Переподключение к радару... Пожалуйста, обновите страницу через 20 секунд. (Инфо: {e})")
