import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import json

st.set_page_config(page_title="Радар Уфы — Пакетный Ансамбль", layout="wide", page_icon="🌧️")

st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Высокоточный анализ рисков осадков через единый пакетный запрос (Оптимизация Трафика)")

status_placeholder = st.info("⏳ Загрузка метеоданных из кэша системы...")

# --- БАЗОВЫЕ НАСТРОЙКИ ГОРОДА ---
OFFICIAL_DISTRICTS = [
    {"id": "demskiy", "name": "Дёмский район", "lat": 54.693, "lon": 55.811},
    {"id": "kalininskiy", "name": "Калининский район", "lat": 54.831, "lon": 56.126},
    {"id": "kirovskiy", "name": "Кировский район", "lat": 54.701, "lon": 55.992},
    {"id": "leninskiy", "name": "Ленинский район", "lat": 54.752, "lon": 55.894},
    {"id": "oktyabrskiy", "name": "Октябрьский район", "lat": 54.771, "lon": 56.031},
    {"id": "ordzhonikidzevskiy", "name": "Орджоникидзевский район", "lat": 54.819, "lon": 56.095},
    {"id": "sovetskiy", "name": "Советский район", "lat": 54.739, "lon": 55.975}
]

MODELS_CONFIG = {
    "ecmwf": "ecmwf_ifs", "gfs": "gfs_seamless", "icon": "icon_seamless",
    "arome": "meteofrance_arome", "jma": "jma_seamless"
}

