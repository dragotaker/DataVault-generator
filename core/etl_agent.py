import pandas as pd
import hashlib
import psycopg
from datetime import datetime
from psycopg import sql

def generate_hash(value: str) -> str:
    return hashlib.md5(str(value).encode('utf-8')).hexdigest()

def load_data(csv_path: str, model: dict, db_config: dict, schema: str = "data_vault") -> list[str]:
    logs = []
    # Читаем CSV
    df = pd.read_csv(csv_path, dtype=str).fillna("") 
    
    try:
        conn = psycopg.connect(**db_config, autocommit=False) # Отключаем autocommit для транзакций
    except Exception as e:
        return [f"❌ Ошибка БД: {e}"]

    source_name = csv_path.split('/')[-1].split('\\')[-1]
    load_date = datetime.now().isoformat()
    
    with conn:
        with conn.cursor() as cur:
                        # 1. Загружаем Хабы
            for hub in model.get("hubs", []):
                if hub.get("source_file") != source_name: continue
                
                # МАГИЯ ЗДЕСЬ: оставляем только уникальные бизнес-ключи!
                # Если Вася сделал 3 заказа, в df останется только 1 строка с Васей.
                df_hub = df.drop_duplicates(subset=hub["business_keys"])
                
                insert_data = []
                for _, row in df_hub.iterrows(): # Итерируемся по очищенному df
                    bk_val = "".join([str(row.get(bk, "")) for bk in hub["business_keys"]])
                    hk = generate_hash(bk_val)
                    vals = [hk] + [row.get(bk, "") for bk in hub["business_keys"]] + [load_date, source_name]
                    insert_data.append(vals)
                
                if insert_data:
                    cols = ["hash_key"] + hub["business_keys"] + ["load_date", "record_source"]
                    placeholders = ", ".join(["%s"] * len(cols))
                    query = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
                        sql.Identifier(schema), sql.Identifier(hub['name']),
                        sql.SQL(', ').join(map(sql.Identifier, cols)), sql.SQL(placeholders)
                    )
                    cur.executemany(query, insert_data)
                    logs.append(f"✅ Загружен хаб: {hub['name']} (уникальных ключей: {len(insert_data)})")

            # 2. Загружаем Сателлиты
            for sat in model.get("satellites", []):
                if sat.get("source_file") != source_name: continue
                
                parent_hub = next((h for h in model.get("hubs", []) if h["name"] == sat["parent"]), None)
                if not parent_hub: continue
                
                # МАГИЯ ЗДЕСЬ: оставляем уникальные комбинации ключа и атрибутов
                subset_cols = parent_hub["business_keys"] + sat["attributes"]
                df_sat = df.drop_duplicates(subset=subset_cols)
                
                insert_data = []
                for _, row in df_sat.iterrows(): # Итерируемся по очищенному df
                    bk_val = "".join([str(row.get(bk, "")) for bk in parent_hub["business_keys"]])
                    hk = generate_hash(bk_val)
                    attr_vals = [str(row.get(attr, "")) for attr in sat["attributes"]]
                    diff_hash = generate_hash("".join(attr_vals))
                    vals = [hk, diff_hash] + attr_vals + [load_date, source_name]
                    insert_data.append(vals)
                
                if insert_data:
                    cols = [f"{parent_hub['name']}_hash_key", "hash_diff"] + sat["attributes"] + ["load_date", "record_source"]
                    placeholders = ", ".join(["%s"] * len(cols))
                    query = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({})").format(
                        sql.Identifier(schema), sql.Identifier(sat['name']),
                        sql.SQL(', ').join(map(sql.Identifier, cols)), sql.SQL(placeholders)
                    )
                    cur.executemany(query, insert_data)
                    logs.append(f"✅ Загружен сателлит: {sat['name']} (строк: {len(insert_data)})")

            conn.commit() # Фиксируем транзакцию разом

    conn.close()
    return logs