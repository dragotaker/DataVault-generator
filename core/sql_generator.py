def _get_pg_type(pandas_type: str) -> str:
    pandas_type = str(pandas_type).lower()
    if 'int' in pandas_type:
        return 'BIGINT'
    if 'float' in pandas_type:
        return 'NUMERIC(18,4)'
    if 'bool' in pandas_type:
        return 'BOOLEAN'
    if 'datetime' in pandas_type:
        return 'TIMESTAMP'
    return 'TEXT'

def generate_sql(model: dict, profiles: list[dict], schema: str = "data_vault") -> str:
    # Собираем словарь: имя колонки -> pandas_type
    col_types = {}
    for p in profiles:
        for c in p['columns']:
            col_types[c['name']] = c.get('pandas_type', 'string')

    sql = [f"CREATE SCHEMA IF NOT EXISTS {schema};\n"]
    
    # 1. Генерируем Хабы
    for hub in model.get("hubs", []):
        name = hub["name"]
        sql.append(f"CREATE TABLE {schema}.{name} (")
        sql.append(f"    hash_key VARCHAR(32) PRIMARY KEY,")
        for bk in hub["business_keys"]:
            sql.append(f"    {bk} TEXT NOT NULL,")
        sql.append(f"    load_date TIMESTAMP NOT NULL,")
        sql.append(f"    record_source VARCHAR(255) NOT NULL\n);\n")
        
    # 2. Генерируем Линки
    for link in model.get("links", []):
        name = link["name"]
        sql.append(f"CREATE TABLE {schema}.{name} (")
        sql.append(f"    link_hash_key VARCHAR(32) PRIMARY KEY,")
        for h in link["hubs"]:
            sql.append(f"    {h}_hash_key VARCHAR(32) NOT NULL,")
        sql.append(f"    load_date TIMESTAMP NOT NULL,")
        sql.append(f"    record_source VARCHAR(255) NOT NULL\n);\n")
        
    # 3. Генерируем Сателлиты
    for sat in model.get("satellites", []):
        name = sat["name"]
        parent = sat["parent"]
        parent_key = f"{parent}_hash_key" if parent.startswith("hub_") else "link_hash_key"
        
        sql.append(f"CREATE TABLE {schema}.{name} (")
        sql.append(f"    {parent_key} VARCHAR(32) NOT NULL,")
        sql.append(f"    hash_diff VARCHAR(32) NOT NULL,")
        sql.append(f"    load_date TIMESTAMP NOT NULL,")
        sql.append(f"    load_end_date TIMESTAMP,")
        sql.append(f"    record_source VARCHAR(255) NOT NULL,")
        
        for attr in sat.get("attributes", []):
            pg_type = _get_pg_type(col_types.get(attr, 'string'))
            sql.append(f"    {attr} {pg_type},")
            
        sql.append(f"    PRIMARY KEY ({parent_key}, load_date)\n);\n")
        
    return "\n".join(sql)