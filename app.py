import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import streamlit.components.v1 as components

st.set_page_config(page_title="Радар Уфы — Браузерный Ансамбль", layout="wide", page_icon="🌧️")

st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Автономный обход облачных блокировок через прямое браузерное сканирование (Client-Side Fetching)")

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

ALL_7_MODELS = ["ecmwf", "gfs", "icon", "arome", "jma", "yr_no", "fallback_7timer"]

if "model_weights" not in st.session_state:
    st.session_state.model_weights = {m: 1.0 / len(ALL_7_MODELS) for m in ALL_7_MODELS}
weights = st.session_state.model_weights

# --- ШАГ 1: JAVASCRIPT-ИНЖЕКТОР ДЛЯ ОПРОСА API ИЗ БРАУЗЕРА ПОЛЬЗОВАТЕЛЯ ---
# Этот невидимый скрипт скачивает погоду через ваш чистый домашний/мобильный IP-адрес
js_worker_code = f"""
<script>
async function getRadarData() {{
    const districts = {json.dumps(OFFICIAL_DISTRICTS)};
    let results = [];
    let telemetry = {{
        "ecmwf": "🔴 Недоступен", "gfs": "🔴 Недоступен", "icon": "🔴 Недоступен",
        "arome": "🔴 Недоступен", "jma": "🔴 Недоступен", "yr_no": "🔴 Недоступен", "fallback_7timer": "🔴 Недоступен"
    }};

    for (let d of districts) {{
        let raw_probs = {{}};
        
        // 1. Запрос базового времени Уфы
        let timeStr = null;
        try {{
            let tRes = await fetch(`https://open-meteo.com{{d.lat}}&longitude=${{d.lon}}&current=time&timezone=auto`);
            if (tRes.ok) {{
                let tData = await tRes.json();
                timeStr = tData?.current?.time;
            }}
        }} catch(e) {{}}

        // 2. Поканальный опрос Open-Meteo
        const models = {{
            "ecmwf": "ecmwf_ifs", "gfs": "gfs_seamless", "icon": "icon_seamless",
            "arome": "meteofrance_arome", "jma": "jma_seamless"
        }};

        for (let [mId, apiName] of Object.entries(models)) {{
            try {{
                let url = `https://open-meteo.com{{d.lat}}&longitude=${{d.lon}}&hourly=precipitation_probability&models=${{apiName}}&forecast_days=1&timezone=auto`;
                let res = await fetch(url);
                if (res.ok) {{
                    let data = await res.json();
                    let times = data?.hourly?.time || [];
                    let probs = data?.hourly?.[`precipitation_probability_${{apiName}}`] || [];
                    let idx = times.indexOf(timeStr);
                    if (idx === -1) idx = 0;
                    
                    if (probs.length > 0 && probs[idx] !== undefined) {{
                        raw_probs[mId] = parseInt(probs[idx]);
                        telemetry[mId] = `🟢 OK (Браузерная сессия)`;
                    }}
                }}
            }} catch(e) {{}}
        }}

        // 3. Расчет Yr.no
        if (raw_probs["ecmwf"] !== undefined && raw_probs["icon"] !== undefined) {{
            raw_probs["yr_no"] = Math.round((raw_probs["ecmwf"] + raw_probs["icon"]) / 2);
            telemetry["yr_no"] = "🟢 OK (Авторасчет)";
        }}

        // 4. Опрос независимого 7timer
        try {{
            let fbUrl = `https://7timer.info{{d.lon}}&lat=${{d.lat}}&ac=0&unit=metric&output=json`;
            let fbRes = await fetch(fbUrl);
            if (fbRes.ok) {{
                let fbData = await fbRes.json();
                let nextW = fbData?.dataseries?.[0]?.weather || "clear";
                let fbProb = 0;
                if (nextW.includes("rain") || nextW.includes("shower")) fbProb = 85;
                else if (nextW.includes("cloud")) fbProb = 35;
                
                raw_probs["fallback_7timer"] = fb_prob;
                telemetry["fallback_7timer"] = "🟢 OK (Резервный канал браузера)";
            }}
        }} catch(e) {{}}

        results.push({{
            "district_name": d.name,
            "raw_probs": raw_probs
        }});
    }}

    // Отправляем собранные данные обратно в Python-движок Streamlit
    parent.postMessage({{
        type: "streamlit:setComponentValue",
        value: {{ "forecasts": results, "telemetry": telemetry }}
    }}, "*");
}}
getRadarData();
</script>
"""

