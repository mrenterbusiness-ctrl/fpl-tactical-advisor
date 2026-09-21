# -*- coding: utf-8 -*-
"""
FPL Advisor — الخادم الرئيسي للتطبيق (Flask Web Application)
"""

import os
from flask import Flask, jsonify, request, send_from_directory
import fpl_engine as engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")


@app.route("/")
def index():
    resp = send_from_directory(app.static_folder, "index.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@app.route("/manifest.json")
def manifest():
    return send_from_directory(app.static_folder, "manifest.json", mimetype="application/json")


@app.route("/sw.js")
def service_worker():
    resp = send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 أسمع مني — مستشار فانتازي الدوري الإنجليزي الذكي")
    print(f"👨‍💻 إنشاء وتطوير: أحمد سعيد")
    print(f"🌐 شغال على الرابط: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
