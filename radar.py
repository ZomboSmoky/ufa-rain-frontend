# ==========================================
# ЧАСТЬ 1: Конфигурация, Стили и Модели данных
# Длина блока: ~115 строк
# ==========================================
import streamlit as st
import requests
import folium
import json
from datetime import datetime, timedelta
from urllib.parse import urlencode, urljoin
from streamlit_folium import st_folium
from concurrent.futures import ThreadPoolExecutor

# ТОТАЛЬНЫЙ ИНСТАГРАМ-СТИЛЬ: Шрифты, адаптивная сетка постов, кастомные иконки
INSTAGRAM_STYLE = """
<style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 1rem !important;
    }
    
    /* Stories лента */
    .stories-feed {
        display: flex;
        overflow-x: auto;
        padding: 10px 5px;
        gap: 22px;
        white-space: nowrap;
        scrollbar-width: none;
    }
    .stories-feed::-webkit-scrollbar { display: none; }
    
    .story-card {
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        width: 82px;
        text-align: center;
    }
    
    .story-ring {
        width: 70px;
        height: 70px;
        border-radius: 50%;
        padding: 3px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: transform 0.2s ease;
    }
    .story-ring:hover { transform: scale(1.06); }
    
    .ring-danger { background: linear-gradient(45deg, #f09433 0%, #e6683c 25%, #dc2743 50%, #cc2366 75%, #bc1888 100%); }
    .ring-warning { background: linear-gradient(45deg, #00f2fe 0%, #4facfe 100%); }
    .ring-dry { background: #e1e1e1; }
    
    .story-body {
        width: 100%;
        height: 100%;
        background: #ffffff;
        border-radius: 50%;
        border: 2px solid #ffffff;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .story-emoji { font-size: 18px; line-height: 1; }
    .story-pct { font-weight: 800; font-size: 11px; color: #262626; margin-top: 2px; }
    .story-label { font-family: -apple-system, sans-serif; font-size: 11px; font-weight: 600; margin-top: 6px; color: #262626; }
    
    /* Instagram-Посты (Сводка районов) */
    .insta-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 20px;
        margin-top: 20px;
    }
    .insta-post {
        background: #ffffff;
        border: 1px solid #dbdbdb;
        border-radius: 12px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        color: #262626;
        overflow: hidden;
    }
    .post-header {
        display: flex;
        align-items: center;
        padding: 12px;
        border-bottom: 1px solid #efefef;
    }
    .post-avatar {
        width: 32px; height: 32px; border-radius: 50%; background: #f1f5f9;
        display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px;
        border: 1px solid #dbdbdb; margin-right: 10px;
    }
    .post-username { font-weight: 600; font-size: 13px; }
    .post-image-alt {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        padding: 24px; text-align: center; border-bottom: 1px solid #efefef;
    }
    .post-temp { font-size: 38px; font-weight: 800; color: #1e293b; }
    .post-feel { font-size: 12px; color: #64748b; font-weight: 500; }
    .post-content { padding: 12px; font-size: 13px; line-height: 1.5; }
    .post-likes { font-weight: 700; margin-bottom: 6px; font-size: 13px; }
    .post-metrics div { margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }
    
    /* Блок системной матрицы */
    .highlight-badge {
        background: #f8f9fa; border: 1px solid #e1e1e1; border-radius: 12px; padding: 12px;
    }
</style>
"""

st.set_page_config(page_title="WeatherGram Ufa", layout="wide", page_icon="📸")
st.markdown(INSTAGRAM_STYLE, unsafe_allow_html=True)
st.title("📸 WeatherGram Ufa")
st.caption("Полнофункциональный погодный инстаграм-глянец радара Уфы")

