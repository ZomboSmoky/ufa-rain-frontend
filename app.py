    def style_district(feature):
        osm_name = feature.get("properties", {}).get("name", "").strip()
        if osm_name and "район" not in osm_name.lower():
            osm_name = f"{osm_name} район"
            
        prob = name_risk_dict.get(osm_name, 0.0)
        
        # Динамическая шкала для визуального разделения районов
        if prob > 70: 
            color = "#1f1fc2"      # Синий (Сильный ливень)
        elif prob > 40: 
            color = "#6ba1ff"    # Голубой (Умеренный дождь)
        elif prob > 25: 
            color = "#ffd166"    # Жёлтый / Оранжевый (Небольшой риск / Морось)
        elif prob > 12: 
            color = "#aacc00"    # Салатовый (Переменная облачность, слабый тренд)
        else: 
            color = "#47c95e"    # Ярко-зелёный (Полностью сухо)
            
        return {"fillColor": color, "color": "#1a1a1a", "weight": 2.5, "fillOpacity": 0.6}
