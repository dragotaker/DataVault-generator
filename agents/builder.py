import json
from core.llm_client import LLMClient

SYSTEM_PROMPT = """Ты — эксперт по Data Vault 2.0. На вход ты получаешь метаданные CSV и найденные связи.
Твоя задача — спроектировать строгую модель Data Vault 2.0.

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:
1. ХАБЫ (Hubs):
   - Создавай ТОЛЬКО для независимых бизнес-сущностей (клиенты, заказы, товары, продавцы).
   - Колонка бизнес-ключа должна иметь grain_hint = "one_row_per_value" или быть родителем в связи [FK].
   - ЗАПРЕЩЕНО создавать хабы для справочников (например, geolocation_zip_code_prefix) или транзакционных событий (например, отзывы).

2. СВЯЗИ (Links):
   - Создавай Линки для обычных связей [FK] между двумя хабами.
   - ВАЖНО (Транзакционные линки): Если файл (например, order_items) содержит несколько FK (order_id, product_id, seller_id) и числовые атрибуты (price), создай ОДИН Линк (например, lnk_order_items), объединяющий все эти хабы. Числовые атрибуты вынеси в Сателлит Линка (lsat_order_items).
   - Связи типа [LOOKUP] (например, к geolocation) НЕ создают Линк.

3. САТЕЛЛИТЫ (Satellites):
   - hsat_[хаб]_main — для описательных атрибутов хаба.
   - lsat_[линк]_main — для атрибутов транзакции (цена, количество, статус).
   - ВАЖНО (Lookup-атрибуты): Если в правилах есть связь [LOOKUP] (например, customer -> geolocation), НЕ создавай хаб для геолокации. Добавь атрибуты из geolocation (lat, lng, city, state) прямо в Сателлит клиента (hsat_customer_main).

4. ДОПОЛНИТЕЛЬНО:
   - Если сущность (например, отзыв review) не имеет своего бизнес-ключа, но привязана к заказу, создай для нее lsat_order_review.
   - Используй ТОЛЬКО колонки из метаданных. Не выдумывай имена.

Формат JSON:
{
  "hubs": [{"name": "hub_xxx", "business_keys": ["col1"], "source_file": "file.csv"}],
  "links": [{"name": "lnk_xxx_yyy", "hubs": ["hub_xxx", "hub_yyy"], "source_file": "file.csv"}],
  "satellites": [{"name": "hsat_xxx_main", "parent": "hub_xxx", "attributes": ["col2"], "source_file": "file.csv"}]
}
"""

def build_model(profiles: list[dict], fks: list[dict]) -> dict:
    client = LLMClient()
    context = "### Файлы и колонки:\n"
    # ... (код формирования контекста остается прежним, он хорош) ...
    for p in profiles:
        context += f"\n#### {p['file']} ({p['row_count']} строк)\n"
        for c in p["columns"]:
            marks = []
            if c["is_pk_candidate"]: marks.append("PK")
            if c["grain_hint"] == "one_row_per_value": marks.append("UNIQUE_GRAIN")
            mark_str = f" [{', '.join(marks)}]" if marks else ""
            context += f"- {c['name']} ({c['semantic_type']}){mark_str}\n"

    context += "\n### detected_relationships:\n"
    for fk in fks:
        context += f"- {fk['child_file']}.{fk['child_col']} -> {fk['parent_file']}.{fk['parent_col']} [{fk['kind'].upper()}]\n"

    user_prompt = f"Спроектируй модель Data Vault:\n{context}"
    return client.generate_json(SYSTEM_PROMPT, user_prompt)