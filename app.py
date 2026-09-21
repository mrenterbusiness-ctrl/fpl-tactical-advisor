# -*- coding: utf-8 -*-
"""
FPL Advisor — الخادم الرئيسي للتطبيق (Flask Web Application)
"""

import os
from flask import Flask, jsonify, request, send_from_directory, Response
import fpl_engine as engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = os.path.join(os.getcwd(), "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")


@app.route("/")
@app.route("/index.html")
@app.route("/api/index.py")
def index():
    html_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        return Response(content, mimetype="text/html; charset=utf-8", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/manifest.json")
def manifest():
    p = os.path.join(STATIC_DIR, "manifest.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return Response(f.read(), mimetype="application/json; charset=utf-8")
    return send_from_directory(STATIC_DIR, "manifest.json")


@app.route("/sw.js")
def service_worker():
    p = os.path.join(STATIC_DIR, "sw.js")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return Response(f.read(), mimetype="application/javascript; charset=utf-8", headers={"Service-Worker-Allowed": "/"})
    return send_from_directory(STATIC_DIR, "sw.js")


@app.route("/api/overview")
def api_overview():
    """معلومات الجولة القادمة، ميعاد الديدلاين، ومباريات الأسبوع"""
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
                next_event = {
                    "id": ev["id"],
                    "name": ev["name"],
                    "deadline_time": ev["deadline_time"]
                }
                break
                
        return jsonify({
            "current_gw": current_gw,
            "next_gw": next_gw,
            "next_event": next_event,
            "fixtures": gw_fixtures,
            "total_players": boot.get("total_players", 0)
        })
    except Exception as e:
        import demo_data
        return jsonify({
            "current_gw": 4,
            "next_gw": 5,
            "next_event": {"id": 5, "name": "Gameweek 5", "deadline_time": "2026-09-19T10:00:00Z"},
            "fixtures": demo_data.DEMO_FIXTURES,
            "total_players": 650
        })


@app.route("/api/team/<int:team_id>")
def api_team(team_id):
    """جلب التشكيلة والملخص والخطط الـ 5 لمعرّف الفريق"""
    try:
        api_key = request.args.get("api_key") or request.headers.get("X-API-Key") or os.environ.get("GEMINI_API_KEY")
        data = engine.fetch_user_team(team_id, api_key=api_key)
        if "error" in data:
            return jsonify(data), 404
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": "fetch_error", "message": f"حصل خطأ في جلب بيانات الفرقة: {str(e)}"}), 500


@app.route("/<path:subpath>")
def catch_all(subpath):
    target = os.path.join(STATIC_DIR, subpath)
    if os.path.isfile(target):
        return send_from_directory(STATIC_DIR, subpath)
    return index()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 أسمع مني — مستشار فانتازي الدوري الإنجليزي الذكي")
    print(f"👨‍💻 إنشاء وتطوير: أحمد سعيد")
    print(f"🌐 شغال على الرابط: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
