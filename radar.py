import streamlit as st
import requests, folium, json
from datetime import datetime
from streamlit_folium import st_folium

st.set_page_config(page_title="Радар Уфы", layout="wide", page_icon="🌧️")
st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Серверная архитектура: Финальный контур метеоядер")

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

ALL_MODELS = ["ecmwf", "gfs", "icon", "jma", "yr_no"]
BASE_WEIGHTS = {m: 1.0 / len(ALL_MODELS) for m in ALL_MODELS}
HEADERS = {"User-Agent": "Mozilla/5.0 RadarUfa/1.0", "Accept": "application/json"}

def get_model_url(lat, lon, model_key):
    """Генерирует индивидуальный URL с учетом специфики каждого метеоядра"""
    if model_key == "yr_no":
        return f"{VALID_OPEN_METEO_URL}?latitude={lat}&longitude={lon}&hourly=precipitation_probability&models=yr_yr&forecast_days=2"
        
    base = f"{VALID_OPEN_METEO_URL}?latitude={lat}&longitude={lon}&timezone=auto"
    if model_key == "ecmwf":
        return f"{base}&hourly=precipitation_probability&models=ecmwf_ifs&forecast_days=1"
    elif model_key == "gfs":
        return f"{base}&hourly=precipitation_probability&models=gfs_seamless&forecast_days=1"
    elif model_key == "icon":
        return f"{base}&hourly=precipitation_probability&models=icon_seamless&forecast_days=1"
    elif model_key == "jma":
        return f"{base}&hourly=precipitation&models=jma_seamless&forecast_days=1"
    return base

@st.cache_data(ttl=600)
def fetch_single_node(lat, lon, model_key):
    """Выполняет изолированный запрос к конкретной погодной модели"""
    url = get_model_url(lat, lon, model_key)
    try:
        res = requests.get(url, headers=HEADERS, timeout=4.0)
        if res.status_code == 200 and res.text.strip():
            return res.json(), "🟢 Достоверно"
        return None, f"🔴 Ошибка HTTP {res.status_code}"
    except Exception as e:
        return None, "🔴 Ошибка сети"

def build_radar_intelligence():
    forecast_results = []
    server_matrix = {m: {d["id"]: "🔴" for d in DISTRICT_COORDS} for m in ALL_MODELS}
    current_hour = datetime.now().hour
    
    for d in DISTRICT_COORDS:
        probs = {m: 0 for m in ALL_MODELS}
        statuses = {m: "🔴 Нет данных" for m in ALL_MODELS}
        is_alive = {m: False for m in ALL_MODELS}
        
        for m_id in ALL_MODELS:
            js, msg = fetch_single_node(d["lat"], d["lon"], m_id)
            
            if js:
                hourly_data = js.get("hourly", {})
                matching_keys = [k for k in hourly_data.keys() if "precipitation" in k]
                
                if matching_keys:
                    # ВЕРИФИЦИРОВАНО: Извлекаем строго первый строковый элемент списка во избежание TypeError
                    target_key = str(matching_keys[0])
                    p_arr = hourly_data.get(target_key, [])
                    
                    if m_id == "yr_no":
                        idx = current_hour - 5
                        if idx < 0: idx = 24 + idx
                    else:
                        idx = current_hour
                    
                    if p_arr and len(p_arr) > idx:
                        try:
                            val = p_arr[idx]
                            if val is not None:
                                if "precipitation" in target_key and not "probability" in target_key:
                                    probs[m_id] = 100 if float(val) > 0.1 else 0
                                else:
                                    probs[m_id] = int(val)
                                    
                                statuses[m_id] = "🟢 Достоверно"
                                is_alive[m_id] = True
                                server_matrix[m_id][d["id"]] = "🟢"
                            else:
                                statuses[m_id] = "🔴 Значение в JSON равно null"
                        except (ValueError, TypeError):
                            statuses[m_id] = "🔴 Некорректный формат числа"
                    else:
                        statuses[m_id] = "🔴 Ошибка диапазона индексов"
                else:
                    statuses[m_id] = "🔴 Переменная осадков отсутствует"
            else:
                statuses[m_id] = msg

        live_models = [m for m in ALL_MODELS if is_alive[m]]
        src_disp = {}
        
        if not live_models:
            final_p = None
            for m in ALL_MODELS: src_disp[m] = f"Прогноз: Данные отсутствуют | Вес: 0.0% | Статус: {statuses[m]}"
        else:
            sum_base_w = sum(BASE_WEIGHTS[m] for m in live_models)
            final_p = min(max(int(sum((BASE_WEIGHTS[m] / sum_base_w) * probs[m] for m in live_models)), 0), 100)
            for m in ALL_MODELS:
                if is_alive[m]:
                    calc_w = round((BASE_WEIGHTS[m] / sum_base_w * 100), 1)
                    src_disp[m] = f"Прогноз: {probs[m]}% | Вес: {calc_w}% | Статус: {statuses[m]}"
                else:
                    src_disp[m] = f"Прогноз: 0% | Вес: 0.0% | Статус: {statuses[m]}"
                    
        forecast_results.append({"name": d["name"], "center": d["center"], "prob": final_p, "src": src_disp})
        
    return forecast_results, server_matrix

