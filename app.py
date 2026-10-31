import gradio as gr
import pandas as pd
import json
from core.profiler import profile_csv, detect_fks, strip_internal
from agents.builder import build_model
from core.model_validator import validate_model
from core.sql_generator import generate_sql
from core.db_manager import execute_sql
from core.diagram import render_source_fks_diagram, render_dv_diagram

STATE = {"profiles": [], "fks": [], "model": {}, "sql": ""}


def step1_analyze(files):
    if not files:
        return "Файлы не выбраны", pd.DataFrame(), None

    profiles = []
    for f in files:
        path = f.name if hasattr(f, "name") else f
        profiles.append(profile_csv(path))

    fks = detect_fks(profiles)
    STATE["profiles"] = profiles
    STATE["fks"] = fks

    rows = []
    for p in profiles:
        for c in p["columns"]:
            rows.append([
                p["file"], c["name"], c["semantic_type"],
                f"{c['null_pct']*100:.1f}%",
                c["distinct_count"], c["grain_hint"],
                "✓" if c["is_pk_candidate"] else "",
            ])
    df = pd.DataFrame(rows, columns=[
        "Файл", "Колонка", "Тип", "Null %",
        "Уникальных", "Grain", "PK?",
    ])
    diagram = render_source_fks_diagram(profiles, fks)
    status = (f"✅ Файлов: {len(profiles)}. "
              f"Связей: {len(fks)} "
              f"(из них lookup: {sum(1 for x in fks if x['kind'] == 'lookup')}).")
    return status, df, diagram


def step2_build():
    if not STATE["profiles"]:
        return "Сначала загрузите файлы", "{}", None
    try:
        model = build_model(strip_internal(STATE["profiles"]), STATE["fks"])
        STATE["model"] = model
        return ("✅ LLM сгенерировала модель",
                json.dumps(model, indent=2, ensure_ascii=False),
                render_dv_diagram(model))
    except Exception as e:
        return f"❌ Ошибка LLM: {e}", "{}", None


def step3_validate(json_text):
    if not json_text:
        return "Модель пуста", ""
    try:
        STATE["model"] = json.loads(json_text)
    except json.JSONDecodeError as e:
        return "❌ Ошибка синтаксиса JSON", str(e)

    errors = validate_model(STATE["model"], strip_internal(STATE["profiles"]))
    if errors:
        return "❌ Найдены ошибки:", "\n".join(f"- {e}" for e in errors)
    return "✅ Валидация пройдена", "Все правила соблюдены."


def step4_generate():
    if not STATE["model"]:
        return "Сначала сгенерируйте модель"
    sql = generate_sql(STATE["model"], strip_internal(STATE["profiles"]),
                       schema="data_vault")
    STATE["sql"] = sql
    return sql


def step5_deploy(host, port, dbname, user, password, sql_text):
    if not sql_text:
        return "Сначала сгенерируйте SQL"
    if not password:
        return "❌ Введите пароль"
    try:
        logs = execute_sql(host, int(port), dbname, user, password, sql_text)
        ok = sum(1 for line in logs if line.startswith("✅"))
        return f"📊 Создано объектов: {ok}\n\n" + "\n".join(logs)
    except Exception as e:
        return f"❌ Ошибка: {e}"


with gr.Blocks(title="Vault Designer") as demo:
    gr.Markdown("# Vault Designer\n*CSV → Data Vault 2.0 DDL*")

    with gr.Tab("1. Источники"):
        with gr.Row():
            file_input = gr.File(label="CSV", file_count="multiple",
                                 file_types=[".csv"])
            analyze_btn = gr.Button("Анализировать", variant="primary")
        status1 = gr.Textbox(label="Статус", interactive=False)
        with gr.Tabs():
            with gr.Tab("Метаданные"):
                table_output = gr.Dataframe(label="Колонки")
            with gr.Tab("Диаграмма связей"):
                fk_diagram = gr.Plot()
        analyze_btn.click(step1_analyze, inputs=file_input,
                          outputs=[status1, table_output, fk_diagram])

    with gr.Tab("2. Модель (LLM)"):
        build_btn = gr.Button("Сгенерировать модель", variant="primary")
        status2 = gr.Textbox(label="Статус", interactive=False)
        with gr.Tabs():
            with gr.Tab("JSON"):
                json_output = gr.Code(language="json", interactive=True)
            with gr.Tab("Диаграмма DV"):
                dv_diagram = gr.Plot()
        build_btn.click(step2_build,
                        outputs=[status2, json_output, dv_diagram])

    with gr.Tab("3. Валидация"):
        validate_btn = gr.Button("Проверить модель", variant="primary")
        status3 = gr.Textbox(label="Результат", interactive=False)
        validation_log = gr.Textbox(label="Детали", interactive=False)
        validate_btn.click(step3_validate, inputs=json_output,
                           outputs=[status3, validation_log])

    with gr.Tab("4. SQL (PostgreSQL)"):
        gen_btn = gr.Button("Сгенерировать DDL", variant="primary")
        sql_output = gr.Code(language="sql", interactive=True)
        gen_btn.click(step4_generate, outputs=sql_output)

        gr.Markdown("### Выполнить в PostgreSQL")
        with gr.Row():
            db_host = gr.Textbox(label="Host", value="localhost")
            db_port = gr.Textbox(label="Port", value="5432")
            db_name = gr.Textbox(label="Database", value="postgres")
        with gr.Row():
            db_user = gr.Textbox(label="User", value="postgres")
            db_pass = gr.Textbox(label="Password", type="password")
        deploy_btn = gr.Button("🚀 Выполнить SQL", variant="stop")
        deploy_status = gr.Textbox(label="Результат", lines=12)
        deploy_btn.click(step5_deploy,
                         inputs=[db_host, db_port, db_name, db_user,
                                 db_pass, sql_output],
                         outputs=deploy_status)


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)