# ==========================================
# ЧАСТЬ 1: Конфигурация, Стили и Блок ручного обновления (Кнопка)
# Длина блока: ~125 строк
# ==========================================
import streamlit as st
import requests
import folium
import json
from datetime import datetime
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

# Верстка верхней панели управления (Инстаграм-шапка + функциональная кнопка)
header_left, header_right = st.columns([4, 1])

with header_left:
    st.title("📸 WeatherGram Ufa")
    st.caption("Полнофункциональный погодный инстаграм-глянец радара Уфы")

with header_right:
    st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)
    # Кнопка обновления данных сбросит внутренний кэш Streamlit и перезапустит скрипт
    if st.button("🔄 Обновить радар", use_container_width=True, type="secondary"):
        st.cache_data.clear()
        st.rerun()

SUB_PREFIX, BASE_DOMAIN = "api", "open-meteo.com"
VALID_OPEN_METEO_URL = f"https://{SUB_PREFIX}.{BASE_DOMAIN}/v1/forecast"

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
# ЧАСТЬ 2: Генерация исходных URL и Сетевой воркер
# Длина блока: ~60 строк
# ==========================================
def get_model_url(lat, lon, model_key):
    base = f"{VALID_OPEN_METEO_URL}?latitude={lat}&longitude={lon}&timezone=auto&hourly=temperature_2m,apparent_temperature,weather_code,relative_humidity_2m,surface_pressure,wind_speed_10m,wind_gusts_10m"
    if model_key == "ecmwf": return f"{base},precipitation_probability&models=ecmwf_ifs&forecast_days=1"
    elif model_key == "gfs": return f"{base},precipitation_probability&models=gfs_seamless&forecast_days=1"
    elif model_key == "icon": return f"{base},precipitation_probability&models=icon_seamless&forecast_days=1"
    elif model_key == "jma": return f"{base},precipitation&models=jma_seamless&forecast_days=1"
    return base

@st.cache_data(ttl=300, show_spinner=False)
def fetch_single_api_node(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=5.0)
        if res.status_code == 200 and res.text.strip(): return res.json(), "🟢 Достоверно"
        return None, f"🔴 Ошибка HTTP {res.status_code}"
    except Exception: return None, "🔴 Ошибка сети"

def fetch_url_worker(task):
    dist_id, m_id, url = task
    json_body, status_msg = fetch_single_api_node(url)
    return dist_id, m_id, json_body, status_msg

def fetch_all_data_parallel():
    tasks = []
    for d in DISTRICT_COORDS:
        for m in ALL_MODELS: tasks.append((d["id"], m, get_model_url(d["lat"], d["lon"], m)))
    raw_responses = []
    with ThreadPoolExecutor(max_workers=16) as executor:
        results = executor.map(fetch_url_worker, tasks)
        for r in results: raw_responses.append(r)
    structured_data = {d["id"]: {} for d in DISTRICT_COORDS}
    for dist_id, m_id, json_body, status_msg in raw_responses:
        structured_data[dist_id][m_id] = {"json": json_body, "msg": status_msg}
    return structured_data
