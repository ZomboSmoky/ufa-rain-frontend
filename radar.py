import streamlit as st
import folium, json
from streamlit_folium import st_folium
from jinja2 import Template

st.set_page_config(page_title="Радар Уфы", layout="wide", page_icon="🌧️")
st.title("🌧️ Микролокальный погодный радар Уфы")
st.subheader("Гибридная архитектура: Клиентский JS-парсинг текущего часа + Бэкенд-метеосводка")

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

# Защищенный символьный сборщик домена от искажения парсером интерфейса ИИ
SUB = "a" + "p" + "i"
DOM = "open-meteo.com"
JS_API_TARGET = f"https://{SUB}.{DOM}/v1/forecast"

# Загрузка карты районов Уфы
with open("ufa_districts.geojson", "r", encoding="utf-8") as f:
    ufa_geo = json.load(f)

# Создаем базовую Folium-карту
m = folium.Map(location=[54.745, 55.960], zoom_start=11, tiles="OpenStreetMap")

# Наносим слой геометрии районов с базовой аккуратной заливкой
folium.GeoJson(
    ufa_geo,
    name="districts",
    style_function=lambda x: {"fillColor": "#64748b", "color": "#0f172a", "weight": 2, "fillOpacity": 0.2}
).add_to(m)

# --- ИЗОЛИРОВАННЫЙ JS-МАКРОС С ИСПРАВЛЕННЫМ ВЫБОРОМ ТЕКУЩЕГО ЧАСА ---
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
                const mapObject = {{ this._parent.get_name() }};
                
                if (!mapObject) return;

                async function fetchClientRadar() {
                    // Определяем текущий час на компьютере пользователя (0-23)
                    const currentHour = new Date().getHours();
                    
                    for (let d of coords) {
                        try {
                            let url = `${apiTarget}?latitude=${d.lat}&longitude=${d.lon}&hourly=precipitation_probability&models=gfs_seamless&forecast_days=1&timezone=auto`;
                            let res = await fetch(url);
                            let data = await res.json();
                            
                            let probs = data.hourly.precipitation_probability_gfs_seamless;
                            
                            // ИСПРАВЛЕНО: Извлекаем значение строго для текущего часа, а не весь массив целиком
                            let current_prob = (probs && probs.length > currentHour) ? probs[currentHour] : 0;
                            
                            console.log("Успешный опрос:", d.name, "Час:", currentHour, "Вероятность:", current_prob + "%");
                            
                            // Динамический выбор цвета метки в зависимости от угрозы дождя
                            let labelColor = current_prob > 70 ? "#1f1fc2" : (current_prob > 40 ? "#2563eb" : (current_prob > 15 ? "#eab308" : "#16a34a"));
                            
                            // Рендерим плашку с реальными данными на карту
                            L.marker(d.center, {
                                icon: L.divIcon({
                                    className: 'weather-label',
                                    html: `<div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; font-weight: 800; background: #ffffff; padding: 5px 10px; border-radius: 6px; border: 2.5px solid ${labelColor}; text-align: center; box-shadow: 2px 2px 6px rgba(0,0,0,0.15); white-space: nowrap;">
                                            <span style="color: #0f172a;">${d.name}</span><br>
                                            <span style="color: ${labelColor}; font-size: 15px;">${current_prob}% risk</span>
                                           </div>`
                                })
                            }).addTo(mapObject);
                            
                        } catch (e) {
                            console.error("Ошибка клиентского воркспейса для:", d.name, e);
                        }
                    }
                }
                setTimeout(fetchClientRadar, 400);
            })();
            {% endmacro %}
        """)

# Активируем макрос инжекции в Leaflet
LeafletWeatherInjector(DISTRICT_COORDS, JS_API_TARGET).add_to(m)

# Рендерим карту в интерфейсе
st_folium(m, width=950, height=530, key="ufa_map_hybrid_v76")

# --- СТАТИЧЕСКАЯ ИНФОРМАЦИОННАЯ МЕТЕОСВОДКА ПО РАЙОНАМ ---
st.markdown("---")
st.markdown("### 📊 Метеосводка и аналитическая информация по районам")
st.info("💡 Карта выше обновляется в реальном времени вашим браузером. Ниже приведена справочная структура координатной сетки радара.")

cols = st.columns(3)
chunks = [DISTRICT_COORDS[i:i + 3] for i in range(0, len(DISTRICT_COORDS), 3)]

for col_idx, chunk in enumerate(chunks):
    with cols[col_idx]:
        for d in chunk:
            with st.expander(f"📍 {d['name']} (ID: {d['id']})"):
                st.markdown(f"""
                * **Широта (Latitude):** `{d['lat']}`
                * **Долгота (Longitude):** `{d['lon']}`
                * **Центроида маркера:** `{d['center']}`
                * **Целевой эндпоинт опроса:** [Open-Meteo API URL]({JS_API_TARGET}?latitude={d['lat']}&longitude={d['lon']}&hourly=precipitation_probability&models=gfs_seamless&forecast_days=1&timezone=auto)
                """)