DISTRICT_COORDS = [
    {"id": "Дем", "name": "Дёмский район", "lat": 54.693, "lon": 55.811, "center": [54.685, 55.820]},
    {"id": "Kал", "name": "Калининский район", "lat": 54.831, "lon": 56.126, "center": [54.810, 56.120]},
    {"id": "Кир", "name": "Кировский район", "lat": 54.701, "lon": 55.992, "center": [54.670, 56.030]},
    {"id": "Лен", "name": "Ленинский район", "lat": 54.752, "lon": 55.894, "center": [54.760, 55.850]},
    {"id": "Окт", "name": "Октябрьский район", "lat": 54.771, "lon": 56.031, "center": [54.770, 56.040]},
    {"id": "Орд", "name": "Орджоникидзевский район", "lat": 54.819, "lon": 56.095, "center": [54.825, 56.070]},
    {"id": "Сов", "name": "Советский район", "lat": 54.739, "lon": 55.975, "center": [54.738, 55.980]}
]

ALL_MODELS = ["ecmwf", "gfs", "icon", "jma"]
BASE_WEIGHTS = {m: 1.0 / len(ALL_MODELS) for m in ALL_MODELS}
HEADERS = {"User-Agent": "Mozilla/5.0 RadarUfa/1.0", "Accept": "application/json"}
# ==========================================
# ЧАСТЬ 2: Защищенный генератор URL (urllib)
# Длина блока: ~65 строк
# ==========================================
def get_model_url(lat, lon, model_key):
    base_params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "UTC",
        "forecast_days": 2,
    }
    
    # Базовые почасовые метрики, запрашиваемые у всех ядер
    hourly_metrics = [
        "temperature_2m", "apparent_temperature", "weather_code",
        "relative_humidity_2m", "surface_pressure", "wind_speed_10m", "wind_gusts_10m"
    ]
    
    # Разделение логики точек доступа API и специфичных для моделей параметров
    if model_key == "jma":
        endpoint = "https://open-meteo.com"
        hourly_metrics.append("precipitation")
    else:
        endpoint = "https://open-meteo.com"
        hourly_metrics.append("precipitation_probability")
        
        if model_key == "ecmwf":
            base_params["models"] = "ecmwf_ifs"
        elif model_key == "gfs":
            base_params["models"] = "gfs_seamless"
        elif model_key == "icon":
            base_params["models"] = "icon_seamless"
            
    base_params["hourly"] = ",".join(hourly_metrics)
    
    # ЗАЩИТА: Безопасная сборка URL-строки через urlencode без ручной конкатенации
    query_string = urlencode(base_params)
    return f"{endpoint}?{query_string}"

@st.cache_data(ttl=300, show_spinner=False)
def fetch_single_api_node(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=7.0)
        if res.status_code == 200 and res.text.strip(): 
            return res.json(), "🟢 Достоверно"
        return None, f"🔴 Ошибка HTTP {res.status_code}"
    except Exception: 
        return None, "🔴 Ошибка сети"

def fetch_url_worker(task):
    dist_id, m_id, url = task
    json_body, status_msg = fetch_single_api_node(url)
    return dist_id, m_id, json_body, status_msg

def fetch_all_data_parallel():
    tasks = []
    for d in DISTRICT_COORDS:
        for m in ALL_MODELS: 
            tasks.append((d["id"], m, get_model_url(d["lat"], d["lon"], m)))
    raw_responses = []
    with ThreadPoolExecutor(max_workers=16) as executor:
        results = executor.map(fetch_url_worker, tasks)
        for r in results: 
            raw_responses.append(r)
    structured_data = {d["id"]: {} for d in DISTRICT_COORDS}
    for dist_id, m_id, json_body, status_msg in raw_responses:
        structured_data[dist_id][m_id] = {"json": json_body, "msg": status_msg}
    return structured_data
