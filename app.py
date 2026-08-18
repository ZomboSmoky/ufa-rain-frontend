import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import json

st.set_page_config(page_title="Радар Уфы — Официальные Границы", layout="wide", page_icon="🌧️")

st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Высокоточный анализ рисков осадков по 7 официальным административным районам города")

# СТРОГО КОРРЕКТНЫЙ АДРЕС БЭКЕНДА:
API_URL = "https://ufa-rain-backend-1.onrender.com/api/v1/forecast"

status_placeholder = st.info("⏳ Синхронизация со спутниковыми данными...")

try:
    # Загружаем ваш официальный GeoJSON файл, скачанный с Overpass
    with open("ufa_districts.geojson", "r", encoding="utf-8") as f:
        ufa_geo_data = json.load(f)
        
    response = requests.get(API_URL, timeout=8)
    
    if response.status_code == 200:
        forecast_data = response.json()
        status_placeholder.success("🟢 Интерактивная карта успешно построена по официальным границам!")
        
        # Связываем риски осадков из бэкенда по официальным ID районов
        risk_dict = {dist["district_id"]: dist["rain_probability_percent"] for dist in forecast_data}
        
        # Центрируем карту Folium на Уфе
        m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="cartodbpositron")
        
        def style_district(feature):
            # Извлекаем ID района. Если в Overpass GeoJSON он лежит в properties, 
            # код автоматически подтянет его оттуда или из корневого ключа id.
            district_id = feature.get("id") or feature.get("properties", {}).get("id")
            prob = risk_dict.get(district_id, 0.0)
            
            # Логика смены цвета: Ливень -> Синий, Морось -> Голубой, Сухо -> Приятный Зеленый
            if prob > 70:
                color = "#1f1fc2"  
            elif prob > 40:
                color = "#6ba1ff"  
            else:
                color = "#47c95e"  
                
            return {
                "fillColor": color,
                "color": "#1a1a1a",  # Четкие темные границы
                "weight": 2.5,       # Толщина линий границ
                "fillOpacity": 0.45  # Прозрачность заливки
            }

        # Накладываем вашу детализированную OSM-сетку на карту
        folium.GeoJson(
            ufa_geo_data,
            style_function=style_district,
            tooltip=folium.GeoJsonTooltip(
                fields=["name"], 
                aliases=["Район города:"], 
                style="font-family: sans-serif; font-size: 13px; padding: 8px;"
            )
        ).add_to(m)
        
        # Новый уникальный ключ для принудительного сброса старого кэша в Streamlit
        st_folium(m, width=900, height=520, key="ufa_official_7_districts_clean_map_v1")
        
        st.markdown("### 📊 Официальная метеосводка по районам")
        for dist in forecast_data:
            with st.expander(f"📍 {dist['district_name']} — **{dist['rain_probability_percent']}% риск дождя**"):
                st.write(f"**Анализ ситуации:** {dist['recommendation']}")
                st.markdown("**Данные метео-моделей ансамбля:**")
                st.json(dist['sources_raw'])
                
    else:
        status_placeholder.error(f"🔴 СБОЙ СЕРВЕРА: Код {response.status_code}")
except Exception as e:
    status_placeholder.warning(f"⏳ Переподключение... Обновите страницу через 20 секунд. (Инфо: {e})")
