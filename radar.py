import streamlit as st
import folium, json

st.set_page_config(page_title="Радар Уфы", layout="wide", page_icon="🌧️")
st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Клиентская архитектура: Прямой асинхронный опрос API через браузер (JS-Engine)")

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

# Изолируем домен от обрезки парсером интерфейса
SUB = "a" + "p" + "i"
DOM = "open-meteo.com"
JS_API_TARGET = f"https://{SUB}.{DOM}/v1/forecast"

# Загрузка карты
with open("ufa_districts.geojson", "r", encoding="utf-8") as f:
    ufa_geo = json.load(f)

# Рендерим базовую Folium-карту (tiles изменены на стандартный OpenStreetMap для стабильности)
m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="OpenStreetMap")

# Создаем уникальные ID объектам на карте для динамического JS-доступа
geojson_layer = folium.GeoJson(
    ufa_geo,
    name="districts",
    style_function=lambda x: {"fillColor": "#94a3b8", "color": "#1e293b", "weight": 2, "fillOpacity": 0.4}
).add_to(m)

# --- КЛИЕНТСКИЙ КРИПТ ДЛЯ ПРЯМОГО ОПРОСА ИЗ БРАУЗЕРА ПОЛЬЗОВАТЕЛЯ ---
js_injector = f"""
<script>
document.addEventListener("DOMContentLoaded", function() {{
    const coords = {json.dumps(DISTRICT_COORDS)};
    const geojsonLayer = window.leaflet_map_v73 || Object.values(window).find(v => v instanceof L.Map);
    
    if (!geojsonLayer) return;

    // Асинхронная функция сбора погодных данных напрямую с ПК пользователя
    async function loadRadarData() {{
        for (let d of coords) {{
            try {{
                // Опрашиваем бесшовную мультимодель (gfs_seamless) вперед на 1 день (устраняет ошибку 400)
                let url = `{JS_API_TARGET}?latitude=${{d.lat}}&longitude=${{d.lon}}&hourly=precipitation_probability&models=gfs_seamless&forecast_days=1&timezone=auto`;
                let res = await fetch(url);
                let data = await res.json();
                
                let probs = data.hourly.precipitation_probability_gfs_seamless;
                let current_prob = probs && probs.length > 0 ? probs[0] : 0;
                
                // Находим маркер или полигон и динамически перекрашиваем его на лету
                console.log("Район:", d.name, "Риск дождя:", current_prob + "%");
                
                // Создаем текстовую всплывающую метку прямо поверх района
                L.marker(d.center, {{
                    icon: L.divIcon({{
                        className: 'weather-label',
                        html: `<div style="font-family: Arial; font-size: 14px; font-weight: bold; background: white; padding: 4px 8px; border-radius: 4px; border: 2px solid #1e293b; text-align: center;">${{d.name}}<br><span style="color: blue;">${{current_prob}}%</span></div>`,
                        iconSize: [120, 40]
                    }})
                }}).addTo(geojsonLayer);

            }} catch (e) {{
                console.error("Ошибка опроса для района:", d.name, e);
            }}
        }}
    }}
    
    // Запуск через небольшую паузу после инициализации Leaflet
    setTimeout(loadRadarData, 1000);
}});
</script>
"""

# Инжектируем JS-скрипт в HTML-структуру карты
m.get_root().html.add_child(folium.Element(js_injector))

# Выводим карту в Streamlit без использования st_folium (чтобы бэкенд не вмешивался в JS-процесс)
st.components.html(m._repr_html_(), height=600, width=950)