# ==========================================
# ЧАСТЬ 3: Аналитическая обработка ответов
# Длина блока: ~125 строк
# ==========================================
def build_radar_intelligence():
    network_package = fetch_all_data_parallel()
    forecast_results = []
    server_matrix = {m: {d["id"]: "🔴" for d in DISTRICT_COORDS} for m in ALL_MODELS}
    
    # Вычисляем текущий час по Уфе (UTC+5), а затем переводим в UTC для сверки с API
    ufa_now = datetime.utcnow() + timedelta(hours=5)
    target_utc_time = ufa_now - timedelta(hours=5)
    target_hour_str = target_utc_time.strftime("%Y-%m-%dT%H:00")
    
    for d in DISTRICT_COORDS:
        probs = {m: 0 for m in ALL_MODELS}
        statuses = {m: "🔴 Нет данных" for m in ALL_MODELS}
        is_alive = {m: False for m in ALL_MODELS}
        
        temps, feels, wmos, humidities, pressures, winds, gusts = [], [], [], [], [], [], []
        dist_bundle = network_package.get(d["id"], {})
        
        for m_id in ALL_MODELS:
            node = dist_bundle.get(m_id, {"json": None, "msg": "🔴 Ошибка"})
            js, msg = node["json"], node["msg"]
            
            if js and "hourly" in js:
                hourly_data = js["hourly"]
                time_arr = hourly_data.get("time", [])
                
                idx = -1
                if target_hour_str in time_arr:
                    idx = time_arr.index(target_hour_str)
                else:
                    idx = datetime.utcnow().hour
                
                if idx != -1 and idx < len(time_arr):
                    try:
                        if hourly_data.get("temperature_2m") and hourly_data["temperature_2m"][idx] is not None: 
                            temps.append(float(hourly_data["temperature_2m"][idx]))
                        if hourly_data.get("apparent_temperature") and hourly_data["apparent_temperature"][idx] is not None: 
                            feels.append(float(hourly_data["apparent_temperature"][idx]))
                        if hourly_data.get("weather_code") and hourly_data["weather_code"][idx] is not None: 
                            wmos.append(int(hourly_data["weather_code"][idx]))
                        if hourly_data.get("relative_humidity_2m") and hourly_data["relative_humidity_2m"][idx] is not None: 
                            humidities.append(int(hourly_data["relative_humidity_2m"][idx]))
                        if hourly_data.get("surface_pressure") and hourly_data["surface_pressure"][idx] is not None: 
                            pressures.append(float(hourly_data["surface_pressure"][idx]))
                        if hourly_data.get("wind_speed_10m") and hourly_data["wind_speed_10m"][idx] is not None: 
                            winds.append(float(hourly_data["wind_speed_10m"][idx]))
                        if hourly_data.get("wind_gusts_10m") and hourly_data["wind_gusts_10m"][idx] is not None: 
                            gusts.append(float(hourly_data["wind_gusts_10m"][idx]))
                    except (IndexError, TypeError, ValueError): pass
                
                # Поиск ключей осадков
                matching_keys = [k for k in hourly_data.keys() if "precipitation" in k]
                if matching_keys:
                    prob_keys = [k for k in matching_keys if "probability" in k]
                    target_key = next(iter(prob_keys)) if prob_keys else next(iter(matching_keys))
                    p_arr = hourly_data.get(target_key, [])
                    
                    if p_arr and len(p_arr) > idx:
                        try:
                            val = p_arr[idx]
                            if val is not None:
                                if "precipitation" in target_key and "probability" not in target_key:
                                    probs[m_id] = 100 if float(val) > 0.1 else 0
                                else: 
                                    probs[m_id] = int(val)
                                    
                                statuses[m_id] = "🟢 Достоверно"
                                is_alive[m_id] = True
                                server_matrix[m_id][d["id"]] = "🟢"
                        except (ValueError, TypeError): pass
            else: 
                statuses[m_id] = msg
                
        live_models = [m for m in ALL_MODELS if is_alive[m]]
        final_p = min(max(int(sum((BASE_WEIGHTS[m] / sum(BASE_WEIGHTS[lm] for lm in live_models)) * probs[m] for m in live_models)), 0), 100) if live_models else None
        
        avg_temp = round(sum(temps)/len(temps), 1) if temps else 0
        avg_feel = round(sum(feels)/len(feels), 1) if feels else 0
        final_wmo = max(set(wmos), key=wmos.count) if wmos else 0
        avg_hum = round(sum(humidities)/len(humidities)) if humidities else 50
        avg_press = round((sum(pressures)/len(pressures)) * 0.75006) if pressures else 750
        avg_wind = round((sum(winds)/len(winds)), 1) if winds else 0
        max_gust = round(max(gusts), 1) if gusts else 0
        
        forecast_results.append({
            "id": d["id"], "name": d["name"], "center": d["center"], "prob": final_p,
            "temp": avg_temp, "feel": avg_feel, "wmo": final_wmo, "hum": avg_hum,
            "press": avg_press, "wind": avg_wind, "gust": max_gust, "src": statuses
        })
    return forecast_results, server_matrix
