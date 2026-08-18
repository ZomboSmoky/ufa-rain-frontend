import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import json

st.set_page_config(page_title="Радар Уфы — Телеметрия", layout="wide", page_icon="🌧️")

st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Высокоточный анализ рисков осадков с поканальной отладкой источников")

API_URL = "https://ufa-rain-backend-1.onrender.com/api/v1/forecast"
status_placeholder = st.info("⏳ Синхронизация со спутниковыми данными и опрос телеметрии моделей...")

try:
    with open("ufa_districts.geojson", "r", encoding="utf-8") as f:
        ufa_geo_data = json.load(f)
        
    response = requests.get(API_URL, timeout=12)
    
    if response.status_code == 200:
        root_data = response.json()
        status_placeholder.success("🟢 Телеметрия успешно получена с сервера бэкенда!")
        
        # Безопасно достаем списки прогнозов и телеметрии из корня JSON
        forecast_data = root_data.get("forecasts", [])
        telemetry_data = root_data.get("telemetry", {})
        
        risk_dict = {dist["district_id"]: dist["rain_probability_percent"] for dist in forecast_data}
        
        m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="cartodbpositron")
        
        def style_district(feature):
            district_id = feature.get("id") or feature.get("properties", {}).get("id")
            prob = risk_dict.get(district_id, 0.0)
            if prob > 70: color = "#1f1fc2"
            elif prob > 40: color = "#6ba1ff"
            else: color = "#47c95e"
            return {"fillColor": color, "color": "#1a1a1a", "weight": 2.5, "fillOpacity": 0.45}

        folium.GeoJson(
            ufa_geo_data,
            style_function=style_district,
            tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Район:"], style="font-family: sans-serif; font-size: 13px;")
        ).add_to(m)
        
        st_folium(m, width=900, height=520, key="ufa_root_fixed_map_v3")
        
        # ОТЛАДОЧНЫЙ МОНИТОРИНГ ИСТОЧНИКОВ
        st.markdown("### 🖥️ Поканальный отладочный статус метео-серверов")
        cols = st.columns(6)
        models_keys = [
            ("ecmwf", "ECMWF (Европа)"), ("gfs", "GFS (США)"), ("icon", "ICON (Германия)"), 
            ("arome", "France (Франция)"), ("jma", "JMA (Япония)"), ("yr_no", "Yr.no (Норвегия)")
        ]
        
        for i, (key, label) in enumerate(models_keys):
            status_text = telemetry_data.get(key, "🔴 Данные отсутствуют")
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
                
    else:
        status_placeholder.error(f"🔴 СБОЙ СЕРВЕРА БЭКЕНДА: Код {response.status_code}")
except Exception as e:
    status_placeholder.warning(f"⏳ Переподключение... Обновите страницу. (Техническое инфо: {e})")
