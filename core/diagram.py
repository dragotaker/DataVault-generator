import math
import plotly.graph_objects as go


# ---------- Диаграмма 1: связи между файлами ----------

def render_source_fks_diagram(profiles: list[dict], fks: list[dict]) -> go.Figure:
    if not profiles:
        return go.Figure()

    files = [p["file"] for p in profiles]
    n = len(files)
    positions = {}
    for i, f in enumerate(files):
        angle = 2 * math.pi * i / n - math.pi / 2
        positions[f] = (3.0 * math.cos(angle), 3.0 * math.sin(angle))

    fig = go.Figure()

    # Рёбра
    for fk in fks:
        p_from = positions.get(fk["child_file"])
        p_to = positions.get(fk["parent_file"])
        if not p_from or not p_to: continue

        color = "#F5A623" if fk["kind"] == "lookup" else "#9AA4AE"
        dash = "dot" if fk["kind"] == "lookup" else "solid"

        fig.add_trace(go.Scatter(
            x=[p_from[0], p_to[0]], y=[p_from[1], p_to[1]],
            mode="lines",
            line=dict(color=color, width=2, dash=dash),
            hovertext=f"{fk['child_file']}.{fk['child_col']} → "
                      f"{fk['parent_file']}.{fk['parent_col']} "
                      f"({fk['overlap']*100:.0f}%)",
            hoverinfo="text", showlegend=False,
        ))

    # Узлы-файлы
    fig.add_trace(go.Scatter(
        x=[positions[f][0] for f in files],
        y=[positions[f][1] for f in files],
        mode="markers+text",
        marker=dict(size=44, color="#4A90E2",
                    line=dict(color="#2C5F8A", width=2)),
        text=files, textposition="bottom center",
        hovertext=[f"{p['file']}<br>{p['row_count']} строк, "
                   f"{p['column_count']} колонок" for p in profiles],
        hoverinfo="text", showlegend=False,
    ))

    fig.update_layout(
        title=f"Обнаруженные связи ({len(fks)})",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-4.5, 4.5]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-4.5, 4.5]),
        plot_bgcolor="white", height=600,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


# ---------- Диаграмма 2: модель Data Vault ----------

def render_dv_diagram(model: dict) -> go.Figure:
    if not model or not any(model.get(k) for k in ("hubs", "links", "satellites")):
        return go.Figure()

    hubs = model.get("hubs", [])
    links = model.get("links", [])
    sats = model.get("satellites", [])

    positions = {}
    for i, h in enumerate(hubs):
        positions[h["name"]] = (0.0, -i * 1.5)
    for i, l in enumerate(links):
        positions[l["name"]] = (1.6, -i * 1.5 - 0.5)
    for i, s in enumerate(sats):
        positions[s["name"]] = (3.2, -i * 1.2)

    fig = go.Figure()
    edge_color = "#CCCCCC"

    for sat in sats:
        parent = sat.get("parent")
        if parent in positions and sat["name"] in positions:
            p1, p2 = positions[parent], positions[sat["name"]]
            fig.add_trace(go.Scatter(
                x=[p1[0], p2[0]], y=[p1[1], p2[1]],
                mode="lines", line=dict(color=edge_color, width=1),
                hoverinfo="skip", showlegend=False,
            ))

    for lnk in links:
        if lnk["name"] not in positions: continue
        p_link = positions[lnk["name"]]
        for h in lnk.get("hubs", []):
            if h in positions:
                p_hub = positions[h]
                fig.add_trace(go.Scatter(
                    x=[p_hub[0], p_link[0]], y=[p_hub[1], p_link[1]],
                    mode="lines",
                    line=dict(color=edge_color, width=1, dash="dash"),
                    hoverinfo="skip", showlegend=False,
                ))

    if hubs:
        fig.add_trace(go.Scatter(
            x=[positions[h["name"]][0] for h in hubs],
            y=[positions[h["name"]][1] for h in hubs],
            mode="markers+text",
            marker=dict(size=40, color="#4A90E2", symbol="square"),
            text=[h["name"] for h in hubs], textposition="middle left",
            hovertext=[f"Hub {h['name']}<br>BK: {', '.join(h.get('business_keys', []))}"
                       for h in hubs],
            hoverinfo="text", name="Hubs",
        ))

    if links:
        fig.add_trace(go.Scatter(
            x=[positions[l["name"]][0] for l in links],
            y=[positions[l["name"]][1] for l in links],
            mode="markers+text",
            marker=dict(size=35, color="#F5A623", symbol="diamond"),
            text=[l["name"] for l in links], textposition="middle right",
            hovertext=[f"Link {l['name']}<br>Between: {', '.join(l.get('hubs', []))}"
                       for l in links],
            hoverinfo="text", name="Links",
        ))

    if sats:
        fig.add_trace(go.Scatter(
            x=[positions[s["name"]][0] for s in sats],
            y=[positions[s["name"]][1] for s in sats],
            mode="markers+text",
            marker=dict(size=28, color="#7ED321", symbol="circle"),
            text=[s["name"] for s in sats], textposition="middle right",
            hovertext=[f"Satellite {s['name']}<br>Parent: {s['parent']}"
                       f"<br>Attrs: {', '.join(s.get('attributes', []))}"
                       for s in sats],
            hoverinfo="text", name="Satellites",
        ))

    fig.update_layout(
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-1, 5]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor="white",
        height=max(500, (len(hubs) + len(links) + len(sats)) * 35 + 100),
        margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig