import streamlit as st
import requests
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Дождь в Уфе — Метео-Ансамбль", layout="wide", page_icon="🌧️")

# --- ИНДИКАТОР ШАГОВ В БОКОВОЙ ПАНЕЛИ ---
st.sidebar.title("🧭 Мониторинг алгоритма")

def update_status(step_1="⚪ Ожидание", step_2="⚪ Ожидание", step_3="⚪ Ожидание"):
    st.sidebar.markdown(f"**[Шаг 1] Подключение к бэкенду:**\n{step_1}")
    st.sidebar.markdown(f"**[Шаг 2] Расчёт ансамбля по районам:**\n{step_2}")
    st.sidebar.markdown(f"**[Шаг 3] Визуализация карты Folium:**\n{step_3}")

# Начальное состояние индикаторов
step_1_status = "⏳ Запрос к серверу..."
step_2_status = "⚪ Ожидание Шага 1"
step_3_status = "⚪ Ожидание Шага 2"

# Основные заголовки
st.title("🌧️ Система микролокального прогноза дождей в Уфе")
st.subheader("Анализ данных Яндекс.Погода, AccuWeather и Apple WeatherKit")

# Убедитесь, что здесь указана ВАША ссылка с Render (обязательно с /api/v1/forecast на конце!)
API_URL = "https://ufa-rain-backend-1.onrender.com"

DISTRICT_COORDS = {
    "chernikovka": [54.8122, 56.0915],
    "sipalovo": [54.7678, 56.0621],
    "center": [54.7348, 55.9579],
    "dema": [54.6983, 55.8115],
    "zaton": [54.7621, 55.8944]
}

try:
    # --- ВЫПОЛНЕНИЕ ШАГА 1 ---
    response = requests.get(API_URL, timeout=10)
    
    if response.status_code == 200:
        step_1_status = "🟢 УСПЕШНО (Код 200)"
        step_2_status = "⏳ Чтение JSON данных..."
        
        forecast_data = response.json()
        
        # --- ВЫПОЛНЕНИЕ ШАГА 2 ---
        if forecast_data and isinstance(forecast_data, list):
            step_2_status = f"🟢 УСПЕШНО (Обработано районов: {len(forecast_data)})"
            step_3_status = "⏳ Отрисовка карты..."
        else:
            step_2_status = "🔴 ОШИБКА: Сервер вернул пустой или неверный массив данных"
            step_3_status = "❌ Отменено"
            
    else:
        step_1_status = f"🔴 ОШИБКА: Код {response.status_code} (Detail Not Found или сон)"
        step_2_status = "❌ Отменено"
        step_3_status = "❌ Отменено"
        st.error(f"Бэкенд вернул код ошибки: {response.status_code}. Проверьте хвостик ссылки.")

except Exception as e:
    step_1_status = f"🔴 ОШИБКА ПОДКЛЮЧЕНИЯ: {str(e)}"
    step_2_status = "❌ Отменено"
    step_3_status = "❌ Отменено"
    st.error("Не удалось достучаться до сервера. Скорее всего, он спит. Подождите 30 секунд и обновите страницу.")

# Если Шаг 2 пройден успешно, пытаемся нарисовать карту (Шаг 3)
if "🟢" in step_2_status:
    try:
        col1, col2 = st.columns(2)
        
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
            
            st_folium(m, width=700, height=500, key="ufa_map_v2")
            step_3_status = "🟢 УСПЕШНО (Карта выведена)"
            
        with col2:
            st.markdown("### 📊 Точные метрики")
            for dist in forecast_data:
                with st.expander(f"📍 {dist['district_name']} — **{dist['rain_probability_percent']}%**"):
                    st.write(f"**Рекомендация:** {dist['recommendation']}")
                    st.json(dist['sources_raw'])
                    
    except Exception as map_err:
        step_3_status = f"🔴 ОШИБКА КАРТЫ: {str(map_err)}"
        st.error(f"Произошел сбой при генерации графической карты: {map_err}")

# Отрисовываем финальные статусы в боковой панели
update_status(step_1_status, step_2_status, step_3_status)
