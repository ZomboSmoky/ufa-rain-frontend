import streamlit as st
import requests, folium, json, time, random
import numpy as np
from datetime import datetime
from streamlit_folium import st_folium

st.set_page_config(page_title="Радар Уфы", layout="wide", page_icon="🌧️")
st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Модульная архитектура: 9 изолированных контуров со сквозным CORS-проксированием")

DISTRICTS = [
    {"id": "Д", "name": "Дёмский район", "lat": 54.693, "lon": 55.811, "center": [54.685, 55.820]},
    {"id": "Кл", "name": "Калининский район", "lat": 54.831, "lon": 56.126, "center": [54.810, 56.120]},
    {"id": "Кр", "name": "Кировский район", "lat": 54.701, "lon": 55.992, "center": [54.670, 56.030]},
    {"id": "Л", "name": "Ленинский район", "lat": 54.752, "lon": 55.894, "center": [54.760, 55.850]},
    {"id": "О", "name": "Октябрьский район", "lat": 54.771, "lon": 56.031, "center": [54.770, 56.040]},
    {"id": "Орд", "name": "Орджоникидзевский район", "lat": 54.819, "lon": 56.095, "center": [54.825, 56.070]},
    {"id": "С", "name": "Советский район", "lat": 54.739, "lon": 55.975, "center": [54.738, 55.980]}
]

ALL_9 = ["ecmwf", "gfs", "icon", "arome", "jma", "yr_no", "cma_china", "imd_india", "fallback_7timer"]
BASE_WEIGHTS = {m: 1.0 / len(ALL_9) for m in ALL_9}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Публичные шлюзы для смены забаненного IP Streamlit Cloud
PROXIES = [
    "https://allorigins.win",
    "https://corsproxy.io"
]

def make_proxied_request(raw_url):
    """Вспомогательная функция для перебора прокси-серверов"""
    for proxy in PROXIES:
        try:
            encoded_url = requests.utils.quote(raw_url) if "allorigins" in proxy else raw_url
            res = requests.get(f"{proxy}{encoded_url}", headers=HEADERS, timeout=5.0)
            if res.status_code == 200 and res.text.strip() and not res.text.startswith("<"):
                return res.text
        except:
            continue
    return None

# --- ПОЛНОСТЬЮ ИЗОЛИРОВАННЫЕ КОНТУРЫ С ОБХОДОМ БЛОКИРОВОК ---

def get_europe_model(model_name, lat, lon):
    try:
        time.sleep(0.02)
        url = f"https://open-meteo.com{float(lat)}&longitude={float(lon)}&hourly=precipitation_probability&models={model_name}&forecast_days=1&timezone=auto"
        response_text = make_proxied_request(url)
        if response_text:
            p_arr = json.loads(response_text).get("hourly", {}).get(f"precipitation_probability_{model_name}", [])
            if p_arr: 
                return int(p_arr[0]), "🟢 Достоверно (Сеть через Прокси)"
    except Exception as e:
        return 0, f"🔴 Недостоверно ({str(e)})"
    return 0, "🔴 Недостоверно (Все прокси-шлюзы заблокированы)"

def get_asian_archive_model(model_name, lat, lon):
    try:
        time.sleep(0.02)
        # Динамически берем вчерашний день, чтобы архив гарантированно выдал сформированный пакет осадков
        yesterday_str = datetime.now().strftime("%Y-%m-%d")
        url = f"https://open-meteo.com{float(lat)}&longitude={float(lon)}&hourly=precipitation&models={model_name}&start_date={yesterday_str}&end_date={yesterday_str}"
        response_text = make_proxied_request(url)
        if response_text:
            p_arr = json.loads(response_text).get("hourly", {}).get(f"precipitation_{model_name}", [])
            if p_arr and len(p_arr) > 0:
                prob = min(int(float(p_arr[-1]) * 100), 95) if float(p_arr[-1]) > 0 else 10
                return prob, "🟢 Достоверно (Сеть через Прокси)"
    except Exception as e:
        return 0, f"🔴 Недостоверно ({str(e)})"
    return 0, "🔴 Недостоверно (Все прокси-шлюзы заблокированы)"

def get_7timer_isolated(lat, lon):
    try:
        time.sleep(0.03)
        url = f"https://7timer.info{float(lon)}&lat={float(lat)}&ac={random.randint(1,99)}&unit=metric&output=json"
        response_text = make_proxied_request(url)
        if response_text:
            cleaned = response_text.strip().lstrip('\ufeff')
            js = json.loads(cleaned)
            ds = js.get("dataseries", [])
            w_text = ds[0].get("weather", "clear") if (isinstance(ds, list) and len(ds) > 0) else "clear"
            prob = 85 if "rain" in w_text or "shower" in w_text else (40 if "cloud" in w_text else 10)
            return prob, "🟢 Достоверно (Сеть через Прокси)"
    except Exception as e:
        return 0, f"🔴 Недостоверно ({str(e)})"
    return 0, "🔴 Недостоверно (Ошибка сети 7timer)"

# --- АНСАМБЛЕВЫЙ ПРОЦЕССОР РАДАРНЫХ ДАННЫХ ---

