"""Live web view of orbit.db, meant to sit beside the app during a demo.

Usage: python scripts/dbview/server.py [--db orbit.db] [--port 8899]
"""

import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
DB = HERE.parents[1] / "orbit.db"


def query(sql, args=()):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in con.execute(sql, args)]
    except sqlite3.Error as exc:
        return [{"error": str(exc)}]
    finally:
        con.close()


def snapshot():
    return {
        "mastery": query(
            "select skill_id, difficulty_vector, updated_at from subject_mastery"
            " order by skill_id"
        ),
        "attempts": query(
            "select id, operands, operator, answer_given, correct_answer, is_correct,"
            " error_class, tier_key, latency_to_submit_ms, difficulty_vector_snapshot,"
            " cursor_velocity_px_s, jitter_ratio, idle_time_ms, distraction_events,"
            " focus_score, is_synthetic, created_at from attempts"
            " order by created_at desc limit 12"
        ),
        "counts": query(
            "select (select count(*) from attempts) as attempts,"
            " (select count(*) from development_notes) as notes,"
            " (select count(*) from reported_problems) as problems,"
            " (select count(*) from audit_log) as audit,"
            " (select count(*) from games) as games"
        )[0],
        "notes": query(
            "select id, author, note, created_at from development_notes"
            " order by created_at desc limit 4"
        ),
        "problems": query(
            "select id, description, created_at from reported_problems"
            " order by created_at desc limit 4"
        ),
        "audit": query(
            "select id, actor, action, payload, created_at from audit_log"
            " order by created_at desc limit 8"
        ),
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/data"):
            body = json.dumps(snapshot()).encode()
            ctype = "application/json"
        else:
            body = (HERE / "index.html").read_bytes()
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    global DB
    parser = argparse.ArgumentParser(description="Live web view of orbit.db")
    parser.add_argument("--db", type=Path, default=DB, help="path to the SQLite file")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()
    DB = args.db
    print(f"orbit.db view on http://127.0.0.1:{args.port} (reading {DB})")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
