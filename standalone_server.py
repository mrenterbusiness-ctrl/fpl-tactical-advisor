# -*- coding: utf-8 -*-
"""
FPL Advisor — سيرفر التشغيل المستقل المحمي من أخطاء المنافذ
"""

import os
import sys
import json
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
import fpl_engine as engine

try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


class FPLHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        url_path = self.path.split("?")[0]
        
        if url_path == "/" or url_path == "/index.html":
            self.serve_static("index.html", "text/html; charset=utf-8")
            return

        if url_path == "/manifest.json":
            self.serve_static("manifest.json", "application/json; charset=utf-8")
            return

        if url_path == "/sw.js":
            self.serve_static("sw.js", "application/javascript; charset=utf-8")
            return

        if url_path == "/api/overview":
            try:
                boot = engine.get_bootstrap()
                fixtures_data = engine.get_fixtures()
                current_gw, next_gw = engine.get_current_and_next_gw(boot)
                teams = {t["id"]: t for t in boot.get("teams", [])}
                gw_fixtures = engine.get_gw_fixtures(fixtures_data, next_gw, teams)
                events = boot.get("events", [])
                next_event = None
                for ev in events:
                    if ev.get("id") == next_gw:
                        next_event = {"id": ev["id"], "name": ev["name"], "deadline_time": ev["deadline_time"]}
                        break
                self.send_json({
                    "current_gw": current_gw,
                    "next_gw": next_gw,
                    "next_event": next_event,
                    "fixtures": gw_fixtures,
                    "total_players": boot.get("total_players", 0)
                })
            except Exception as e:
                import demo_data
                self.send_json({
                    "current_gw": 4,
                    "next_gw": 5,
                    "next_event": {"id": 5, "name": "Gameweek 5", "deadline_time": "2026-09-19T10:00:00Z"},
                    "fixtures": demo_data.DEMO_FIXTURES,
                    "total_players": 650
                })
            return

        if url_path.startswith("/api/team/"):
            parts = url_path.strip("/").split("/")
            if len(parts) == 3 and parts[2].isdigit():
                team_id = int(parts[2])
                try:
                    from urllib.parse import parse_qs, urlparse
                    query_params = parse_qs(urlparse(self.path).query)
                    api_key = query_params.get("api_key", [None])[0] or self.headers.get("X-API-Key") or os.environ.get("GEMINI_API_KEY")
                    data = engine.fetch_user_team(team_id, api_key=api_key)
                    if "error" in data:
                        self.send_json(data, status=404)
                    else:
                        self.send_json(data)
                except Exception as e:
                    self.send_json({"error": "fetch_error", "message": str(e)}, status=500)
                return

        rel_path = url_path.lstrip("/")
        static_file = os.path.join(os.path.dirname(__file__), "static", rel_path)
        if os.path.exists(static_file) and os.path.isfile(static_file):
            mime_type, _ = mimetypes.guess_type(static_file)
            self.serve_static(rel_path, mime_type or "application/octet-stream")
            return

        self.send_error(404, "Not Found")

    def serve_static(self, filename, content_type):
        path = os.path.join(os.path.dirname(__file__), "static", filename)
        if not os.path.exists(path):
            self.send_error(404, "File not found")
            return
        with open(path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def run(port=8000, start_port=None):
    start_port = start_port or port
    env_port = os.environ.get("PORT")
    ports_to_try = [int(env_port)] if env_port else [start_port, 8001, 8080, 8888, 5000]
    httpd = None
    chosen_port = None

    for p in ports_to_try:
        try:
            server_address = ("0.0.0.0", p)
            httpd = ReusableHTTPServer(server_address, FPLHandler)
            chosen_port = p
            break
        except OSError:
            continue

    if not httpd:
        raise RuntimeError("المنافذ (8000, 8001, 8080) مشغولة ببرامج أخرى. برجاء إغلاق أي سيرفر شغال وجرب تاني.")

    print("\n" + "=" * 58)
    print(" 🏆 أسمع مني — مستشار فانتازي الدوري الإنجليزي الذكي")
    print(" 👨‍💻 إنشاء وتطوير: أحمد سعيد")
    print(f" 🌐 افتح المتصفح على: http://localhost:{chosen_port}")
    print("=" * 58)
    print(" 💡 نصيحة: لو الشاشة دي قفلت، السيرفر هيقفل. سيبها مفتوحة في الخلفية.")
    print(" ⏹️ لإيقاف السيرفر: اضغط Ctrl + C في الشاشة دي.")
    print("=" * 58 + "\n")

    # محاولة فتح المتصفح أوتوماتيكياً في البيئة المحلية فقط
    if not os.environ.get("PORT"):
        try:
            import webbrowser
            webbrowser.open(f"http://localhost:{chosen_port}")
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nتم إيقاف السيرفر بنجاح.")
        sys.exit(0)


if __name__ == "__main__":
    try:
        run()
    except Exception as err:
        print(f"\n❌ حدث خطأ أثناء تشغيل السيرفر:\n{err}\n")
        try:
            input("اضغط Enter للخروج...")
        except Exception:
            pass
