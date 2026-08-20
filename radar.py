import streamlit as st
import requests, folium, json, time
from datetime import datetime
from streamlit_folium import st_folium

st.set_page_config(page_title="Радар Уфы", layout="wide", page_icon="🌧️")
st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Серверная архитектура: Прямые запросы через Python Requests (forecast_days)")

# --- ЗАЩИЩЕННЫЙ СБОРЩИК БАЗОВОГО ЭНДПОИНТА ---
SUB_PREFIX = "a" + "p" + "i"
BASE_DOMAIN = "open-meteo.com"
VALID_OPEN_METEO_URL = f"https://{SUB_PREFIX}.{BASE_DOMAIN}/v1/forecast"

# Координатная сетка районов Уфы
DISTRICT_COORDS = [
    {"id": "Д", "name": "Дёмский район", "lat": 54.693, "lon": 55.811, "center": [54.685, 55.820]},
    {"id": "Кл", "name": "Калининский район", "lat": 54.831, "lon": 56.126, "center": [54.810, 56.120]},
    {"id": "Кр", "name": "Кировский район", "lat": 54.701, "lon": 55.992, "center": [54.670, 56.030]},
    {"id": "Л", "name": "Ленинский район", "lat": 54.752, "lon": 55.894, "center": [54.760, 55.850]},
    {"id": "О", "name": "Октябрьский район", "lat": 54.771, "lon": 56.031, "center": [54.770, 56.040]},
    {"id": "Орд", "name": "Орджоникидзевский район", "lat": 54.819, "lon": 56.095, "center": [54.825, 56.070]},
    {"id": "С", "name": "Советский район", "lat": 54.739, "lon": 55.975, "center": [54.738, 55.980]}
]

# Сводная таблица соответствия внутренних имен моделей в API Open-Meteo
OM_MAPPING = {
    "ecmwf": "ecmwf_ifs", 
    "gfs": "gfs_seamless", 
    "icon": "icon_seamless",
    "arome": "meteofrance_arome", 
    "jma": "jma_seamless", 
    "yr_no": "yr_yr",
    "cma_china": "cma_graphes", 
    "imd_india": "imd_gfs"
}

ALL_MODELS = list(OM_MAPPING.keys())
BASE_WEIGHTS = {m: 1.0 / len(ALL_MODELS) for m in ALL_MODELS}

# Стандартные браузерные заголовки для серверных запросов
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

def execute_server_request(lat, lon, model_key):
    """Выполняет изолированный запрос к API Open-Meteo для конкретного района и модели"""
    sys_model_name = OM_MAPPING.get(model_key)
    # Используем forecast_days=1 вместо проблемных календарных дат start_date/end_date
    url = f"{VALID_OPEN_METEO_URL}?latitude={lat}&longitude={lon}&hourly=precipitation_probability&models={sys_model_name}&forecast_days=1&timezone=auto"
    
    try:
        time.sleep(0.02)  # Небольшая пауза для предотвращения спам-бана по частоте
        res = requests.get(url, headers=HEADERS, timeout=6.0)
        
        if res.status_code != 200:
            return None, f"🔴 Ошибка HTTP {res.status_code}"
            
        if not res.text.strip():
            return None, "🔴 Пустой ответ от сервера"
            
        js = res.json()
        probs = js.get("hourly", {}).get(f"precipitation_probability_{sys_model_name}", [])
        
        if probs and len(probs) > 0:
            # Извлекаем значение для текущего часа
            current_hour = datetime.now().hour
            current_prob = probs[min(current_hour, len(probs) - 1)]
            return int(current_prob), "🟢 Достоверно"
            
        return None, "🔴 Нет данных по осадкам в JSON"
        
    except Exception as e:
        return None, f"🔴 Ошибка сети: {str(e)}"

