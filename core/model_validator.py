def validate_model(model: dict, profiles: list[dict]) -> list[str]:
    errors = []
    
    # 1. Собираем все доступные колонки из CSV
    available_cols = set()
    for p in profiles:
        for c in p['columns']:
            available_cols.add(c['name'])
            
    # 2. Проверяем Хабы
    hub_names = set()
    for hub in model.get("hubs", []):
        name = hub.get("name")
        if not name or not name.startswith("hub_"):
            errors.append(f"Хаб {name} имеет неверный префикс (должен быть hub_)")
        hub_names.add(name)
        
        for bk in hub.get("business_keys", []):
            if bk not in available_cols:
                errors.append(f"Хаб {name}: колонка '{bk}' не найдена в исходных CSV!")
                
    # 3. Проверяем Линки
    for link in model.get("links", []):
        name = link.get("name")
        if not name or not name.startswith("lnk_"):
            errors.append(f"Линк {name} имеет неверный префикс (должен быть lnk_)")
        
        for h in link.get("hubs", []):
            if h not in hub_names:
                errors.append(f"Линк {name} ссылается на несуществующий Хаб '{h}'")
                
    # 4. Проверяем Сателлиты
    for sat in model.get("satellites", []):
        name = sat.get("name")
        if not name or not (name.startswith("hsat_") or name.startswith("lsat_")):
            errors.append(f"Сателлит {name} имеет неверный префикс")
            
        parent = sat.get("parent")
        if parent not in hub_names and not any(l.get("name") == parent for l in model.get("links", [])):
            errors.append(f"Сателлит {name} ссылается на несуществующего родителя '{parent}'")
            
        for attr in sat.get("attributes", []):
            if attr not in available_cols:
                errors.append(f"Сателлит {name}: атрибут '{attr}' не найден в исходных CSV!")

    return errors