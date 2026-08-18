import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import json

st.set_page_config(page_title="Радар Уфы — Реальные Районы", layout="wide", page_icon="🌧️")

st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Высокоточный анализ рисков осадков по официальным границам районов города")

# АДРЕС УКАЗАН ПОЛНОСТЬЮ И СТРОГО КОРРЕКТНО:
API_URL = "https://ufa-rain-backend-1.onrender.com/api/v1/forecast"

status_placeholder = st.info("⏳ Синхронизация со спутниковыми данными...")

try:
    # Загружаем реальные асимметричные границы районов Уфы
    with open("ufa_districts.geojson", "r", encoding="utf-8") as f:
        ufa_geo_data = json.load(f)
        
    response = requests.get(API_URL, timeout=8)
    
    if response.status_code == 200:
        forecast_data = response.json()
        status_placeholder.success("🟢 Интерактивная карта успешно построена по реальным контурам Уфы!")
        
        risk_dict = {dist["district_id"]: dist["rain_probability_percent"] for dist in forecast_data}
        
        m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="cartodbpositron")
        
        def style_district(feature):
            district_id = feature["id"]
            prob = risk_dict.get(district_id, 0.0)
            
            if prob > 70:
                color = "#1f1fc2"  
            elif prob > 40:
                color = "#6ba1ff"  
            else:
                color = "#47c95e"  
                
            return {
                "fillColor": color,
                "color": "#1a1a1a",  
                "weight": 3,         
                "fillOpacity": 0.45  
            }

        # Накладываем выверенную GeoJSON сетку
        folium.GeoJson(
            ufa_geo_data,
            style_function=style_district,
            tooltip=folium.GeoJsonTooltip(
                fields=["name"], 
                aliases=["Сектор города:"], 
                style="font-family: sans-serif; font-size: 13px; padding: 8px;"
            )
        ).add_to(m)
        
        # Новый уникальный ключ карты для полного сброса круглого кэша
        st_folium(m, width=900, height=520, key="ufa_industrial_geojson_v1")
        
        st.markdown("### 📊 Метеосводка по секторам")
        for dist in forecast_data:
            with st.expander(f"📍 {dist['district_name']} — **{dist['rain_probability_percent']}% риск дождя**"):
                st.write(f"**Анализ ситуации:** {dist['recommendation']}")
                st.markdown("**Данные метео-моделей ансамбля:**")
                st.json(dist['sources_raw'])
                
    else:
        status_placeholder.error(f"🔴 СБОЙ СЕРВЕРА: Код {response.status_code}")
except Exception as e:
    status_placeholder.warning(f"⏳ Переподключение... Пожалуйста, обновите страницу через 20 секунд. (Инфо: {e})")
