"""Live web view of orbit.db, meant to sit beside the app during a demo.

Usage: python scripts/dbview/server.py [--db orbit.db] [--port 8899]
"""

import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).parent
DB = HERE.parents[1] / "orbit.db"


def get_db_con(readonly: bool = True):
    if readonly:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    else:
        con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    return con


def query(sql, args=()):
    try:
        con = get_db_con(readonly=True)
        try:
            return [dict(row) for row in con.execute(sql, args)]
        finally:
            con.close()
    except sqlite3.Error as exc:
        return [{"error": str(exc)}]


def clear_history():
    try:
        con = get_db_con(readonly=False)
        with con:
            con.execute("DELETE FROM attempts")
            con.execute("DELETE FROM audit_log")
            con.execute("DELETE FROM reported_problems")
        con.close()
        return {"status": "ok", "message": "Demo attempts and audit logs cleared."}
    except Exception as exc:
        return {"error": str(exc)}


def snapshot(profile_id: str | None = None):
    profiles = query("SELECT id, name, age FROM child_profiles ORDER BY name")

    if profile_id:
        mastery_rows = query(
            "SELECT p.name AS child_name, sm.skill_id, sm.difficulty_vector, sm.updated_at "
            "FROM subject_mastery sm JOIN child_profiles p ON sm.profile_id = p.id "
            "WHERE sm.profile_id = ? ORDER BY sm.skill_id",
            (profile_id,),
        )
        attempts_rows = query(
            "SELECT a.id, a.profile_id, p.name AS child_name, a.operands, a.operator, a.answer_given, "
            "a.correct_answer, a.is_correct, a.error_class, a.tier_key, a.latency_to_submit_ms, "
            "a.difficulty_vector_snapshot, a.cursor_velocity_px_s, a.jitter_ratio, a.idle_time_ms, "
            "a.distraction_events, a.focus_score, a.is_synthetic, a.created_at "
            "FROM attempts a LEFT JOIN child_profiles p ON a.profile_id = p.id "
            "WHERE a.profile_id = ? ORDER BY a.created_at DESC LIMIT 20",
            (profile_id,),
        )
    else:
        mastery_rows = query(
            "SELECT p.name AS child_name, sm.skill_id, sm.difficulty_vector, sm.updated_at "
            "FROM subject_mastery sm JOIN child_profiles p ON sm.profile_id = p.id "
            "ORDER BY p.name, sm.skill_id"
        )
        attempts_rows = query(
            "SELECT a.id, a.profile_id, p.name AS child_name, a.operands, a.operator, a.answer_given, "
            "a.correct_answer, a.is_correct, a.error_class, a.tier_key, a.latency_to_submit_ms, "
            "a.difficulty_vector_snapshot, a.cursor_velocity_px_s, a.jitter_ratio, a.idle_time_ms, "
            "a.distraction_events, a.focus_score, a.is_synthetic, a.created_at "
            "FROM attempts a LEFT JOIN child_profiles p ON a.profile_id = p.id "
            "ORDER BY a.created_at DESC LIMIT 20"
        )

    return {
        "profiles": profiles,
        "active_profile_id": profile_id,
        "mastery": mastery_rows,
        "attempts": attempts_rows,
        "counts": query(
            "SELECT (SELECT count(*) FROM attempts) AS attempts,"
            " (SELECT count(*) FROM development_notes) AS notes,"
            " (SELECT count(*) FROM reported_problems) AS problems,"
            " (SELECT count(*) FROM audit_log) AS audit,"
            " (SELECT count(*) FROM games) AS games,"
            " (SELECT count(*) FROM child_profiles) AS profiles"
        )[0],
        "notes": query(
            "SELECT dn.id, p.name AS child_name, dn.author, dn.note, dn.created_at "
            "FROM development_notes dn LEFT JOIN child_profiles p ON dn.profile_id = p.id "
            "ORDER BY dn.created_at DESC LIMIT 6"
        ),
        "problems": query(
            "SELECT id, description, created_at FROM reported_problems "
            "ORDER BY created_at DESC LIMIT 6"
        ),
        "audit": query(
            "SELECT id, actor, action, payload, created_at FROM audit_log "
            "ORDER BY created_at DESC LIMIT 8"
        ),
    }


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path.startswith("/clear-history") or self.path.startswith("/reset"):
            result = clear_history()
            body = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/clear-history"):
            result = clear_history()
            body = json.dumps(result).encode()
            ctype = "application/json"
        elif parsed.path.startswith("/data"):
            params = parse_qs(parsed.query)
            pid = params.get("profile_id", [None])[0]
            body = json.dumps(snapshot(profile_id=pid)).encode()
            ctype = "application/json"
        else:
            body = (HERE / "index.html").read_bytes()
            ctype = "text/html; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    global DB
    parser = argparse.ArgumentParser(description="Live web view of orbit.db")
    parser.add_argument("--db", type=Path, default=DB, help="path to the SQLite file")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="host to bind to")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()
    DB = args.db
    print(f"orbit.db view on http://{args.host}:{args.port} (reading {DB})")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

