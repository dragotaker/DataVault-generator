import warnings
import pandas as pd
from pathlib import Path

INT_TYPES = {"int8", "int16", "int32", "int64",
             "uint8", "uint16", "uint32", "uint64"}
FLOAT_TYPES = {"float16", "float32", "float64"}

MAX_SET_FOR_FK = 100_000   # не храним сеты больше — жрёт память
MAX_DISTINCT_FK = 200_000  # не детектим FK у колонок с огромной кардинальностью


def _semantic_type(series: pd.Series) -> str:
    dt = str(series.dtype)
    if dt in INT_TYPES: return "integer"
    if dt in FLOAT_TYPES: return "number"
    if dt == "bool": return "boolean"
    if dt.startswith("datetime"): return "datetime"

    non_null = series.dropna()
    if len(non_null) == 0: return "string"
    sample = non_null.astype(str).head(50)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            pd.to_datetime(sample, errors="raise")
            return "datetime"
        except (ValueError, TypeError):
            pass

    try:
        nums = pd.to_numeric(sample, errors="raise")
        if (nums % 1 == 0).all(): return "integer"
        return "number"
    except (ValueError, TypeError):
        pass
    return "string"


def profile_csv(path: str, sample_n: int = 5) -> dict:
    path_obj = Path(path)
    df = pd.read_csv(path_obj, low_memory=False)
    n = len(df)

    columns = []
    for col in df.columns:
        s = df[col]
        nulls = int(s.isna().sum())
        non_null = s.dropna()
        distinct = int(non_null.nunique())
        null_pct = nulls / n if n else 0.0
        distinct_pct = distinct / n if n else 0.0
        rows_per_value = n / distinct if distinct else 0.0
        is_unique = n > 0 and nulls == 0 and distinct == n

        # Grain — ключевая подсказка для LLM (хаб или линк)
        if rows_per_value < 1.05:
            grain = "one_row_per_value"
        elif rows_per_value < 10:
            grain = "few_rows_per_value"
        else:
            grain = "many_rows_per_value"

        # Набор значений для FK-детекции
        value_set = None
        if 2 <= distinct <= MAX_SET_FOR_FK:
            value_set = set(non_null.astype(str).head(MAX_SET_FOR_FK).tolist())

        columns.append({
            "name": str(col),
            "pandas_type": str(s.dtype),
            "semantic_type": _semantic_type(s),
            "null_count": nulls,
            "null_pct": round(null_pct, 4),
            "distinct_count": distinct,
            "distinct_pct": round(distinct_pct, 4),
            "rows_per_value": round(rows_per_value, 2),
            "grain_hint": grain,
            "samples": non_null.astype(str).head(sample_n).tolist(),
            "top_values": non_null.astype(str).value_counts().head(3).to_dict(),
            "is_pk_candidate": is_unique,
            "is_bk_candidate": (
                not is_unique and null_pct < 0.2 and distinct > 1
                and distinct_pct > 0.5
            ),
            "_value_set": value_set,
        })

    return {
        "file": path_obj.name,
        "row_count": int(n),
        "column_count": int(df.shape[1]),
        "columns": columns,
    }


def detect_fks(profiles: list[dict], min_overlap: float = 0.5) -> list[dict]:
    """
    Детерминированно ищет FK-связи между файлами по пересечению значений.
    Никакой LLM тут нет — только set intersection.
    """
    fks: list[dict] = []
    seen: set = set()

    def _skip(c):
        if not c.get("_value_set") or len(c["_value_set"]) < 2:
            return True
        if c["distinct_count"] > MAX_DISTINCT_FK:
            return True
        # float / datetime с почти уникальными значениями — не FK
        if c["semantic_type"] in ("number", "datetime") and c["distinct_pct"] > 0.9:
            return True
        return False

    for i, p1 in enumerate(profiles):
        for c1 in p1["columns"]:
            if _skip(c1): continue
            for j, p2 in enumerate(profiles):
                if i == j: continue
                for c2 in p2["columns"]:
                    if _skip(c2): continue

                    same_name = c1["name"] == c2["name"]

                    # Отсекаем явно несвязанные по кардинальности
                    if not same_name:
                        ratio = min(c1["distinct_count"], c2["distinct_count"]) / \
                                max(c1["distinct_count"], c2["distinct_count"])
                        if ratio < 0.8:
                            continue

                    overlap = len(c1["_value_set"] & c2["_value_set"]) / len(c1["_value_set"])
                    if overlap < min_overlap:
                        continue

                    # Дедуп (A→B и B→A)
                    k1 = (p1["file"], c1["name"], p2["file"], c2["name"])
                    k2 = (p2["file"], c2["name"], p1["file"], c1["name"])
                    if k1 in seen or k2 in seen: continue
                    seen.add(k1)

                    # Родитель — где кардинальность выше (или где PK)
                    if c1["distinct_count"] >= c2["distinct_count"]:
                        parent, child = (p2["file"], c2["name"]), (p1["file"], c1["name"])
                    else:
                        parent, child = (p1["file"], c1["name"]), (p2["file"], c2["name"])

                    # Классифицируем: справочник или FK
                    child_col_meta = c1 if child == (p1["file"], c1["name"]) else c2
                    kind = "lookup" if child_col_meta["distinct_count"] < 500 else "fk"

                    fks.append({
                        "parent_file": parent[0], "parent_col": parent[1],
                        "child_file": child[0], "child_col": child[1],
                        "overlap": round(overlap, 3),
                        "same_name": same_name,
                        "kind": kind,
                    })

    fks.sort(key=lambda x: (-x["same_name"], -x["overlap"]))
    return fks


def strip_internal(profiles: list[dict]) -> list[dict]:
    """Убирает _value_set перед JSON-сериализацией / отправкой в LLM."""
    import copy
    result = copy.deepcopy(profiles)
    for p in result:
        for c in p["columns"]:
            c.pop("_value_set", None)
    return result