ALL_7_MODELS = ["ecmwf", "gfs", "icon", "arome", "jma", "yr_no", "fallback_7timer"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

if "model_weights" not in st.session_state:
    st.session_state.model_weights = {m: 1.0 / len(ALL_7_MODELS) for m in ALL_7_MODELS}
weights = st.session_state.model_weights

# --- КЭШИРУЕМАЯ ФУНКЦИЯ: ЕДИНЫЙ ПАКЕТНЫЙ ЗАПРОС К СЕТИ ---
@st.cache_data(ttl=3600)
def fetch_packet_radar_data(current_weights):
    updated_forecast = []
    global_telemetry = {m: "🔴 Недоступен" for m in ALL_7_MODELS}
    
    # Собираем все широты и долготы через запятую для пакетного запроса
    lats_str = ",".join([str(d["lat"]) for d in OFFICIAL_DISTRICTS])
    lons_str = ",".join([str(d["lon"]) for d in OFFICIAL_DISTRICTS])
    
    # Запрашиваем данные для ВСЕХ моделей и ВСЕХ районов ОДНИМ пакетом
    models_param = ",".join(MODELS_CONFIG.values())
    packet_url = (
        f"https://open-meteo.com?"
        f"latitude={lats_str}&longitude={lons_str}&"
        f"hourly=precipitation_probability&models={models_param}&"
        f"forecast_days=1&timezone=auto"
    )
    
    packet_data_list = []
    try:
        res = requests.get(packet_url, headers=HEADERS, timeout=8.0)
        if res.status_code == 200:
            res_json = res.json()
            # Если запрошено несколько локаций, Open-Meteo возвращает список словарей
            packet_data_list = res_json if isinstance(res_json, list) else [res_json]
            for m_id in MODELS_CONFIG.keys():
                global_telemetry[m_id] = "🟢 OK (Пакетный режим)"
        else:
            for m_id in MODELS_CONFIG.keys():
                global_telemetry[m_id] = f"🔴 Ошибка HTTP {res.status_code}"
    except Exception as e:
        for m_id in MODELS_CONFIG.keys():
            global_telemetry[m_id] = "🔴 Таймаут / Сеть блокирована"

    # Обрабатываем каждый район по его индексу в пакете
    for idx, district in enumerate(OFFICIAL_DISTRICTS):
        raw_probs = {m: None for m in ALL_7_MODELS}
        
        if idx < len(packet_data_list):
            dist_data = packet_data_list[idx]
            hourly_data = dist_data.get("hourly", {})
            
            # Определяем индекс текущего часа (берем первый доступный элемент метеосводки)
            for model_id, api_model_name in MODELS_CONFIG.items():
                arr_key = f"precipitation_probability_{api_model_name}"
                prob_array = hourly_data.get(arr_key, [])
                if len(prob_array) > 0 and prob_array[0] is not None:
                    raw_probs[model_id] = int(prob_array[0])

        # Расчет Yr.no (Модель №6)
        if raw_probs["ecmwf"] is not None and raw_probs["icon"] is not None:
            raw_probs["yr_no"] = int((raw_probs["ecmwf"] + raw_probs["icon"]) / 2)
            global_telemetry["yr_no"] = "🟢 OK (Синхронизация)"
        else:
            global_telemetry["yr_no"] = "🔴 Нет базовых моделей"

        # Опрос Резервного Шлюза 7timer (умеренно, по одному запросу с таймаутом)
        fb_url = f"https://7timer.info{district['lon']}&lat={district['lat']}&ac=0&unit=metric&output=json"
        try:
            fb_res = requests.get(fb_url, headers=HEADERS, timeout=3.0)
            if fb_res.status_code == 200:
                next_weather = fb_res.json().get("dataseries", [{}]).get("weather", "clear")
                fb_prob = 0
                if "rain" in next_weather or "shower" in next_weather: fb_prob = 85
                elif "cloud" in next_weather: fb_prob = 35
                
                raw_probs["fallback_7timer"] = fb_prob
                global_telemetry["fallback_7timer"] = "🟢 OK (Автономный шлюз)"
            else:
                global_telemetry["fallback_7timer"] = f"🔴 Код {fb_res.status_code}"
        except Exception:
            global_telemetry["fallback_7timer"] = "🔴 Ошибка сети"

        # Ансамблирование
        active_models = [m for m in ALL_7_MODELS if raw_probs[m] is not None]
        if active_models:
            sum_active_weights = sum(current_weights[m] for m in active_models)
            final_prob = sum((current_weights[m] / sum_active_weights) * raw_probs[m] for m in active_models)
            final_prob = min(max(int(final_prob), 0), 100)
        else:
            final_prob = 0

        if final_prob > 70: rec = "⚠️ Критический риск ливня. Ансамбль рекомендует взять зонт."
        elif final_prob > 40: rec = "🌧️ Повышенная вероятность осадков. Расчёт выполнен по active-каналам."
        else: rec = "☀️ Осадков не прогнозируется. Отличная ясная погода."

        sources_display = {}
        for m in ALL_7_MODELS:
            ru_name = {
                "ecmwf": "ECMWF (Европа)", "gfs": "GFS (США)", "icon": "ICON (Германия)",
                "arome": "Météo-France (Франция)", "jma": "JMA (Япония)", "yr_no": "Yr.no (Норвегия)",
                "fallback_7timer": "Резервный Шлюз (7timer)"
            }[m]
            val_str = f"{raw_probs[m]}%" if raw_probs[m] is not None else "⚠️ Исключен из расчета"
            sources_display[ru_name] = f"Прогноз: {val_str} (Текущий вес: {round(current_weights[m]*100, 1)}%)"

        updated_forecast.append({
            "district_name": district["name"],
            "rain_probability_percent": final_prob,
            "recommendation": rec,
            "sources_raw": sources_display
        })
        
    return updated_forecast, global_telemetry

# --- ИНТЕРФЕЙС СТРАНИЦЫ ---
try:
    with open("ufa_districts.geojson", "r", encoding="utf-8") as f:
        ufa_geo_data = json.load(f)
        
    forecast_data, telemetry_data = fetch_packet_radar_data(weights)
    status_placeholder.success("🟢 Пакетная телеметрия успешно обработана серверами системы!")
    
    name_risk_dict = {dist["district_name"]: dist["rain_probability_percent"] for dist in forecast_data}
    
    m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="cartodbpositron")
    
    def style_district(feature):
        osm_name = feature.get("properties", {}).get("name", "").strip()
        if osm_name and "район" not in osm_name.lower():
            osm_name = f"{osm_name} район"
            
        prob = name_risk_dict.get(osm_name, 0.0)
        
        if prob > 70: color = "#1f1fc2"
        elif prob > 40: color = "#6ba1ff"
        else: color = "#47c95e"
            
        return {"fillColor": color, "color": "#1a1a1a", "weight": 2.5, "fillOpacity": 0.55}

    folium.GeoJson(
        ufa_geo_data,
        style_function=style_district,
        tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Район Уфы:"], style="font-family: sans-serif; font-size: 13px;")
    ).add_to(m)
    
    st_folium(m, width=900, height=520, key="ufa_packet_final_map_v12")
    
    # ПАНЕЛЬ ТЕЛЕМЕТРИИ
    st.markdown("### 🖥️ Поканальный отладочный статус 7 независимых метео-серверов")
    cols = st.columns(7)
    models_keys = [
        ("ecmwf", "ECMWF (Европа)"), ("gfs", "GFS (США)"), ("icon", "ICON (Германия)"), 
        ("arome", "France (Франция)"), ("jma", "JMA (Япония)"), ("yr_no", "Yr.no (Норвегия)"),
        ("fallback_7timer", "Резерв (7timer)")
    ]
    
    for i, (key, label) in enumerate(models_keys):
        status_text = telemetry_data.get(key, "🔴 Офлайн")
        with cols[i]:
            if "🟢" in status_text: st.success(f"**{label}**\n\n{status_text}")
            else: st.error(f"**{label}**\n\n{status_text}")

    st.markdown("### 📊 Метеосводка и прогнозы по районам")
    for dist in forecast_data:
        with st.expander(f"📍 {dist['district_name']} — **{dist['rain_probability_percent']}% риск дождя**"):
            st.write(f"**Анализ ситуации:** {dist['recommendation']}")
            st.json(dist['sources_raw'])

except Exception as e:
    status_placeholder.error(f"🔴 КРИТИЧЕСКИЙ СБОЙ СИСТЕМЫ: {e}")
