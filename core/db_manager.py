import psycopg
from psycopg import errors

def execute_sql(host: str, port: int, dbname: str, user: str, password: str, sql_script: str) -> list[str]:
    """
    Выполняет SQL скрипт и возвращает список логов (успехи/ошибки).
    """
    logs = []
    
    # Разделяем скрипт на отдельные команды по точке с запятой
    # (В нашем генераторе это безопасно, так как нет процедур и сложных функций)
    commands = [cmd.strip() for cmd in sql_script.split(";") if cmd.strip()]
    
    try:
        # Подключаемся к базе
        conn = psycopg.connect(
            host=host, port=port, dbname=dbname, 
            user=user, password=password, autocommit=True
        )
    except Exception as e:
        return [f"❌ Ошибка подключения к БД: {e}"]

    with conn:
        with conn.cursor() as cur:
            for cmd in commands:
                if not cmd: continue
                
                # Для красоты лога вытаскиваем первые 50 символов команды
                short_cmd = " ".join(cmd.split())[:60] + "..."
                
                try:
                    cur.execute(cmd)
                    logs.append(f"✅ Успешно: {short_cmd}")
                except errors.DuplicateTable:
                    logs.append(f"⚠️ Пропущено (таблица уже существует): {short_cmd}")
                except errors.DuplicateSchema:
                    logs.append(f"⚠️ Пропущено (схема уже существует): {short_cmd}")
                except Exception as e:
                    logs.append(f"❌ Ошибка при выполнении: {short_cmd}\n   Детали: {e}")
                    
    conn.close()
    return logs