# update_cache.py
# Genera el cache usando compute_rows() y games_played_today_scl() del módulo standings_*
import json, os, sys, time
from datetime import datetime
from zoneinfo import ZoneInfo

# --- Import robusto del módulo principal ---
try:
    import standings_cascade_points_desc as standings
except Exception:
    import standings_cascade_points as standings  # fallback si el nombre no tiene _desc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, "standings_cache.json")
SCL = ZoneInfo("America/Santiago")

# --- Lista de exclusiones manuales ---
EXCLUDE_STRINGS = {
    "Yankees 0 - 0 Mets - 08-09-2025 - 9:40 pm (hora Chile)",
}

EXCLUDE_RULES = [
    {
        "home_team": "Yankees",
        "away_team": "Mets",
        "home_score": 0,
        "away_score": 0,
        "ended_at_local_contains": "08-09-2025 - 9:40"
    }
]

def _should_exclude_game(g):
    if isinstance(g, str):
        return g.strip() in EXCLUDE_STRINGS

    if isinstance(g, dict):
        for rule in EXCLUDE_RULES:
            ok = True
            for k, v in rule.items():
                if k == "ended_at_local_contains":
                    if v not in (g.get("ended_at_local") or ""):
                        ok = False
                        break
                else:
                    if g.get(k) != v:
                        ok = False
                        break
            if ok:
                return True
    return False

# ==========================
# Playoffs (manual por ahora)
# ==========================
def build_playoffs(standings):
    top8 = standings[:8]
    if len(top8) < 8:
        return {}

    series = {
        "QF1": {"teams": [top8[0]["team"], top8[7]["team"]], "games": []},
        "QF2": {"teams": [top8[1]["team"], top8[6]["team"]], "games": []},
        "QF3": {"teams": [top8[2]["team"], top8[5]["team"]], "games": []},
        "QF4": {"teams": [top8[3]["team"], top8[4]["team"]], "games": []},
        "SF1": {"teams": ["Ganador QF1", "Ganador QF4"], "games": []},
        "SF2": {"teams": ["Ganador QF2", "Ganador QF3"], "games": []},
        "Final": {"teams": ["Ganador SF1", "Ganador SF2"], "games": []},
    }
    return series

# ==========================
# Historial acumulado
# ==========================
def build_games_history():
    """
    Devuelve un listado acumulado de todos los juegos jugados (no solo hoy).
    """
    try:
        games = standings.games_played_today_scl()
    except Exception:
        games = []
    # Aplicar exclusiones manuales
    games = [g for g in games if not _should_exclude_game(g)]
    return games

# ==========================
# Cache principal
# ==========================
def update_data_cache():
    ts = datetime.now(SCL).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] Iniciando actualización del cache...")

    try:
        if not hasattr(standings, "compute_rows"):
            raise AttributeError("El módulo no define compute_rows()")
        if not hasattr(standings, "games_played_today_scl"):
            raise AttributeError("El módulo no define games_played_today_scl()")

        # 1) Tabla
        rows = standings.compute_rows()

        # 2) Historial acumulado
        games_history = build_games_history()

        # 3) Construir bloque de playoffs (manual por ahora)
        playoffs = build_playoffs(rows)

        # 4) Escribir cache
        payload = {
            "standings": rows,
            "games_history": games_history,
            "last_updated": ts,
            "playoffs": playoffs
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        print("Actualización completada exitosamente.")
        return True
    except Exception as e:
        print(f"ERROR durante la actualización del cache: {e}")
        return False

def _run_once_then_exit():
    ok = update_data_cache()
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    if "--once" in sys.argv or os.getenv("RUN_ONCE") == "1":
        _run_once_then_exit()

    UPDATE_INTERVAL_SECONDS = int(os.getenv("UPDATE_INTERVAL_SECONDS", "300"))
    while True:
        update_data_cache()
        print(f"Esperando {UPDATE_INTERVAL_SECONDS} segundos para la próxima actualización...")
        try:
            time.sleep(UPDATE_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("Detenido por el usuario.")
            break