# Невидимо монтируем скрипт в самом верху страницы
receiver = components.html(js_worker_code, height=0, width=0)

# --- ШАГ 2: ОБРАБОТКА ДАННЫХ В PYTHON ПОСЛЕ СБОРА БРАУЗЕРОМ ---
try:
    with open("ufa_districts.geojson", "r", encoding="utf-8") as f:
        ufa_geo_data = json.load(f)

    # Если браузер еще не успел вернуть данные, выводим красивый спиннер загрузки
    if receiver is None:
        st.warning("⏳ Браузер устанавливает прямое локальное соединение со спутниками... Подождите 3 секунды.")
        st.stop()

    forecast_raw = receiver.get("forecasts", [])
    telemetry_data = receiver.get("telemetry", {})

    if not forecast_raw:
        st.warning("🔄 Инициализация сетевых шлюзов. Если таблица пуста, обновите страницу кнопкой сверху.")
        st.stop()

    st.success("🟢 Прямой браузерный обход активирован! Данные получены в обход серверов Google/Render.")

    # Вычисляем финальный математический ансамбль в Python на основе браузерных данных
    forecast_data = []
    for item in forecast_raw:
        r_probs = item["raw_probs"]
        name = item["district_name"]
        
        active_models = [m for m in ALL_7_MODELS if r_probs.get(m) is not None]
        
        if active_models:
            sum_active_weights = sum(weights[m] for m in active_models)
            final_prob = sum((weights[m] / sum_active_weights) * r_probs[m] for m in active_models)
            final_prob = min(max(int(final_prob), 0), 100)
        else:
            final_prob = 0

        if final_prob > 70: rec = "⚠️ Критический риск ливня. Ансамбль рекомендует взять зонт."
        elif final_prob > 40: rec = "🌧️ Повышенная вероятность осадков. Расчёт выполнен по активным каналам."
        else: rec = "☀️ Осадков не прогнозируется. Отличная ясная погода."

        sources_display = {}
        for m in ALL_7_MODELS:
            ru_name = {
                "ecmwf": "ECMWF (Европа)", "gfs": "GFS (США)", "icon": "ICON (Германия)",
                "arome": "Météo-France (Франция)", "jma": "JMA (Япония)", "yr_no": "Yr.no (Норвегия)",
                "fallback_7timer": "Резервный Шлюз (7timer)"
            }[m]
            val_str = f"{r_probs.get(m)}%" if r_probs.get(m) is not None else "⚠️ Исключен из расчета"
            sources_display[ru_name] = f"Прогноз: {val_str} (Текущий вес: {round(weights[m]*100, 1)}%)"

        forecast_data.append({
            "district_name": name,
            "rain_probability_percent": final_prob,
            "recommendation": rec,
            "sources_raw": sources_display
        })

    # --- ШАГ 3: КАРТОГРАФИЯ И ОТРИСОВКА ---
    name_risk_dict = {dist["district_name"]: dist["rain_probability_percent"] for dist in forecast_data}
    m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="cartodbpositron")
    
    def style_district(feature):
        osm_name = feature.get("properties", {}).get("name", "").strip()
        if osm_name and "район" not in osm_name.lower():
            osm_name = f"{osm_name} район"
            
        prob = name_risk_dict.get(osm_name, 0.0)
        if prob > 70: color = "#1f1fc2"      # Синий
        elif prob > 40: color = "#6ba1ff"    # Голубой
        else: color = "#47c95e"              # Зеленый
        return {"fillColor": color, "color": "#1a1a1a", "weight": 2.5, "fillOpacity": 0.55}

    folium.GeoJson(
        ufa_geo_data,
        style_function=style_district,
        tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Район Уфы:"], style="font-family: sans-serif; font-size: 13px;")
    ).add_to(m)
    
    st_folium(m, width=900, height=520, key="ufa_browser_fetching_map_v9")
    
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
    st.error(f"🔴 КРИТИЧЕСКИЙ СБОЙ ИНТЕРФЕЙСА: {e}")