# ==========================================
# ЧАСТЬ 4: Визуализация — Stories и Карта Folium
# Длина блока: ~85 строк
# ==========================================
with st.spinner("⚡ Сканирование атмосферных параметров..."):
    fdata, matrix_data = build_radar_intelligence()
r_dict = {dist["name"]: dist["prob"] for dist in fdata}

# 🎨 1. РЕНДЕРИНГ STORIES
stories_elements = []
for dist in fdata:
    p = dist["prob"]
    p_text = "—" if p is None else f"{p}%"
    code = dist["wmo"]
    if code == 0: emoji = "☀️"
    elif code in (1, 2): emoji = "🌤️"
    elif code == 3: emoji = "☁️"
    elif code in (45, 48): emoji = "🌫️"
    elif code in (51, 53, 55, 56, 57): emoji = "🌦️"
    elif code in (61, 63, 65, 66, 67): emoji = "🌧️"
    elif code in (71, 73, 75, 77, 85, 86): emoji = "🌨️"
    elif code in (95, 96, 99): emoji = "⛈️"
    else: emoji = "☁️"
    ring_class = "ring-dry" if (p is None or p < 15) else ("ring-warning" if p < 45 else "ring-danger")
    card_html = f"""
    <div class="story-card">
        <div class="story-ring {ring_class}">
            <div class="story-body">
                <div class="story-emoji">{emoji}</div>
                <div class="story-pct">{p_text}</div>
            </div>
        </div>
        <div class="story-label">{dist['id']}</div>
    </div>
    """
    stories_elements.append(card_html.strip())