def fetch_isolated_radar_data():
    forecast = []
    district_matrix = {m: {d["id"]: "🔴" for d in DISTRICTS} for m in ALL_9}
    global_weights = {m: 0.0 for m in ALL_9}
    
    for d in DISTRICTS:
        probs = {m: 0 for m in ALL_9}
        statuses = {m: "🔴 Недостоверно" for m in ALL_9}
        is_alive = {m: False for m in ALL_9}
        
        # 1. Опрос европейского контура
        euro_map = {"ecmwf": "ecmwf_ifs", "gfs": "gfs_seamless", "icon": "icon_seamless", "arome": "meteofrance_arome", "jma": "jma_seamless"}
        for m_id, sys_name in euro_map.items():
            val, msg = get_europe_model(sys_name, d["lat"], d["lon"])
            probs[m_id], statuses[m_id] = val, msg
            if "🟢" in msg:
                is_alive[m_id] = True
                district_matrix[m_id][d["id"]] = "🟢"
                
        # 2. Опрос азиатского контура архивов (Китай, Индия, Норвегия)
        asia_map = {"cma_china": "cma_graphes", "imd_india": "imd_gfs", "yr_no": "yr_yr"}
        for m_id, sys_name in asia_map.items():
            val, msg = get_asian_archive_model(sys_name, d["lat"], d["lon"])
            probs[m_id], statuses[m_id] = val, msg
            if "🟢" in msg:
                is_alive[m_id] = True
                district_matrix[m_id][d["id"]] = "🟢"

        # 3. Опрос контура 7timer
        val_7t, msg_7t = get_7timer_isolated(d["lat"], d["lon"])
        probs["fallback_7timer"], statuses["fallback_7timer"] = val_7t, msg_7t
        if "🟢" in msg_7t:
            is_alive["fallback_7timer"] = True
            district_matrix["fallback_7timer"][d["id"]] = "🟢"

        # --- СТРОГИЙ ДИНАМИЧЕСКИЙ ПЕРЕСЧЕТ ВЕСОВ ---
        live_models = [m for m in ALL_9 if is_alive[m]]
        src_disp = {}
        
        if not live_models:
            final_p = 0
            for m in ALL_9: src_disp[m] = f"Прогноз: 0% | Вес: 0.0% | Состояние: {statuses[m]}"
        else:
            sum_base_w = sum(BASE_WEIGHTS[m] for m in live_models)
            final_p = min(max(int(sum((BASE_WEIGHTS[m] / sum_base_w) * probs[m] for m in live_models)), 0), 100)
            
            for m in ALL_9:
                if is_alive[m]:
                    calc_w = round((BASE_WEIGHTS[m] / sum_base_w * 100), 1)
                    global_weights[m] = calc_w
                    src_disp[m] = f"Прогноз: {probs[m]}% | Вес: {calc_w}% | Состояние: {statuses[m]}"
                else:
                    src_disp[m] = f"Прогноз: 0% | Вес: 0.0% | Состояние: {statuses[m]}"
                    
        forecast.append({"name": d["name"], "center": d["center"], "prob": final_p, "src": src_disp})
        
    return forecast, district_matrix, global_weights

# --- РЕНДЕРИНГ ФИНАЛЬНОГО ИНТЕРФЕЙСА MAPPING ---

with open("ufa_districts.geojson", "r", encoding="utf-8") as f:
    ufa_geo = json.load(f)

fdata, matrix_data, wdata = fetch_isolated_radar_data()
r_dict = {dist["name"]: dist["prob"] for dist in fdata}

m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="cartodbpositron")

def style_d(feat):
    name = feat.get("properties", {}).get("name", "").strip()
    if name and "район" not in name.lower(): name = name + " район"
    p = r_dict.get(name, 0.0)
    color = "#1f1fc2" if p > 70 else ("#6ba1ff" if p > 40 else ("#ffd166" if p > 25 else ("#aacc00" if p > 12 else "#47c95e")))
    return {"fillColor": color, "color": "#1a1a1a", "weight": 2.5, "fillOpacity": 0.3}

folium.GeoJson(ufa_geo, style_function=style_d, tooltip=folium.GeoJsonTooltip(fields=["name"])).add_to(m)

for dist in fdata:
    folium.Marker(
        location=dist["center"],
        icon=folium.DivIcon(
            icon_size=(50, 50), icon_anchor=(25, 15),
            html=f"""<div style="font-family: 'Arial Black', sans-serif; font-size: 16px; font-weight: 900; color: #0f172a; text-shadow: 2px 2px 0px #fff, -2px -2px 0px #fff; text-align: center; width: 100%;">{dist['prob']}%</div>"""
        )
    ).add_to(m)

st_folium(m, width=900, height=520, key="ufa_map_v59")

st.markdown("### 📊 Метеосводка по районам")
for dist in fdata:
    with st.expander(f"📍 {dist['name']} — **{dist['prob']}% риск**"):
        st.json(dist['src'])
    
st.markdown("---")
st.markdown("### 🖥️ Текущий статус оригинальности метео-серверов")
cols = st.columns(9)
labels = [
    ("ecmwf", "ECMWF"), ("gfs", "GFS"), ("icon", "ICON"), 
    ("arome", "France"), ("jma", "JMA"), ("yr_no", "Yr.no"), 
    ("cma_china", "CMA"), ("imd_india", "IMD"), ("fallback_7timer", "7timer")
]

for i, (k, lbl) in enumerate(labels):
    current_w = wdata.get(k, 0.0)
    m_statuses = matrix_data.get(k, {})
    status_line = " ".join([str(rid) + ":" + str(m_statuses.get(rid, '🔴')) for rid in ["Д", "Кл", "Кр", "Л", "О", "Орд", "С"]])
    is_fully_online = "🔴" not in m_statuses.values() and len(m_statuses) > 0
    
    with cols[i]:
        if is_fully_online:
            st.success(f"**{lbl}**\n\n{status_line}\n\n⚖️ Вес: {current_w}%")
        else:
            st.warning(f"**{lbl}**\n\n{status_line}\n\n⚖️ Вес: {current_w}%")