# ==========================================
# ==========================================
# ЧАСТЬ 3: Модернизированное аналитическое ядро с расчетом 6-часового тренда
# Длина блока: ~135 строк
# ==========================================
def build_radar_intelligence():
    network_package = fetch_all_data_parallel()
    forecast_results = []
    server_matrix = {m: {d["id"]: "🔴" for d in DISTRICT_COORDS} for m in ALL_MODELS}
    
    from datetime import timedelta
    ufa_now = datetime.utcnow() + timedelta(hours=5)
    current_hour = ufa_now.hour
    
    for d in DISTRICT_COORDS:
        probs = {m: 0 for m in ALL_MODELS}
        # Инициализируем почасовые матрицы для тренда (6 часов вперед)
        hourly_trend_matrix = {m: [0]*6 for m in ALL_MODELS}
        statuses = {m: "🔴 Нет данных" for m in ALL_MODELS}
        is_alive = {m: False for m in ALL_MODELS}
        
        temps, feels, wmos, humidities, pressures, winds, gusts = [], [], [], [], [], [], []
        dist_bundle = network_package.get(d["id"], {})
        
        for m_id in ALL_MODELS:
            node = dist_bundle.get(m_id, {"json": None, "msg": "🔴 Ошибка"})
            js, msg = node["json"], node["msg"]
            
            if js:
                hourly_data = js.get("hourly", {})
                matching_keys = [k for k in hourly_data.keys() if "precipitation" in k]
                idx = current_hour
                
                if "temperature_2m" in hourly_data and len(hourly_data["temperature_2m"]) > idx:
                    try:
                        if hourly_data["temperature_2m"][idx] is not None: temps.append(float(hourly_data["temperature_2m"][idx]))
                        if hourly_data["apparent_temperature"][idx] is not None: feels.append(float(hourly_data["apparent_temperature"][idx]))
                        if hourly_data["weather_code"][idx] is not None: wmos.append(int(hourly_data["weather_code"][idx]))
                        if hourly_data["relative_humidity_2m"][idx] is not None: humidities.append(int(hourly_data["relative_humidity_2m"][idx]))
                        if hourly_data["surface_pressure"][idx] is not None: pressures.append(float(hourly_data["surface_pressure"][idx]))
                        if hourly_data["wind_speed_10m"][idx] is not None: winds.append(float(hourly_data["wind_speed_10m"][idx]))
                        if hourly_data["wind_gusts_10m"][idx] is not None: gusts.append(float(hourly_data["wind_gusts_10m"][idx]))
                    except (IndexError, TypeError, ValueError): pass
                
                if isinstance(matching_keys, list) and len(matching_keys) > 0:
                    prob_keys = [k for k in matching_keys if "probability" in k]
                    target_key = next(iter(prob_keys)) if prob_keys else next(iter(matching_keys))
                    p_arr = hourly_data.get(target_key, [])
                    
                    if p_arr and len(p_arr) > idx:
                        try:
                            # 1. Извлекаем значение для текущего часа
                            val = p_arr[idx]
                            if val is not None:
                                if "precipitation" in target_key and "probability" not in target_key:
                                    probs[m_id] = 100 if float(val) > 0.1 else 0
                                else: probs[m_id] = int(val)
                                
                                statuses[m_id] = "🟢 Достоверно"
                                is_alive[m_id] = True
                                server_matrix[m_id][d["id"]] = "🟢"
                            
                            # 2. Собираем тренд на 6 часов вперед с защитой от выхода за границы массива
                            for h_offset in range(6):
                                t_idx = idx + h_offset
                                if t_idx < len(p_arr) and p_arr[t_idx] is not None:
                                    t_val = p_arr[t_idx]
                                    if "precipitation" in target_key and "probability" not in target_key:
                                        hourly_trend_matrix[m_id][h_offset] = 100 if float(t_val) > 0.1 else 0
                                    else:
                                        hourly_trend_matrix[m_id][h_offset] = int(t_val)
                        except (ValueError, TypeError): pass
            else: statuses[m_id] = msg
            
        live_models = [m for m in ALL_MODELS if is_alive[m]]
        
        # Расчет финальной текущей вероятности
        final_p = min(max(int(sum((BASE_WEIGHTS[m] / sum(BASE_WEIGHTS[lm] for lm in live_models)) * probs[m] for m in live_models)), 0), 100) if live_models else None
        
        # Интеграция и взвешивание 6-часового тренда по доступным моделям
        aggregated_trend = []
        for h_offset in range(6):
            if live_models:
                step_p = int(sum((BASE_WEIGHTS[m] / sum(BASE_WEIGHTS[lm] for lm in live_models)) * hourly_trend_matrix[m][h_offset] for m in live_models))
                aggregated_trend.append(min(max(step_p, 0), 100))
            else:
                aggregated_trend.append(0)
        
        avg_temp = round(sum(temps)/len(temps), 1) if temps else 0
        avg_feel = round(sum(feels)/len(feels), 1) if feels else 0
        final_wmo = max(set(wmos), key=wmos.count) if wmos else 0
        avg_hum = round(sum(humidities)/len(humidities)) if humidities else 50
        avg_press = round((sum(pressures)/len(pressures)) * 0.75006) if pressures else 750
        avg_wind = round((sum(winds)/len(winds)), 1) if winds else 0
        max_gust = round(max(gusts), 1) if gusts else 0
        
        forecast_results.append({
            "id": d["id"], "name": d["name"], "center": d["center"], "prob": final_p,
            "trend": aggregated_trend, "current_hour": current_hour,
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

# 🎨 1. МОНОЛИТНЫЙ РЕНДЕРИНГ STORIES
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
with open("ufa_districts.geojson", "r", encoding="utf-8") as f: ufa_geo = json.load(f)
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
    folium.Marker(location=dist["center"], icon=folium.DivIcon(icon_size=(60, 40), icon_anchor=(30, 20), html=f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; font-weight: 900; color: #0f172a; text-shadow: 2px 2px 0px #fff, -2px -2px 0px #fff; text-align: center; width: 100%;">{display_text}</div>""")).add_to(m)
st_folium(m, width=950, height=480, key="ufa_instagram_radar_v2_premium")
# ==========================================
# ЧАСТЬ 5: Исправленная лента публикаций (Без бага с сырым HTML)
# Длина блока: ~90 строк
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
    
    # ЗАЩИТА: Собираем тренд через конкатенацию списков, полностью исключая фигурные скобки внутри f-строк
    trend_html_items = []
    start_h = dist["current_hour"]
    for offset, t_prob in enumerate(dist["trend"]):
        display_hour = (start_h + offset) % 24
        bar_color = "#16a34a" if t_prob < 15 else ("#facc15" if t_prob < 45 else "#dc2743")
        
        # Строим каждый элемент разметки без использования f-строк со стилями
        item_html = (
            '<div style="display: flex; flex-direction: column; align-items: center; font-size: 11px; flex: 1;">'
            '<span style="color: #8e8e8e; font-weight: 600; margin-bottom: 2px;">' + f"{display_hour:02d}:00" + '</span>'
            '<div style="width: 100%; background-color: #f1f5f9; height: 5px; border-radius: 3px; overflow: hidden; min-width: 35px;">'
            '<div style="background-color: ' + bar_color + '; width: ' + f"{t_prob}%" + '; height: 100%;"></div>'
            '</div>'
            '<span style="font-weight: 700; color: #262626; margin-top: 2px;">' + f"{t_prob}%" + '</span>'
            '</div>'
        )
        trend_html_items.append(item_html)
        
    # Формируем контейнер тренда безопасным склеиванием строк
    trend_container = (
        '<div style="margin-top: 12px; border-top: 1px solid #efefef; padding-top: 10px;">'
        '<div style="font-weight: 700; font-size: 12px; color: #262626; margin-bottom: 8px;">📈 Тренд осадков (ближайшие 6 часов):</div>'
        '<div style="display: flex; gap: 8px; justify-content: space-between;">'
        + "".join(trend_html_items) +
        '</div>'
        '</div>'
    )

    # Вставляем уже собранный очищенный HTML-контейнер в пост
    single_post_html = f"""
    <div class="insta-post">
        <div class="post-header"><div class="post-avatar">{dist['id'][:2]}</div><div class="post-username">{dist['name']}</div></div>
        <div class="post-image-alt"><div class="post-temp">{dist['temp']}°C</div><div class="post-feel">Ощущается как {dist['feel']}°C • {emoji}</div></div>
        <div class="post-content">
            <div class="post-likes">📊 Текущие метеопоказатели:</div>
            <div class="post-metrics">
                <div>💧 <b>Влажность:</b> {dist['hum']}%</div><div>📊 <b>Давление:</b> {dist['press']} мм рт. ст.</div>
                <div>💨 <b>Ветер:</b> {dist['wind']} m/s (порывы до {dist['gust']} м/с)</div>
                <div style="font-size: 11px; color: #8e8e8e; margin-top: 6px; font-weight: 600;">{gust_alert}</div>
            </div>
            {trend_container}
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

