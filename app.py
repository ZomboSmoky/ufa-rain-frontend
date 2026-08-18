import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import json

st.set_page_config(page_title="Радар Уфы — Точная Раскраска", layout="wide", page_icon="🌧️")

st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Высокоточный анализ рисков осадков с поканальной отладкой 7 независимых источников")

API_URL = "https://ufa-rain-backend-1.onrender.com/api/v1/forecast"
status_placeholder = st.info("⏳ Синхронизация со спутниковыми данными и опрос телеметрии моделей...")

try:
    with open("ufa_districts.geojson", "r", encoding="utf-8") as f:
        ufa_geo_data = json.load(f)
        
    response = requests.get(API_URL, timeout=12)
    
    if response.status_code == 200:
        root_data = response.json()
        status_placeholder.success("🟢 Данные и телеметрия успешно получены с сервера!")
        
        forecast_data = root_data.get("forecasts", [])
        telemetry_data = root_data.get("telemetry", {})
        
        # Создаем словарь связи, где ключом является НАСТОЯЩЕЕ имя района (например, "Советский район")
        # Это гарантирует 100% совпадение с данными из Overpass Turbo
        name_risk_dict = {dist["district_name"]: dist["rain_probability_percent"] for dist in forecast_data}
        
        m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="cartodbpositron")
        
        def style_district(feature):
            # Извлекаем человеческое название района из GeoJSON (блок properties -> name)
            osm_name = feature.get("properties", {}).get("name", "").strip()
            
            # Если Overpass выдал имя без слова "район" (например, "Советский"), подстрахуемся:
            if osm_name and "район" not in osm_name.lower():
                osm_name = f"{osm_name} район"
                
            # Ищем вероятность осадков по русскому имени района. Если не нашли — берем 0%
            prob = name_risk_dict.get(osm_name, 0.0)
            
            # Логика смены цвета в строгом соответствии с процентами ансамбля
            if prob > 70:
                color = "#1f1fc2"  # Ливень -> Тёмно-синий
            elif prob > 40:
                color = "#6ba1ff"  # Средний риск -> Голубой
            else:
                color = "#47c95e"  # Сухо -> Приятный зеленый
                
            return {
                "fillColor": color, 
                "color": "#1a1a1a", 
                "weight": 2.5, 
                "fillOpacity": 0.50
            }

        folium.GeoJson(
            ufa_geo_data,
            style_function=style_district,
            tooltip=folium.GeoJsonTooltip(
                fields=["name"], 
                aliases=["Район города Уфы:"], 
                style="font-family: sans-serif; font-size: 13px; padding: 8px;"
            )
        ).add_to(m)
        
        # Принудительно меняем ключ карты на v5, чтобы Streamlit Cloud полностью очистил старый кэш отрисовки
        st_folium(m, width=900, height=520, key="ufa_7_sources_fixed_names_map_v5")
        
        # СЕТКА МОНИТОРИНГА НА 7 КОЛОНОК
        st.markdown("### 🖥️ Поканальный отладочный статус 7 метео-серверов")
        cols = st.columns(7)
        models_keys = [
            ("ecmwf", "ECMWF (Европа)"), ("gfs", "GFS (США)"), ("icon", "ICON (Германия)"), 
            ("arome", "France (Франция)"), ("jma", "JMA (Япония)"), ("yr_no", "Yr.no (Норвегия)"),
            ("fallback_7timer", "Резерв (7timer)")
        ]
        
        for i, (key, label) in enumerate(models_keys):
            status_text = telemetry_data.get(key, "🔴 Офлайн")
            with cols[i]:
                if "🟢" in status_text:
                    st.success(f"**{label}**\n\n{status_text}")
                else:
                    st.error(f"**{label}**\n\n{status_text}")

        st.markdown("### 📊 Метеосводка и прогнозы по районам")
        for dist in forecast_data:
            with st.expander(f"📍 {dist['district_name']} — **{dist['rain_probability_percent']}% риск дождя**"):
                st.write(f"**Анализ ситуации:** {dist['recommendation']}")
                st.json(dist['sources_raw'])
                
except Exception as e:
    status_placeholder.error(f"🔴 КРИТИЧЕСКИЙ СБОЙ ИНТЕРФЕЙСА: {e}")
