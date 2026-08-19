import streamlit as st
import folium, json
from streamlit_folium import st_folium
from jinja2 import Template

st.set_page_config(page_title="Радар Уфы", layout="wide", page_icon="🌧️")
st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Клиентская архитектура: Прямой асинхронный опрос API через изолированный JS-Макрос")

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

# Защищенный символьный сборщик домена от искажения парсером
SUB = "a" + "p" + "i"
DOM = "open-meteo.com"
JS_API_TARGET = f"https://{SUB}.{DOM}/v1/forecast"

# Загрузка карты районов Уфы
with open("ufa_districts.geojson", "r", encoding="utf-8") as f:
    ufa_geo = json.load(f)

# Создаем базовую Folium-карту
m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="OpenStreetMap")

# Наносим слой геометрии районов
folium.GeoJson(
    ufa_geo,
    name="districts",
    style_function=lambda x: {"fillColor": "#4f46e5", "color": "#1e1b4b", "weight": 2.5, "fillOpacity": 0.25}
).add_to(m)

# --- ШАБЛОН ИЗОЛИРОВАННОГО JS-МАКРОСА ДЛЯ ИНЖЕКЦИИ ВНУТРЬ IFRAME ---
class LeafletWeatherInjector(folium.elements.MacroElement):
    def __init__(self, coords, api_url):
        super(LeafletWeatherInjector, self).__init__()
        self.coords = coords
        self.api_url = api_url
        self._template = Template("""
            {% macro script(this, kwargs) %}
            (function() {
                const coords = {{ this.coords | tojson }};
                const apiTarget = "{{ this.api_url }}";
                
                // Внутренний идентификатор карты Leaflet в текущей сессии jinja
                const mapObject = {{ this._parent.get_name() }};
                
                if (!mapObject) return;

                async function fetchClientRadar() {
                    for (let d of coords) {
                        try {
                            let url = `${apiTarget}?latitude=${d.lat}&longitude=${d.lon}&hourly=precipitation_probability&models=gfs_seamless&forecast_days=1&timezone=auto`;
                            let res = await fetch(url);
                            let data = await res.json();
                            
                            let probs = data.hourly.precipitation_probability_gfs_seamless;
                            let current_prob = (probs && probs.length > 0) ? probs[0] : 0;
                            
                            // Вывод логов напрямую в консоль iframe браузера
                            console.log("Клиентский опрос:", d.name, "->", current_prob + "%");
                            
                            // Отрисовка метки поверх карты
                            L.marker(d.center, {
                                icon: L.divIcon({
                                    className: 'weather-label',
                                    html: `<div style="font-family: 'Arial', sans-serif; font-size: 12px; font-weight: 900; background: #ffffff; padding: 4px 8px; border-radius: 5px; border: 2px solid #1e1b4b; text-align: center; box-shadow: 1px 1px 4px rgba(0,0,0,0.15); white-space: nowrap;">${d.name}<br><span style="color: #2563eb; font-size: 14px;">${current_prob}%</span></div>`
                                })
                            }).addTo(mapObject);
                            
                        } catch (e) {
                            console.error("Ошибка воркспейса для:", d.name, e);
                        }
                    }
                }
                
                setTimeout(fetchClientRadar, 500);
            })();
            {% endmacro %}
        """)

# Добавляем наш изолированный макрос в карту
LeafletWeatherInjector(DISTRICT_COORDS, JS_API_TARGET).add_to(m)

# Безопасный рендеринг карты через виджет streamlit_folium
st_folium(m, width=950, height=550, key="ufa_map_macro_v75")