def build_radar_intelligence():
    """Собирает метеоданные по всем районам и вычисляет взвешенный индекс осадков"""
    forecast_results = []
    server_matrix = {m: {d["id"]: "🔴" for d in DISTRICT_COORDS} for m in ALL_MODELS}
    
    for d in DISTRICT_COORDS:
        probs = {}
        statuses = {}
        is_alive = {}
        
        # Опрашиваем метеомодели по очереди через серверный бэкенд
        for m_id in ALL_MODELS:
            val, msg = execute_server_request(d["lat"], d["lon"], m_id)
            statuses[m_id] = msg
            if val is not None:
                probs[m_id] = val
                is_alive[m_id] = True
                server_matrix[m_id][d["id"]] = "🟢"
            else:
                probs[m_id] = 0
                is_alive[m_id] = False

        live_models = [m for m in ALL_MODELS if is_alive[m]]
        src_disp = {}
        
        if not live_models:
            final_p = 0
            for m in ALL_MODELS: 
                src_disp[m] = f"Прогноз: 0% | Вес: 0.0% | Статус: {statuses[m]}"
        else:
            # Пересчитываем веса динамически в зависимости от того, какие серверы ответили
            sum_base_w = sum(BASE_WEIGHTS[m] for m in live_models)
            final_p = min(max(int(sum((BASE_WEIGHTS[m] / sum_base_w) * probs[m] for m in live_models)), 0), 100)
            
            for m in ALL_MODELS:
                if is_alive[m]:
                    calc_w = round((BASE_WEIGHTS[m] / sum_base_w * 100), 1)
                    src_disp[m] = f"Прогноз: {probs[m]}% | Вес: {calc_w}% | Статус: {statuses[m]}"
                else:
                    src_disp[m] = f"Прогноз: 0% | Вес: 0.0% | Статус: {statuses[m]}"
                    
        forecast_results.append({
            "name": d["name"], 
            "center": d["center"], 
            "prob": final_p, 
            "src": src_disp
        })
        
    return forecast_results, server_matrix

# --- СБОР ДАННЫХ НА СЕРВЕРЕ ---
fdata, matrix_data = build_radar_intelligence()
r_dict = {dist["name"]: dist["prob"] for dist in fdata}

# --- ОТРИСОВКА ИНТЕРФЕЙСА FOLIUM ---
with open("ufa_districts.geojson", "r", encoding="utf-8") as f:
    ufa_geo = json.load(f)

m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="OpenStreetMap")

def style_d(feat):
    name = feat.get("properties", {}).get("name", "").strip()
    if name and "район" not in name.lower(): 
        name = name + " район"
    p = r_dict.get(name, 0)
    
    # Плавное цветовое кодирование полигонов районов на сервере
    color = "#1d4ed8" if p > 75 else ("#3b82f6" if p > 45 else ("#facc15" if p > 15 else "#16a34a"))
    return {"fillColor": color, "color": "#0f172a", "weight": 2.5, "fillOpacity": 0.3}

folium.GeoJson(
    ufa_geo, 
    style_function=style_d, 
    tooltip=folium.GeoJsonTooltip(fields=["name"])
).add_to(m)

# Наносим статические текстовые маркеры с процентами осадков
for dist in fdata:
    folium.Marker(
        location=dist["center"],
        icon=folium.DivIcon(
            icon_size=(60, 40), icon_anchor=(30, 20),
            html=f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; font-weight: 900; color: #0f172a; text-shadow: 2px 2px 0px #fff, -2px -2px 0px #fff; text-align: center; width: 100%;">{dist['prob']}%</div>"""
        )
    ).add_to(m)

# Родной и безопасный вывод карты через библиотеку streamlit_folium
st_folium(m, width=950, height=530, key="ufa_pure_python_radar")

# --- МЕТЕОСВОДКА STREAMLIT ---
st.markdown("### 📊 Аналитическая метеосводка по районам")
for dist in fdata:
    with st.expander(f"📍 {dist['name']} — **{dist['prob']}% общий риск осадков**"):
        st.json(dist['src'])

st.markdown("---")
st.markdown("### 🖥️ Системная матрица ответов погодных ядер")
cols = st.columns(8)
for i, m_id in enumerate(ALL_MODELS):
    m_statuses = matrix_data.get(m_id, {})
    status_line = " ".join([f"{rid}:{m_statuses.get(rid, '🔴')}" for rid in ["Д", "Кл", "Кр", "Л", "О", "Орд", "С"]])
    with cols[i]:
        st.metric(label=m_id.upper(), value="ONLINE" if "🔴" not in m_statuses.values() else "PARTIAL", delta=status_line)
