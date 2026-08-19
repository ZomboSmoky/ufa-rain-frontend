import streamlit as st
import requests, folium, json, time, random
import numpy as np
from streamlit_folium import st_folium

st.set_page_config(page_title="Радар Уфы", layout="wide", page_icon="🌧️")
st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Динамический ансамбль: строгая фильтрация достоверности данных")

DISTRICTS = [
    {"id": "Д", "name": "Дёмский район", "lat": 54.693, "lon": 55.811, "center": [54.685, 55.820]},
    {"id": "Кл", "name": "Калининский район", "lat": 54.831, "lon": 56.126, "center": [54.810, 56.120]},
    {"id": "Кр", "name": "Кировский район", "lat": 54.701, "lon": 55.992, "center": [54.670, 56.030]},
    {"id": "Л", "name": "Ленинский район", "lat": 54.752, "lon": 55.894, "center": [54.760, 55.850]},
    {"id": "О", "name": "Октябрьский район", "lat": 54.771, "lon": 56.031, "center": [54.770, 56.040]},
    {"id": "Орд", "name": "Орджоникидзевский район", "lat": 54.819, "lon": 56.095, "center": [54.825, 56.070]},
    {"id": "С", "name": "Советский район", "lat": 54.739, "lon": 55.975, "center": [54.738, 55.980]}
]

AUTONOMOUS_MODELS = {
    "ecmwf": "ecmwf_ifs", "gfs": "gfs_seamless", "icon": "icon_seamless",
    "arome": "meteofrance_arome", "jma": "jma_seamless", "yr_no": "yr_yr",
    "cma_china": "cma_graphes", "imd_india": "imd_gfs"
}
ALL_9 = ["ecmwf", "gfs", "icon", "arome", "jma", "yr_no", "cma_china", "imd_india", "fallback_7timer"]

# Базовые проектные веса моделей при идеальных условиях (равные доли)
BASE_WEIGHTS = {m: 1.0 / len(ALL_9) for m in ALL_9}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

def fetch_strict_radar_data(base_weights):
    forecast = []
    district_matrix = {m: {d["id"]: "🔴" for d in DISTRICTS} for m in ALL_9}
    global_weights = {m: 0.0 for m in ALL_9}
    
    for d in DISTRICTS:
        probs = {m: 0 for m in ALL_9}
        is_authentic = {m: False for m in ALL_9}
        err_logs = {m: "ОК" for m in ALL_9}
        
        session = requests.Session()
        current_headers = {"User-Agent": random.choice(USER_AGENTS), "Accept": "application/json"}
        
        # --- 1. ОПРОС СЕРВЕРОВ OPEN-METEO (8 МОДЕЛЕЙ) ---
        for m_id, api_name in AUTONOMOUS_MODELS.items():
            time.sleep(0.04)
            try:
                om_params = {
                    "latitude": float(d['lat']), "longitude": float(d['lon']),
                    "current": "time", "hourly": "precipitation_probability",
                    "models": str(api_name), "forecast_days": 1, "timezone": "auto"
                }
                res = session.get("https://open-meteo.com", params=om_params, headers=current_headers, timeout=3.5)
                
                if res.status_code == 200 and res.text.strip() and not res.text.startswith("<"):
                    res_json = res.json()
                    t_current = res_json.get("current", {}).get("time")
                    h_data = res_json.get("hourly", {})
                    times = h_data.get("time", [])
                    p_arr = h_data.get(f"precipitation_probability_{api_name}", [])
                    
                    if t_current and times and p_arr and (t_current in times):
                        idx = times.index(t_current)
                        probs[m_id] = int(p_arr[idx])
                        is_authentic[m_id] = True
                        district_matrix[m_id][d["id"]] = "🟢"
                    else:
                        raise Exception("Ошибка структуры или индексов времени в ответе")
                else:
                    raise Exception(f"HTTP {res.status_code} или HTML блокировка шлюза")
            except Exception as ex:
                probs[m_id] = 0
                is_authentic[m_id] = False
                err_logs[m_id] = str(ex)

        # --- 2. ОПРОС СЕРВЕРА 7TIMER (1 МОДЕЛЬ) ---
        try:
            time.sleep(0.04)
            st7_params = {"lon": float(d['lon']), "lat": float(d['lat']), "ac": 0, "unit": "metric", "output": "json"}
            res = session.get("https://7timer.info", params=st7_params, headers=current_headers, timeout=4.0)
            
            if res.status_code == 200 and res.text.strip() and not res.text.startswith("<"):
                cleaned_text = res.text.strip().lstrip('\ufeff')
                data_json = json.loads(cleaned_text)
                ds = data_json.get("dataseries", [])
                w_text = ds.get("weather", "clear") if (isinstance(ds, list) and len(ds) > 0) else "clear"
                probs["fallback_7timer"] = 85 if "rain" in w_text or "shower" in w_text else (35 if "cloud" in w_text else 10)
                is_authentic["fallback_7timer"] = True
                district_matrix["fallback_7timer"][d["id"]] = "🟢"
            else:
                raise Exception(f"HTTP {res.status_code} или HTML-заглушка")
        except Exception as ex:
            probs["fallback_7timer"] = 0
            is_authentic["fallback_7timer"] = False
            err_logs["fallback_7timer"] = str(ex)

        # --- 3. ДИНАМИЧЕСКИЙ РАСЧЕТ ВЕСОВ АНСАМБЛЯ ДЛЯ РАЙОНА ---
        # В вес берем ТОЛЬКО те модели, которые достоверно ответили по сети
        authentic_models = [m for m in ALL_9 if is_authentic[m]]
        src_disp = {}
        
        if not authentic_models:
            # Если вообще вся сеть лежит - выводим ноль и предупреждение
            final_p = 0
            for m in ALL_9:
                src_disp[m] = f"Прогноз: 0% | Вес: 0.0% | Состояние: 🔴 Недостоверно ({err_logs.get(m)})"
        else:
            # Считаем сумму базовых весов только ответивших серверов
            sum_base_w = sum(base_weights[m] for m in authentic_models)
            
            # Взвешиваем итоговую вероятность на основе их живых долей
            final_p = min(max(int(sum((base_weights[m] / sum_base_w) * probs[m] for m in authentic_models)), 0), 100)
            
            for m in ALL_9:
                if is_authentic[m]:
                    # Вычисляем долю модели внутри распределения живой сети
                    calc_w = round((base_weights[m] / sum_base_w * 100), 1)
                    global_weights[m] = calc_w # Для вывода общей панели
                    src_disp[m] = f"Прогноз: {probs[m]}% | Вес: {calc_w}% | Состояние: 🟢 Достоверно"
                else:
                    src_disp[m] = f"Прогноз: 0% | Вес: 0.0% | Состояние: 🔴 Недостоверно ({err_logs.get(m)})"
            
        forecast.append({"name": d["name"], "center": d["center"], "prob": final_p, "src": src_disp})
        
    return forecast, district_matrix, global_weights

with open("ufa_districts.geojson", "r", encoding="utf-8") as f:
    ufa_geo = json.load(f)

fdata, matrix_data, wdata = fetch_strict_radar_data(BASE_WEIGHTS)
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

st_folium(m, width=900, height=520, key="ufa_map_v52")

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
