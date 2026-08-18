import streamlit as st
import requests
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Радар Уфы — Метео-Ансамбль", layout="wide", page_icon="🌧️")

st.sidebar.title("🧭 Мониторинг алгоритма")

def update_status(step_1="⚪ Ожидание", step_2="⚪ Ожидание", step_3="⚪ Ожидание"):
    st.sidebar.markdown(f"**[Шаг 1] Подключение к спутникам:**\n{step_1}")
    st.sidebar.markdown(f"**[Шаг 2] Анализ метео-моделей:**\n{step_2}")
    st.sidebar.markdown(f"**[Шаг 3] Отрисовка карты Уфы:**\n{step_3}")

st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Контурный анализ рисков осадков по районам города")

# Укажите вашу ссылку из Render (с хвостиком /api/v1/forecast на конце!)
API_URL = "https://ufa-rain-backend.onrender-1.com/api/v1/forecast"

# ГЕО-КООРДИНАТЫ ГРАНИЦ РАЙОНОВ УФЫ (Полигоны для отрисовки)
DISTRICT_POLYGONS = {
    "chernikovka": [
        [54.795, 56.050], [54.835, 56.050], [54.845, 56.120], [54.795, 56.140]
    ],
    "sipalovo": [
        [54.755, 56.030], [54.780, 56.030], [54.780, 56.090], [54.755, 56.080]
    ],
    "center": [
        [54.710, 55.930], [54.750, 55.930], [54.750, 56.020], [54.710, 56.020]
    ],
    "dema": [
        [54.670, 55.780], [54.710, 55.780], [54.710, 55.840], [54.670, 55.840]
    ],
    "zaton": [
        [54.740, 55.860], [54.780, 55.860], [54.780, 55.920], [54.740, 55.920]
    ]
}

try:
    response = requests.get(API_URL, timeout=10)
    if response.status_code == 200:
        step_1_status = "🟢 СВЯЗЬ УСТАНОВЛЕНА"
        forecast_data = response.json()
        step_2_status = "🟢 ДАННЫЕ СКАЧАНЫ"
    else:
        step_1_status = f"🔴 ОШИБКА КОД {response.status_code}"
        step_2_status = "❌ Отменено"
        st.error("Бэкенд заснул или обновляется.")
except Exception as e:
    step_1_status = f"🔴 ОШИБКА: {str(e)}"
    step_2_status = "❌ Отменено"
    st.error("Подождите, сервер просыпается...")

if "🟢" in step_2_status:
    try:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🗺️ Интерактивная карта осадков")
            # Карта Уфы с темным стилем для контрастности радара
            m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="cartodbpositron")
            
            for dist in forecast_data:
                d_id = dist["district_id"]
                prob = dist["rain_probability_percent"]
                
                # Градация цвета в зависимости от реального риска дождя
                if prob > 70:
                    fill_color = "#2b2bd6"  # Темно-синий (ливень)
                    line_color = "#1a1a99"
                elif prob > 40:
                    fill_color = "#73a5ff"  # Голубой (морось)
                    line_color = "#4a7acc"
                else:
                    fill_color = "#70e087"  # Зеленый (сухо/солнечно)
                    line_color = "#439953"
                
                # РИСУЕМ ПОЛНОЦЕННЫЙ РАЙОННЫЙ ПОЛИГОН
                if d_id in DISTRICT_POLYGONS:
                    folium.Polygon(
                        locations=DISTRICT_POLYGONS[d_id],
                        popup=f"<b>{dist['district_name']}</b><br>Вероятность дождя: {prob}%",
                        color=line_color,
                        weight=3,
                        fill=True,
                        fill_color=fill_color,
                        fill_opacity=0.4
                    ).add_to(m)
            
            st_folium(m, width=700, height=500, key="ufa_radar_polygons")
            step_3_status = "🟢 РАДАР ОТРИСОВАН"
            
        with col2:
            st.markdown("### 📊 Метеосводка по секторам")
            for dist in forecast_data:
                with st.expander(f"📍 {dist['district_name']} — **{dist['rain_probability_percent']}%**"):
                    st.write(f"**Текущий анализ:** {dist['recommendation']}")
                    st.markdown("**Взвешенные коэффициенты моделей:**")
                    st.json(dist['sources_raw'])
                    
    except Exception as map_err:
        step_3_status = f"🔴 ОШИБКА РЕНДЕРА: {str(map_err)}"
        st.error(f"Ошибка карты: {map_err}")

    update_status(step_1_status, step_2_status, step_3_status)