# --- СБОР ДАННЫХ НА СЕРВЕРЕ ---
fdata, matrix_data = build_radar_intelligence()
r_dict = {dist["name"]: dist["prob"] for dist in fdata}

# --- ОТРИСОВКА FOLIUM ---
with open("ufa_districts.geojson", "r", encoding="utf-8") as f:
    ufa_geo = json.load(f)

m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="OpenStreetMap")

def style_d(feat):
    name = feat.get("properties", {}).get("name", "").strip()
    if name and "район" not in name.lower(): name = name + " район"
    p = r_dict.get(name, None)
    
    if p is None:
        return {"fillColor": "#cbd5e1", "color": "#94a3b8", "weight": 2.0, "fillOpacity": 0.1}
        
    color = "#1d4ed8" if p > 75 else ("#3b82f6" if p > 45 else ("#facc15" if p > 15 else "#16a34a"))
    return {"fillColor": color, "color": "#0f172a", "weight": 2.5, "fillOpacity": 0.3}

folium.GeoJson(ufa_geo, style_function=style_d, tooltip=folium.GeoJsonTooltip(fields=["name"])).add_to(m)

for dist in fdata:
    p_val = dist['prob']
    display_text = "—" if p_val is None else f"{p_val}%"
    
    folium.Marker(
        location=dist["center"],
        icon=folium.DivIcon(
            icon_size=(60, 40), icon_anchor=(30, 20),
            html=f"""<div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; font-weight: 900; color: #0f172a; text-shadow: 2px 2px 0px #fff, -2px -2px 0px #fff; text-align: center; width: 100%;">{display_text}</div>"""
        )
    ).add_to(m)

st_folium(m, width=950, height=530, key="ufa_pure_python_radar")

# --- МЕТЕОСВОДКА STREAMLIT ---
st.markdown("### 📊 Аналитическая метеосводка по районам")
for dist in fdata:
    prob_header = "Нет данных" if dist['prob'] is None else f"{dist['prob']}% общий риск осадков"
    with st.expander(f"📍 {dist['name']} — **{prob_header}**"):
        st.json(dist['src'])

st.markdown("---")
st.markdown("### 🖥️ Системная матрица ответов погодных ядер")
cols = st.columns(len(ALL_MODELS))
for i, m_id in enumerate(ALL_MODELS):
    m_statuses = matrix_data.get(m_id, {})
    status_line = " ".join([f"{rid}:{m_statuses.get(rid, '🔴')}" for rid in ["Д", "Кл", "Кр", "Л", "О", "Орд", "С"]])
    with cols[i]:
        st.metric(label=m_id.upper(), value="ONLINE" if "🔴" not in m_statuses.values() else "PARTIAL", delta=status_line)