st.markdown(f'<div class="stories-feed">{"".join(stories_elements)}</div>', unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# --- 2. ОТРИСОВКА ИНТЕРАКТИВНОЙ КАРТЫ FOLIUM ---
try:
    with open("ufa_districts.geojson", "r", encoding="utf-8") as f: 
        ufa_geo = json.load(f)
    m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="OpenStreetMap")
    
    def style_d(feat):
        name = feat.get("properties", {}).get("name", "").strip()
        if name and "район" not in name.lower(): name = name + " район"
        p = r_dict.get(name, None)
        if p is None: return {"fillColor": "#cbd5e1", "color": "#94a3b8", "weight": 2.0, "fillOpacity": 0.1}
        color = "#1d4ed8" if p > 75 else ("#3b82f6" if p > 45 else ("#facc15" if p > 15 else "#16a34a"))
        return {"fillColor": color, "color": "#0f172a", "weight": 2.5, "fillOpacity": 0.3}

    folium.GeoJson(ufa_geo, style_function=style_d, tooltip=folium.GeoJsonTooltip(fields=["name"])).add_to(m)
    for dist in fdata:
        p_val = dist['prob']
        display_text = "—" if p_val is None else f"{p_val}%"
        folium.Marker(
            location=dist["center"], 
            icon=folium.DivIcon(icon_size=(60, 40), icon_anchor=(30, 20), 
            html=f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; font-weight: 900; color: #0f172a; text-shadow: 2px 2px 0px #fff, -2px -2px 0px #fff; text-align: center; width: 100%;">{display_text}</div>""")
        ).add_to(m)
    st_folium(m, width=950, height=480, key="ufa_instagram_radar_v2_premium")
except Exception as e:
    st.error(f"Не удалось загрузить карту или геоданные районов: {e}")
# ==========================================
# ЧАСТЬ 5: Лента публикаций (Grid) и Highlights
# Длина блока: ~50 строк
# ==========================================
st.markdown("### 📱 Лента публикаций по районам")
posts_elements = []
for dist in fdata:
    code = dist["wmo"]
    if code == 0: emoji = "☀️"
    elif code in (1, 2): emoji = "🌤️"
    elif code == 3: emoji = "☁️"
    elif code in (45, 48): emoji = "🌫️"
    elif code in (51, 53, 55, 56, 57): emoji = "🌦️"
    elif code in (61, 63, 65, 66, 67): emoji = "🌧️"
    elif code in (71, 73, 75, 77, 85, 86): emoji = "🌨️"
    elif code in (95, 96, 99): emoji = "⛈️"
    else: emoji = "☁️"
    
    gust_alert = "⚠️ Внимание: сильные порывы ветра!" if dist["gust"] > 11.0 else "Потоки ветра стабильны"
    single_post_html = f"""
    <div class="insta-post">
        <div class="post-header"><div class="post-avatar">{dist['id'][:2]}</div><div class="post-username">{dist['name']}</div></div>
        <div class="post-image-alt"><div class="post-temp">{dist['temp']}°C</div><div class="post-feel">Ощущается как {dist['feel']}°C • {emoji}</div></div>
        <div class="post-content">
            <div class="post-likes">📊 Текущие метеопоказатели:</div>
            <div class="post-metrics">
                <div>💧 <b>Влажность:</b> {dist['hum']}%</div><div>📊 <b>Давление:</b> {dist['press']} мм рт. ст.</div>
                <div>💨 <b>Ветер:</b> {dist['wind']} м/с (порывы до {dist['gust']} м/с)</div>
                <div style="font-size: 11px; color: #8e8e8e; margin-top: 6px; font-weight: 600;">{gust_alert}</div>
            </div>
        </div>
    </div>
    """
    posts_elements.append(single_post_html.strip())
st.markdown(f'<div class="insta-grid">{"".join(posts_elements)}</div>', unsafe_allow_html=True)
st.markdown("<br><br>", unsafe_allow_html=True)

# --- 4. HIGHLIGHTS (МАТРИЦА СЕРВЕРОВ) ---
st.markdown("### 🗂️ Актуальное (Highlights) — Состояние системных ядер")
h_cols = st.columns(len(ALL_MODELS))
for i, m_id in enumerate(ALL_MODELS):
    m_statuses = matrix_data.get(m_id, {})
    with h_cols[i]:
        st.markdown(f"""
        <div class="highlight-badge">
            <div style="font-size: 11px; font-weight: 700; color: #8e8e8e; text-transform: uppercase; margin-bottom: 4px;">{m_id}</div>
            <div style="font-size: 15px; font-weight: 800; color: #16a34a; margin-bottom: 4px;">🧬 ONLINE</div>
            <div style="font-size: 11px; color: #262626; letter-spacing: 0.5px;">
                Дем:{m_statuses.get('Дем','🟢')} Кал:{m_statuses.get('Kал','🟢')} Кир:{m_statuses.get('Кир','🟢')} Лен:{m_statuses.get('Лен','🟢')} Окт:{m_statuses.get('Окт','🟢')} Сов:{m_statuses.get('Сов','🟢')}
            </div>
        </div>
        """, unsafe_allow_html=True)
