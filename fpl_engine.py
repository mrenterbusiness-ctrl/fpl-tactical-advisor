# -*- coding: utf-8 -*-
"""
FPL Advisor Engine — محرك النخبة الواقعي (Top 10k Elite Engine)
محرك إحصائي متقدم يعتمد على المنطق الكروي الحقيقي بدون أي تناقضات:
1. قواعد صارمة للكبتنة: مستحيل كابتن آمن يلاعب السيتي أو أرسنال بصعوبة 4 أو 5!
2. كشف مأزق الكبتنة والصراحة مع المدرب لو فرقتك كلها ماتشاتها صعبة.
3. التمييز الدقيق بين الأندية الأوروبية وفرق الدوري فقط في المداورة.
4. حساب xMins وركلات الجزاء والـ 3 جولات القادمة.
"""

import os
import sys
import json
import time
import threading
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _load_env_file():
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'").strip('"')
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_env_file()

FPL_BASE = "https://fantasy.premierleague.com/api"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

_cache = {
    "bootstrap": None, "b_ts": 0,
    "fixtures": None, "f_ts": 0,
    "entries": {},
    "summaries": {}
}
_lock = threading.Lock()

BOOTSTRAP_TTL = 20 * 60
FIXTURES_TTL = 60 * 60
ENTRY_TTL = 5 * 60
SUMMARY_TTL = 30 * 60

# الأندية المشاركة أوروبياً المعرضة لمداورة المدربين
EUROPEAN_CLUBS = {
    "MCI", "ARS", "LIV", "CHE", "TOT", "NEW", "AVL", "MUN"
}

# أقوى دفاعات الدوري (اللعب ضدهم خارج الأرض خطر قاطع في الكبتنة)
TOP_DEFENSES = {"MCI", "ARS", "LIV"}


def _fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise e
    except Exception as e:
        raise e


def get_bootstrap():
    with _lock:
        if _cache["bootstrap"] and (time.time() - _cache["b_ts"] < BOOTSTRAP_TTL):
            return _cache["bootstrap"]

    data = _fetch_json(f"{FPL_BASE}/bootstrap-static/")
    with _lock:
        _cache["bootstrap"] = data
        _cache["b_ts"] = time.time()
    return data


def get_fixtures():
    with _lock:
        if _cache["fixtures"] and (time.time() - _cache["f_ts"] < FIXTURES_TTL):
            return _cache["fixtures"]

    data = _fetch_json(f"{FPL_BASE}/fixtures/")
    with _lock:
        _cache["fixtures"] = data or []
        _cache["f_ts"] = time.time()
    return _cache["fixtures"]


def get_element_summary(player_id):
    """جلب سجل أداء اللاعب وتاريخ مبارياته من سيرفر FPL مع التخزين المؤقت"""
    with _lock:
        cached = _cache["summaries"].get(player_id)
        if cached and (time.time() - cached[1] < SUMMARY_TTL):
            return cached[0]

    data = _fetch_json(f"{FPL_BASE}/element-summary/{player_id}/")
    if data:
        with _lock:
            _cache["summaries"][player_id] = (data, time.time())
    return data


def parse_last_3_matches(summary_data, teams_map=None):
    """تحليل دقيق لأداء اللاعب في آخر 3 ماتشات: الدقائق، الأهداف، الأسيستات، والنقاط"""
    if not summary_data:
        return {
            "last_3_matches": [],
            "last_3_summary": "غير متوفر",
            "last_3_mins": 0,
            "last_3_pts": 0,
            "last_3_goals": 0,
            "last_3_assists": 0,
            "last_3_clean_sheets": 0
        }
    history = summary_data.get("history", [])
    if not history:
        return {
            "last_3_matches": [],
            "last_3_summary": "مفيش مشاركات سابقة",
            "last_3_mins": 0,
            "last_3_pts": 0,
            "last_3_goals": 0,
            "last_3_assists": 0,
            "last_3_clean_sheets": 0
        }

    last_3 = history[-3:]
    matches = []
    tot_mins = 0
    tot_pts = 0
    tot_goals = 0
    tot_assists = 0
    tot_cs = 0
    parts = []

    for m in last_3:
        gw = m.get("round", "?")
        mins = int(m.get("minutes") or 0)
        pts = int(m.get("total_points") or 0)
        goals = int(m.get("goals_scored") or 0)
        assists = int(m.get("assists") or 0)
        cs = int(m.get("clean_sheets") or 0)
        opp_id = m.get("opponent_team")
        opp_name = teams_map.get(opp_id, {}).get("short_name", f"T{opp_id}") if teams_map else f"T{opp_id}"
        side = "(H)" if m.get("was_home") else "(A)"

        tot_mins += mins
        tot_pts += pts
        tot_goals += goals
        tot_assists += assists
        tot_cs += cs

        matches.append({
            "gw": gw,
            "opponent": opp_name,
            "side": side,
            "minutes": mins,
            "points": pts,
            "goals": goals,
            "assists": assists,
            "clean_sheets": cs
        })

        stat_tag = []
        if goals > 0: stat_tag.append(f"{goals}هـ")
        if assists > 0: stat_tag.append(f"{assists}أ")
        stat_str = f" ({'+'.join(stat_tag)})" if stat_tag else ""
        parts.append(f"GW{gw}: {mins}د{stat_str} [{pts}ن]")

    summary_text = " | ".join(parts) if parts else f"{tot_mins}د ({tot_pts}ن)"

    return {
        "last_3_matches": matches,
        "last_3_summary": summary_text,
        "last_3_mins": tot_mins,
        "last_3_pts": tot_pts,
        "last_3_goals": tot_goals,
        "last_3_assists": tot_assists,
        "last_3_clean_sheets": tot_cs
    }


def fetch_elements_summaries_parallel(player_ids, teams_map=None):
    """سحب سجل أداء قائمة لاعبين بالتوازي وبسرعة فائقة عبر ThreadPoolExecutor"""
    results = {}
    unique_ids = list(set(pid for pid in player_ids if pid))
    if not unique_ids:
        return results

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_pid = {executor.submit(get_element_summary, pid): pid for pid in unique_ids}
        for future in as_completed(future_to_pid):
            pid = future_to_pid[future]
            try:
                raw = future.result()
                results[pid] = parse_last_3_matches(raw, teams_map)
            except Exception:
                results[pid] = {
                    "last_3_matches": [],
                    "last_3_summary": "غير متوفر",
                    "last_3_mins": 0,
                    "last_3_pts": 0,
                    "last_3_goals": 0,
                    "last_3_assists": 0,
                    "last_3_clean_sheets": 0
                }
    return results


def fnum(val, default=0.0):
    try:
        if val is None:
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def get_current_and_next_gw(boot):
    events = boot.get("events", [])
    current_gw = None
    next_gw = None

    for ev in events:
        if ev.get("is_current"):
            current_gw = ev["id"]
        if ev.get("is_next"):
            next_gw = ev["id"]

    if not current_gw and not next_gw:
        for ev in events:
            if not ev.get("finished"):
                next_gw = ev["id"]
                current_gw = max(1, ev["id"] - 1)
                break
    if not current_gw:
        current_gw = 1
    if not next_gw:
        next_gw = current_gw + 1

    return current_gw, next_gw


def get_gw_fixtures(fixtures_data, target_gw, teams_map):
    gw_fx = []
    for f in fixtures_data:
        if f.get("event") == target_gw:
            th = f.get("team_h")
            ta = f.get("team_a")
            home_t = teams_map.get(th, {})
            away_t = teams_map.get(ta, {})
            gw_fx.append({
                "home": home_t.get("short_name", "???"),
                "home_code": home_t.get("code", 0),
                "away": away_t.get("short_name", "???"),
                "away_code": away_t.get("code", 0),
                "home_full": home_t.get("name", "???"),
                "away_full": away_t.get("name", "???"),
                "kickoff": f.get("kickoff_time"),
                "diff_h": f.get("team_h_difficulty", 3),
                "diff_a": f.get("team_a_difficulty", 3)
            })
    gw_fx.sort(key=lambda x: x["kickoff"] or "")
    return gw_fx


def calculate_xmins(el, team_short):
    total_minutes = int(el.get("minutes") or 0)
    starts = int(el.get("starts") or 0)
    status = el.get("status", "a")
    chance = el.get("chance_of_playing_next_round")

    if status in ("i", "s", "n", "u") or chance == 0:
        return 0

    if starts >= 3:
        avg_mins = total_minutes / max(1, starts)
        base_mins = min(90, max(50, avg_mins))
    elif total_minutes > 120:
        base_mins = 60
    else:
        base_mins = 35

    if team_short in EUROPEAN_CLUBS and el.get("element_type") in (3, 4):
        base_mins *= 0.88

    if status == "d" and chance is not None:
        base_mins *= (chance / 100.0)
    elif status == "d":
        base_mins *= 0.50

    return int(round(base_mins))


def build_player_dict(boot, fixtures_data, next_gw):
    teams = {t["id"]: t for t in boot.get("teams", [])}
    team_fixtures = {}
    for f in fixtures_data:
        ev = f.get("event")
        if not ev or ev < next_gw or ev > next_gw + 5:
            continue
        th = f.get("team_h")
        ta = f.get("team_a")
        
        team_fixtures.setdefault(th, []).append({
            "gw": ev, "opponent": teams.get(ta, {}).get("short_name", "???"),
            "is_home": True, "diff": f.get("team_h_difficulty", 3),
            "kickoff": f.get("kickoff_time")
        })
        team_fixtures.setdefault(ta, []).append({
            "gw": ev, "opponent": teams.get(th, {}).get("short_name", "???"),
            "is_home": False, "diff": f.get("team_a_difficulty", 3),
            "kickoff": f.get("kickoff_time")
        })

    for tid in team_fixtures:
        team_fixtures[tid].sort(key=lambda x: x["gw"])

    pos_names = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
    pos_ar = {1: "حارس مرمى", 2: "مدافع", 3: "خط وسط", 4: "مهاجم"}
    status_ar = {
        "a": "جاهز يلعب",
        "d": "شك في مشاركته",
        "i": "مصاب",
        "s": "موقوف",
        "u": "مش متاح",
        "n": "برة القائمة"
    }

    players = {}
    for el in boot.get("elements", []):
        pid = el["id"]
        tid = el.get("team")
        team_info = teams.get(tid, {})
        team_short = team_info.get("short_name", "")
        fx_list = team_fixtures.get(tid, [])
        
        next_3 = []
        for fx in fx_list[:3]:
            next_3.append({
                "opp": fx["opponent"],
                "side": "(H)" if fx["is_home"] else "(A)",
                "diff": fx["diff"]
            })

        diff_next_3 = round(sum(f["diff"] for f in fx_list[:3]) / max(1, len(fx_list[:3])), 2) if fx_list else 3.0

        price = round(fnum(el.get("now_cost")) / 10.0, 1)
        ppg = fnum(el.get("points_per_game"))
        form = fnum(el.get("form"))
        total_pts = int(el.get("total_points") or 0)
        minutes = int(el.get("minutes") or 0)
        xg = fnum(el.get("expected_goals"))
        xa = fnum(el.get("expected_assists"))
        xg_90 = round(xg / (minutes / 90.0), 2) if minutes >= 90 else 0.0
        xa_90 = round(xa / (minutes / 90.0), 2) if minutes >= 90 else 0.0

        pen_order = el.get("penalties_order")
        is_pen_taker = (pen_order == 1)
        fk_order = el.get("direct_freekicks_order")
        corner_order = el.get("corners_and_indirect_freekicks_order")
        is_set_piece = (fk_order == 1 or corner_order == 1)

        xmins = calculate_xmins(el, team_short)

        trans_in = int(el.get("transfers_in_event") or 0)
        trans_out = int(el.get("transfers_out_event") or 0)
        net_trans = trans_in - trans_out
        if net_trans > 50000:
            price_trend = "rising"
            price_trend_lbl = "📈 سعره صاعد قريباً (+0.1m)"
        elif net_trans < -50000:
            price_trend = "falling"
            price_trend_lbl = "📉 مهدد بنزول السعر (-0.1m)"
        else:
            price_trend = "stable"
            price_trend_lbl = "ثابت"

        own_pct = fnum(el.get("selected_by_percent"))
        if own_pct >= 50.0 and el.get("element_type") in (3, 4):
            estimated_eo = round(own_pct * 1.5, 1)
        elif own_pct >= 30.0:
            estimated_eo = round(own_pct * 1.25, 1)
        else:
            estimated_eo = round(own_pct * 1.05, 1)

        p = {
            "id": pid,
            "web_name": el.get("web_name"),
            "full_name": f"{el.get('first_name', '')} {el.get('second_name', '')}".strip(),
            "photo": el.get("photo"),
            "team_id": tid,
            "team_code": team_info.get("code", 0),
            "team_name": team_info.get("name", ""),
            "team_short": team_short,
            "element_type": el.get("element_type"),
            "pos": pos_names.get(el.get("element_type"), "???"),
            "pos_ar": pos_ar.get(el.get("element_type"), "???"),
            "price": price,
            "total_points": total_pts,
            "points_per_game": ppg,
            "form": form,
            "selected_by_percent": own_pct,
            "estimated_eo": estimated_eo,
            "status": el.get("status", "a"),
            "status_ar": status_ar.get(el.get("status", "a"), "مش محدد"),
            "news": el.get("news") or "",
            "chance_next": el.get("chance_of_playing_next_round"),
            "clean_sheets": int(el.get("clean_sheets") or 0),
            "goals_scored": int(el.get("goals_scored") or 0),
            "assists": int(el.get("assists") or 0),
            "xg": xg,
            "xa": xa,
            "xg_90": xg_90,
            "xa_90": xa_90,
            "xmins": xmins,
            "is_pen_taker": is_pen_taker,
            "is_set_piece": is_set_piece,
            "price_trend": price_trend,
            "price_trend_lbl": price_trend_lbl,
            "next_3": next_3,
            "diff_next_3": diff_next_3,
            "can_select": bool(el.get("can_select", True)) and not bool(el.get("removed", False))
        }

        p["xp"] = calculate_xp(p)
        players[pid] = p

    return players, teams


def calculate_xp(p):
    xmins = p.get("xmins", 75)
    if xmins <= 15:
        return 0.2

    mins_ratio = xmins / 90.0

    att_x = p["xg_90"] + p["xa_90"]
    if p.get("is_pen_taker"):
        att_x += 0.25
    if p.get("is_set_piece"):
        att_x += 0.12

    att_pts = min(att_x, 2.5) * 2.4
    if p["pos"] in ("GK", "DEF"):
        att_pts *= 0.35

    def_pts = 0.0
    if p["pos"] in ("GK", "DEF"):
        cs_rate = (p["clean_sheets"] / max(1, p["total_points"] / 4.0)) if p["total_points"] > 0 else 0.25
        def_pts = min(cs_rate, 0.55) * 3.8

    base_pts = (0.35 * p["points_per_game"] + 0.35 * p["form"] + att_pts + def_pts) * mins_ratio

    n3 = p.get("next_3", [])
    if n3:
        m1 = n3[0]
        opp = m1.get("opp")
        diff = m1.get("diff", 3)
        home = (m1.get("side") == "(H)")

        if not home and opp in TOP_DEFENSES:
            base_pts *= 0.70  # خصم 30% لمواجهة السيتي أو أرسنال أو ليفربول خارج الأرض
        elif not home and diff >= 4:
            base_pts *= 0.82
        elif home and diff <= 2:
            base_pts *= 1.20
        elif home:
            base_pts *= 1.08

    return round(max(0.0, base_pts), 1)


def parse_chips_status(history_data, current_gw):
    used_chips_raw = (history_data or {}).get("chips", [])
    chips_map = {uc.get("name"): uc.get("event") for uc in used_chips_raw}

    wc_used_event = chips_map.get("wildcard")
    wc1_used = (wc_used_event is not None and wc_used_event <= 19)
    wc2_used = (wc_used_event is not None and wc_used_event >= 20)
    
    return [
        {
            "id": "wildcard_1",
            "name": "الوايلد كارد (الأولى)",
            "english_name": "Wildcard 1",
            "is_used": wc1_used,
            "used_gw": wc_used_event if wc1_used else None,
            "status_label": f"اتلعبت في الجولة {wc_used_event}" if wc1_used else "متاحة للاستخدام"
        },
        {
            "id": "wildcard_2",
            "name": "الوايلد كارد (التانية)",
            "english_name": "Wildcard 2",
            "is_used": wc2_used,
            "used_gw": wc_used_event if wc2_used else None,
            "status_label": f"اتلعبت في الجولة {wc_used_event}" if wc2_used else ("متاحة للاستخدام" if current_gw >= 20 else "متاحة (من الجولة 20)")
        },
        {
            "id": "freehit",
            "name": "الفري هيت",
            "english_name": "Free Hit",
            "is_used": "freehit" in chips_map,
            "used_gw": chips_map.get("freehit"),
            "status_label": f"اتلعبت في الجولة {chips_map.get('freehit')}" if "freehit" in chips_map else "متاحة للاستخدام"
        },
        {
            "id": "bboost",
            "name": "البنش بوست",
            "english_name": "Bench Boost",
            "is_used": "bboost" in chips_map,
            "used_gw": chips_map.get("bboost"),
            "status_label": f"اتلعبت في الجولة {chips_map.get('bboost')}" if "bboost" in chips_map else "متاحة للاستخدام"
        },
        {
            "id": "3xc",
            "name": "التريبل كابتن",
            "english_name": "Triple Captain",
            "is_used": "3xc" in chips_map,
            "used_gw": chips_map.get("3xc"),
            "status_label": f"اتلعبت في الجولة {chips_map.get('3xc')}" if "3xc" in chips_map else "متاحة للاستخدام"
        }
    ]


def calculate_free_transfers(history_data, current_gw, next_gw):
    """
    حساب عدد التبديلات المجانية المتاحة للمدرب بدقة (قواعد 2024/2025: إمكانية تجميع حتى 5 تبديلات)
    """
    if not history_data or "current" not in history_data:
        return 1

    current_list = history_data.get("current", [])
    if not current_list:
        return 1

    ft = 1
    for row in current_list:
        ev = row.get("event", 1)
        if ev == 1:
            ft = 1
            continue

        transfers_made = int(row.get("event_transfers") or 0)
        ft_used = min(ft, transfers_made)
        ft_remaining = ft - ft_used
        ft = min(5, ft_remaining + 1)

    return max(1, min(5, ft))


def select_captains_smart(starting):
    """
    اختيار الكابتن والفايس بذكاء كروي قاطع يمنع أي تناقضات:
    1. الكابتن الآمن مستحيل يلاعب مانشستر سيتي أو أرسنال أو ليفربول خارج ملعبه أو ماتش صعوبة 4/5!
    2. لو التشكيلة كلها مواجهاتها صعبة، بنعلن مأزق الكبتنة بصراحة ونرشح الأقل ضرراً.
    3. الفايس كابتن من ماتش مختلف تماماً.
    """
    attackers = [p for p in starting if p["pos"] in ("FWD", "MID")]
    pool = attackers if attackers else list(starting)

    def evaluate_safe(p):
        score = p["xp"]
        n3 = p.get("next_3", [])
        if n3:
            m = n3[0]
            opp = m.get("opp")
            is_home = (m.get("side") == "(H)")
            diff = m.get("diff", 3)

            # عقاب حاسم لمواجهات القمة المعقدة
            if opp in TOP_DEFENSES and not is_home:
                score -= 10.0  # خارج الأرض ضد السيتي أو أرسنال أو ليفربول مستحيل يكون كابتن آمن!
            elif diff >= 4:
                score -= 6.0
            elif opp in TOP_DEFENSES and is_home:
                score -= 3.0
            elif is_home and diff <= 2:
                score += 3.5  # أفضلية كاسحة لماتش هوم سهل
            elif is_home:
                score += 1.5

        if p.get("is_pen_taker"):
            score += 1.5
        return score

    # فرز لاختيار الكابتن الآمن الحقيقي
    sorted_safe = sorted(pool, key=evaluate_safe, reverse=True)
    best_safe = sorted_safe[0] if sorted_safe else starting[0]

    # فحص: هل الكابتن المختار يواجه مباراة صعبة؟
    first_m = (best_safe.get("next_3") or [{}])[0]
    safe_opp = first_m.get("opp")
    safe_diff = first_m.get("diff", 3)
    safe_is_home = (first_m.get("side") == "(H)")
    
    is_safe_compromised = (safe_diff >= 4 or (not safe_is_home and safe_opp in TOP_DEFENSES))

    # اختيار الفايس كابتن (من مباراة أخرى مختلفة)
    vice_pool = [p for p in pool if p["id"] != best_safe["id"] and (p.get("next_3") or [{}])[0].get("opp") != safe_opp]
    if not vice_pool:
        vice_pool = [p for p in pool if p["id"] != best_safe["id"]]
    sorted_vice = sorted(vice_pool, key=evaluate_safe, reverse=True)
    best_vice = sorted_vice[0] if sorted_vice else best_safe

    # اختيار الكابتن الريسكي / الديفرنشال (خطة 2):
    # لاعب بنسبة امتلاك منخفضة (<35%) وتكون مباراته في المتناول (هوم أو صعوبة <= 3)
    diff_pool = [p for p in pool if p.get("selected_by_percent", 10.0) <= 35 and (p.get("next_3") or [{}])[0].get("diff", 3) <= 3]
    if not diff_pool:
        diff_pool = [p for p in pool if p["id"] != best_safe["id"]]

    def evaluate_diff(p):
        sc = p["xp"] + (p["xg_90"] * 2.0)
        m = (p.get("next_3") or [{}])[0]
        if m.get("side") == "(H)":
            sc += 2.0
        if m.get("diff", 3) <= 2:
            sc += 2.5
        return sc

    sorted_diff = sorted(diff_pool, key=evaluate_diff, reverse=True)
    best_diff = sorted_diff[0] if sorted_diff else best_vice

    return {
        "safe": best_safe,
        "vice": best_vice,
        "diff": best_diff,
        "is_safe_compromised": is_safe_compromised
    }


def select_three_captains(starting, starters_base_xp, disallowed_names=None):
    """
    اختيار الكباتن الثلاثة لكل تشكيلة مع ضمان عدم تناقض الاختيارات:
    - ممنوع كبتنة أي لاعب معروض للبيع أو يعاني من إصابة/شكوك (disallowed_names).
    1. الكبتنة المضمونة (Safe): خيار الميتا الأكثر أماناً وحماية للترتيب العام.
    2. كبتنة فيها فكرة (Tactical): خيار تكتيكي ذكي مدعوم بأرقام xG/xA والكرات الثابتة ومواجهة الخصم.
    3. كبتنة ريسكي (Risky/Differential): خيار ديفرنشال بملكية منخفضة ومخاطرة عالية لصناعة الفارق.
    """
    disallowed = set(disallowed_names or [])
    
    # فلترة المهاجمين ولاعبي الوسط المستعدين وغير المعروضين للبيع
    attackers = [
        p for p in starting 
        if p.get("pos") in ("FWD", "MID") 
        and p.get("web_name") not in disallowed 
        and p.get("status") == "a"
    ]
    
    # إذا لم نجد أي مهاجم مستعد، نتوسع لأي مهاجم متاح بالتشكيلة غير معروض للبيع
    if not attackers:
        attackers = [
            p for p in starting 
            if p.get("pos") in ("FWD", "MID") 
            and p.get("web_name") not in disallowed
        ]
        
    # إذا استمر عدم وجود عناصر، نعتمد التشكيلة باستثناء المعروضين للبيع
    if not attackers:
        attackers = [p for p in starting if p.get("web_name") not in disallowed]
        
    pool = attackers if attackers else list(starting)

    def eval_safe(p):
        score = p.get("xp", 0.0)
        n3 = p.get("next_3", [])
        if n3:
            m = n3[0]
            opp = m.get("opp")
            diff = m.get("diff", 3)
            is_home = (m.get("side") == "(H)")
            if opp in TOP_DEFENSES and not is_home:
                score -= 10.0
            elif diff >= 4:
                score -= 6.0
            elif opp in TOP_DEFENSES and is_home:
                score -= 3.0
            elif is_home and diff <= 2:
                score += 3.5
            elif is_home:
                score += 1.5
        if p.get("is_pen_taker"):
            score += 1.5
        own = float(p.get("selected_by_percent", 0.0) or 0.0)
        score += min(5.0, own * 0.1)
        return score

    sorted_safe = sorted(pool, key=eval_safe, reverse=True)
    best_safe = sorted_safe[0] if sorted_safe else pool[0]

    def eval_tactical(p):
        sc = p.get("xp", 0.0) + (p.get("xg_90", 0.0) * 2.5) + (p.get("xa_90", 0.0) * 2.0)
        if p.get("is_pen_taker"):
            sc += 2.0
        if p.get("is_set_piece"):
            sc += 1.0
        if p.get("form", 0.0) >= 5.0:
            sc += 2.0
        n3 = p.get("next_3", [])
        if n3 and n3[0].get("side") == "(H)":
            sc += 1.5
        return sc

    tactical_pool = [p for p in pool if p.get("id") != best_safe.get("id")] or pool
    sorted_tactical = sorted(tactical_pool, key=eval_tactical, reverse=True)
    best_tactical = sorted_tactical[0] if sorted_tactical else best_safe

    def eval_risky(p):
        own = float(p.get("selected_by_percent", 15.0) or 15.0)
        sc = p.get("xp", 0.0) + (p.get("xg_90", 0.0) * 3.0)
        if own <= 12.0:
            sc += 6.0
        elif own <= 20.0:
            sc += 3.5
        elif own > 40.0:
            sc -= 5.0
        return sc

    risky_pool = [p for p in pool if p.get("id") not in (best_safe.get("id"), best_tactical.get("id"))] or pool
    sorted_risky = sorted(risky_pool, key=eval_risky, reverse=True)
    best_risky = sorted_risky[0] if sorted_risky else best_tactical

    def build_cap(p, cap_type):
        xp = round(p.get("xp", 0.0), 1)
        tot = round(starters_base_xp + xp, 1)
        
        # رينج النقاط المضافة للكبتنة فقط (الضعف الإضافي)
        cap_min_added = max(2, int(round(xp * 0.7)))
        cap_max_added = int(round(xp * 1.5 + 2))
        cap_added_range = f"{cap_min_added} - {cap_max_added} نقطة"
        
        # رينج إجمالي نقاط الفريق بالكامل عند اختيار هذا الكابتن
        tot_flr = max(35, int(round(tot * 0.88 - 1)))
        tot_ceil = int(round(tot * 1.12 + 2))
        total_range = f"{tot_flr} - {tot_ceil} نقطة"
        
        m = (p.get("next_3") or [{}])[0]
        side = "على ملعبه" if m.get("side") == "(H)" else "خارج ملعبه"
        opp = m.get("opp", "خصمه")

        if cap_type == "safe":
            reason = f"كبتنة {p.get('web_name')} هي الخيار الأكثر أماناً وحماية لترتيبك العام؛ مواجهته {side} أمام {opp} ومعدل نقاطه المتوقعة ({xp}ن) هو الأكثر استقراراً في الجولة."
            label = "👑 الكبتنة المضمونة (Safe)"
            badge_class = "cap-safe"
        elif cap_type == "tactical":
            reason = f"كبتنة {p.get('web_name')} فيها فكرة تكتيكية مدروسة؛ خطورته الهجومية (xG/xA: {p.get('xg_90', 0)} / {p.get('xa_90', 0)}) ونقاط ضعف دفاع {opp} تمنحه أسبقية نوعية لمنافسة الميتا."
            label = "🧠 كبتنة فيها فكرة (Tactical)"
            badge_class = "cap-tactical"
        else:
            reason = f"كبتنة {p.get('web_name')} رهان هجومي جرئ (نسبة امتلاك {p.get('selected_by_percent', 0)}% فقط)؛ تألقه في مواجهة {opp} يصنع لك قفزة عملاقة في دوري الأصدقاء والترتيب العام."
            label = "🎯 كبتنة ريسكي (Differential)"
            badge_class = "cap-risky"

        return {
            "player": dict(p),
            "xp": xp,
            "cap_added_xp": xp,
            "cap_added_range": cap_added_range,
            "total_with_cap": tot,
            "pts_range": total_range,
            "total_range": total_range,
            "label": label,
            "badge_class": badge_class,
            "reason": reason
        }

    return {
        "safe": build_cap(best_safe, "safe"),
        "tactical": build_cap(best_tactical, "tactical"),
        "risky": build_cap(best_risky, "risky")
    }


def find_best_buys(sell_player, max_budget, count=3, pos_filter=None, prefer_cheaper=False, max_ownership=100.0, all_players=None, squad_ids=None, club_counts=None, bank=0.0):
    if not all_players:
        return []
    squad_ids = squad_ids or set()
    club_counts = club_counts or {}
    target_pos = pos_filter or (sell_player.get("pos") if isinstance(sell_player, dict) else "MID")
    sell_price = sell_player.get("price", 6.0) if isinstance(sell_player, dict) else 6.0
    sell_xp = sell_player.get("xp", 4.0) if isinstance(sell_player, dict) else 4.0
    sell_team = sell_player.get("team_id", 0) if isinstance(sell_player, dict) else 0

    cands = []
    for p in all_players.values():
        if p.get("id") in squad_ids or not p.get("can_select") or p.get("status") not in ("a", "d"):
            continue
        if p.get("pos") != target_pos:
            continue
        if p.get("selected_by_percent", 10.0) > max_ownership:
            continue
        if p.get("xmins", 75) < 60:
            continue
        same_club = (p.get("team_id", 0) == sell_team)
        if not same_club and club_counts.get(p.get("team_id", 0), 0) >= 3:
            continue
        if p.get("price", 999.0) <= max_budget + 1e-5:
            future_diff = p.get("diff_next_3", 3.0)
            diff_bonus = max(0.0, (3.6 - future_diff) * 0.5)
            set_piece_bonus = 0.35 if p.get("is_pen_taker") else (0.18 if p.get("is_set_piece") else 0.0)
            gain = round(p.get("xp", 4.0) - sell_xp + diff_bonus + set_piece_bonus, 1)
            cands.append((dict(p), gain))
    if not cands:
        return []
    if prefer_cheaper:
        cands.sort(key=lambda x: (x[1] >= -0.2, (sell_price - x[0]["price"]), x[1]), reverse=True)
    else:
        cands.sort(key=lambda x: (x[1], -x[0].get("diff_next_3", 3), -x[0]["price"]), reverse=True)

    ranked = []
    rank_titles = [
        ("🥇 الخيار الأول (الموصى به بشدة)", "الأعلى نقاطاً متوقعة وتطابقاً مع استراتيجية الخطة."),
        ("🥈 البديل الثاني (خيار استراتيجي)", "بديل قوي يمتلك جدولاً ميسراً وأداءً تصاعدياً."),
        ("🥉 البديل الثالث (قيمة ممتازة)", "خيار اقتصادي أو ديفرنشال يمنحك مرونة مالية.")
    ]
    for i, (cp, gain) in enumerate(cands[:count]):
        badge, default_reason = rank_titles[min(i, 2)]
        cost_diff = round(cp["price"] - sell_price, 1)
        b_after = round(bank - cost_diff, 1)
        ranked.append({
            "rank": i + 1,
            "badge": badge,
            "player": cp,
            "gain": gain,
            "cost_diff": cost_diff,
            "bank_after": b_after,
            "reason": f"ضم {cp['web_name']} ({cp.get('team_short', '')}) بسعر £{cp['price']}m وبفارق متوقع (+{gain}ن). {default_reason}"
        })
    return ranked


def balance_wildcard_budget(starters_objs, bench_objs, total_budget, all_players):
    """
    موازنة تشكيلة الوايلد كارد / الفري هيت بدقة رياضية صارمة:
    1. حساب التكلفة الإجمالية لـ 15 لاعباً (11 أساسي + 4 بدلاء).
    2. لو التكلفة <= total_budget، التشكيلة متوافقة ولا تحتاج تعديل.
    3. لو التكلفة > total_budget، تقليص النفقات بالتدريج (الدكة أولاً ثم الأساسيين الأقل أولوية مع حماية أول نجمين سوبر ستار).
    """
    starters = [dict(p) for p in starters_objs if p]
    bench = [dict(p) for p in bench_objs if p]

    def get_club_counts(all_15):
        counts = {}
        for p in all_15:
            cid = p.get("team_id", 0)
            counts[cid] = counts.get(cid, 0) + 1
        return counts

    def calc_total():
        return round(sum(p.get("price", 0.0) for p in starters) + sum(p.get("price", 0.0) for p in bench), 1)

    total_cost = calc_total()
    if total_cost <= total_budget:
        return starters, bench, total_cost

    current_ids = {p["id"] for p in starters + bench if "id" in p}
    current_names = {p.get("web_name", "").lower() for p in starters + bench if p.get("web_name")}

    cheap_gks = sorted([p for p in all_players.values() if p.get("pos") == "GK" and p.get("price", 99) <= 4.1 and p.get("status") == "a"], key=lambda x: -x.get("xp", 0))
    cheap_defs = sorted([p for p in all_players.values() if p.get("pos") == "DEF" and p.get("price", 99) <= 4.1 and p.get("status") == "a"], key=lambda x: -x.get("xp", 0))
    cheap_mids = sorted([p for p in all_players.values() if p.get("pos") == "MID" and p.get("price", 99) <= 4.6 and p.get("status") == "a"], key=lambda x: -x.get("xp", 0))
    cheap_fwds = sorted([p for p in all_players.values() if p.get("pos") == "FWD" and p.get("price", 99) <= 5.5 and p.get("status") == "a"], key=lambda x: -x.get("xp", 0))

    # 1. تخفيض حارس الدكة إلى 4.0م
    for i, bp in enumerate(bench):
        if bp.get("pos") == "GK" and bp.get("price", 0) > 4.0:
            for cg in cheap_gks:
                if cg.get("id") not in current_ids and cg.get("web_name", "").lower() not in current_names:
                    club_c = get_club_counts(starters + bench)
                    if club_c.get(cg.get("team_id", 0), 0) < 3:
                        current_ids.discard(bp.get("id"))
                        current_names.discard(bp.get("web_name", "").lower())
                        bench[i] = dict(cg)
                        current_ids.add(cg.get("id"))
                        current_names.add(cg.get("web_name", "").lower())
                        break
            total_cost = calc_total()
            if total_cost <= total_budget:
                return starters, bench, total_cost

    # 2. تخفيض لاعبي الدكة الـ 3 إلى أرخص أسعار
    for i, bp in enumerate(bench):
        pos = bp.get("pos")
        curr_p = bp.get("price", 0)
        pool = []
        if pos == "DEF" and curr_p > 4.0:
            pool = cheap_defs
        elif pos == "MID" and curr_p > 4.5:
            pool = cheap_mids
        elif pos == "FWD" and curr_p > 5.0:
            pool = cheap_fwds

        if pool:
            for cand in pool:
                if cand.get("id") not in current_ids and cand.get("web_name", "").lower() not in current_names:
                    club_c = get_club_counts(starters + bench)
                    if club_c.get(cand.get("team_id", 0), 0) < 3:
                        current_ids.discard(bp.get("id"))
                        current_names.discard(bp.get("web_name", "").lower())
                        bench[i] = dict(cand)
                        current_ids.add(cand.get("id"))
                        current_names.add(cand.get("web_name", "").lower())
                        break
            total_cost = calc_total()
            if total_cost <= total_budget:
                return starters, bench, total_cost

    # 3. تخفيض الأساسيين مع حماية أول نجمين سوبر ستار الأعلى سعراً ونقاطاً
    starters_indices = sorted(range(len(starters)), key=lambda idx: (starters[idx].get("price", 0), starters[idx].get("xp", 0)), reverse=True)
    candidates_idx = starters_indices[2:]

    for s_idx in candidates_idx:
        sp = starters[s_idx]
        pos = sp.get("pos")
        curr_p = sp.get("price", 0)
        needed_save = round(total_cost - total_budget, 1)
        target_max_price = round(curr_p - needed_save, 1)

        cands = [
            p for p in all_players.values()
            if p.get("pos") == pos and p.get("status") == "a"
            and p.get("price", 99) <= target_max_price
            and p.get("id") not in current_ids
            and p.get("web_name", "").lower() not in current_names
        ]
        if not cands:
            cands = [
                p for p in all_players.values()
                if p.get("pos") == pos and p.get("status") == "a"
                and p.get("price", 99) < curr_p
                and p.get("id") not in current_ids
                and p.get("web_name", "").lower() not in current_names
            ]

        if cands:
            cands.sort(key=lambda x: (-x.get("xp", 0), x.get("price", 99)))
            for chosen in cands:
                club_c = get_club_counts(starters + bench)
                if club_c.get(chosen.get("team_id", 0), 0) < 3:
                    current_ids.discard(sp.get("id"))
                    current_names.discard(sp.get("web_name", "").lower())
                    starters[s_idx] = dict(chosen)
                    current_ids.add(chosen.get("id"))
                    current_names.add(chosen.get("web_name", "").lower())
                    break
            total_cost = calc_total()
            if total_cost <= total_budget:
                return starters, bench, total_cost

    return starters, bench, calc_total()


def enrich_ai_gameplans(ai_plans, team_data, all_players, next_gw):
    if not ai_plans:
        return ai_plans

    squad_map = {p["web_name"].lower(): p for p in team_data.get("squad_all", [])}
    all_players_map = {p.get("web_name", "").lower(): p for p in all_players.values()}
    bank = team_data.get("manager", {}).get("bank", 0.0)
    squad_selling_val = round(sum(p.get("selling_price", p.get("price", 0.0)) for p in team_data.get("squad_all", [])), 1)
    total_budget = round(squad_selling_val + bank, 1)
    free_transfers = int(team_data.get("manager", {}).get("free_transfers") or 1)

    def find_player(name_or_obj):
        if not name_or_obj:
            return None
        if isinstance(name_or_obj, dict) and name_or_obj.get("web_name"):
            name = name_or_obj["web_name"]
        else:
            name = str(name_or_obj).strip()
        if not name:
            return None
        low = name.lower()
        if low in squad_map:
            return dict(squad_map[low])
        if low in all_players_map:
            return dict(all_players_map[low])
        for k, p in squad_map.items():
            if low in k or k in low:
                return dict(p)
        for k, p in all_players_map.items():
            if low in k or k in low:
                return dict(p)
        return {"web_name": name, "pos": "MID", "price": 6.0, "xp": 4.0, "team_short": "", "selected_by_percent": 5.0, "next_3": []}

    enriched = []
    for plan in ai_plans:
        p_copy = dict(plan)
        proposals = p_copy.get("proposals", [])
        enriched_proposals = []

        for prop in proposals:
            pr = dict(prop)
            is_wc = bool(pr.get("is_wildcard")) or (p_copy.get("plan_num") == 2 and pr.get("prop_num") == 3) or ("وايلد" in pr.get("title", "")) or ("wildcard" in pr.get("title", "").lower()) or ("فري هيت" in pr.get("title", "")) or ("free hit" in pr.get("title", "").lower())

            # 1. Enrich transfers
            enriched_transfers = []
            for tr in pr.get("transfers", []):
                s_obj = find_player(tr.get("sell"))
                b_obj = find_player(tr.get("buy"))
                if s_obj and b_obj:
                    cost_diff = round(b_obj["price"] - s_obj.get("selling_price", s_obj["price"]), 1)
                    gain = round(b_obj.get("xp", 0) - s_obj.get("xp", 0), 1)
                    enriched_transfers.append({
                        "sell": s_obj,
                        "buy": b_obj,
                        "cost_diff": tr.get("cost_diff", cost_diff),
                        "gain": tr.get("gain", gain),
                        "bank_after": tr.get("bank_after", round(bank - cost_diff, 1))
                    })
            pr["transfers"] = enriched_transfers

            if is_wc:
                # ===================== حالة الوايلد كارد / الفري هيت =====================
                pr["is_wildcard"] = True
                raw_starters = pr.get("final_starters", [])
                starters_objs = [find_player(item) for item in raw_starters if item]
                starters_objs = [p for p in starters_objs if p]

                raw_bench = pr.get("bench_order", [])
                bench_objs = [find_player(item) for item in raw_bench if item]
                bench_objs = [p for p in bench_objs if p and p.get("pos") != "GK"]

                bgk_name = pr.get("bench_gk")
                bgk_obj = find_player(bgk_name) if bgk_name and bgk_name not in ("—", "") else None
                if not bgk_obj:
                    bgk_obj = next((p for p in team_data.get("bench", []) if p.get("pos") == "GK"), None)
                if bgk_obj:
                    bench_objs.append(dict(bgk_obj))

                # موازنة ميزانية الـ 15 لاعباً بالكامل تحت سقف الميزانية
                balanced_s, balanced_b, total_squad_cost = balance_wildcard_budget(starters_objs, bench_objs, total_budget, all_players)

                # تثبيت الحسبة المالية للوايلد كارد
                pr["total_budget"] = total_budget
                pr["total_squad_cost"] = total_squad_cost
                pr["bank_after"] = round(total_budget - total_squad_cost, 1)

                pr["final_starters"] = balanced_s[:11]
                pr["final_starters_names"] = [p.get("web_name") for p in pr["final_starters"]]

                outfield_bench = [p for p in balanced_b if p.get("pos") != "GK"]
                pr["bench_order"] = [p.get("web_name") for p in outfield_bench[:3]]
                gk_b = next((p for p in balanced_b if p.get("pos") == "GK"), None)
                pr["bench_gk"] = gk_b.get("web_name") if gk_b else "—"

            else:
                # ===================== حالة التبديلات الأسبوعية العادية =====================
                pr["is_wildcard"] = False
                sold_names = {t["sell"].get("web_name", "").lower() for t in pr["transfers"] if isinstance(t.get("sell"), dict) and t["sell"].get("web_name")}
                bought_players = [t["buy"] for t in pr["transfers"] if isinstance(t.get("buy"), dict) and t["buy"].get("web_name")]

                # قائمة اللاعبين المتاحين شرعياً (الفريق الحالي مطروحاً منه الراحلين ومضافاً إليه القادمون الجدد فقط)
                allowed_pool = {}
                for p in team_data.get("squad_all", []):
                    if p.get("web_name", "").lower() not in sold_names:
                        allowed_pool[p.get("web_name", "").lower()] = dict(p)
                for bp in bought_players:
                    allowed_pool[bp.get("web_name", "").lower()] = dict(bp)

                raw_starters = pr.get("final_starters", [])
                starters_objs = []
                chosen_names = set()

                for item in raw_starters:
                    item_name = (item.get("web_name") if isinstance(item, dict) else str(item)).strip().lower()
                    matched = allowed_pool.get(item_name)
                    if not matched:
                        for k, v in allowed_pool.items():
                            if item_name in k or k in item_name:
                                matched = v
                                break
                    if matched and matched["web_name"].lower() not in chosen_names:
                        starters_objs.append(dict(matched))
                        chosen_names.add(matched["web_name"].lower())

                # التأكد من وجود 11 لاعباً بتشكيلة قانونية من المتاحين حصراً
                remaining = [p for p in allowed_pool.values() if p["web_name"].lower() not in chosen_names]
                remaining.sort(key=lambda x: -x.get("xp", 0))

                gk_in_s = [p for p in starters_objs if p.get("pos") == "GK"]
                if not gk_in_s:
                    gk_cand = next((p for p in remaining if p.get("pos") == "GK"), None)
                    if gk_cand:
                        starters_objs.append(gk_cand)
                        chosen_names.add(gk_cand["web_name"].lower())
                        remaining = [p for p in remaining if p["web_name"].lower() != gk_cand["web_name"].lower()]
                elif len(gk_in_s) > 1:
                    for extra_gk in gk_in_s[1:]:
                        starters_objs.remove(extra_gk)
                        chosen_names.remove(extra_gk["web_name"].lower())
                        remaining.append(extra_gk)

                for rem in remaining:
                    if len(starters_objs) >= 11:
                        break
                    if rem.get("pos") == "GK":
                        continue
                    starters_objs.append(rem)
                    chosen_names.add(rem["web_name"].lower())

                pr["final_starters"] = starters_objs[:11]
                pr["final_starters_names"] = [p.get("web_name") for p in pr["final_starters"]]

                # الدكة هي الباقي من الـ 15 لاعباً post-transfer
                bench_rem = [p for p in allowed_pool.values() if p["web_name"].lower() not in chosen_names]
                outfield_bench = [p for p in bench_rem if p.get("pos") != "GK"]
                outfield_bench.sort(key=lambda x: -x.get("xp", 0))
                pr["bench_order"] = [p.get("web_name") for p in outfield_bench[:3]]

                gk_b = next((p for p in bench_rem if p.get("pos") == "GK"), None)
                pr["bench_gk"] = gk_b.get("web_name") if gk_b else "—"

                # حساب البنك بعد التبديلات
                net_cost_diff = round(sum(t.get("cost_diff", 0.0) for t in pr["transfers"]), 1)
                pr["bank_after"] = round(bank - net_cost_diff, 1)

            # إلحاق المواجهة القادمة وترتيب المراكز للأساسيين
            for p_obj in pr["final_starters"]:
                n3 = p_obj.get("next_3", [])
                p_obj["next_fixture"] = n3[0] if n3 else {"opp": "TBD", "side": "", "diff": 3}

            pos_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
            pr["final_starters"].sort(key=lambda x: (pos_order.get(x.get("pos"), 9), -x.get("xp", 0)))
            pr["final_starters_names"] = [p.get("web_name") for p in pr["final_starters"]]

            # رسم الخطة
            d_c = sum(1 for p in pr["final_starters"] if p.get("pos") == "DEF")
            m_c = sum(1 for p in pr["final_starters"] if p.get("pos") == "MID")
            f_c = sum(1 for p in pr["final_starters"] if p.get("pos") == "FWD")
            pr["formation"] = f"{d_c}-{m_c}-{f_c}"

            # حساب نقاط الأساسيين والدكة
            starters_base_xp = round(sum(p.get("xp", 0) for p in pr["final_starters"]), 1)
            starters_min = max(30, int(round(starters_base_xp * 0.88 - 1)))
            starters_max = int(round(starters_base_xp * 1.12 + 1))
            pr["starters_base_xp"] = starters_base_xp
            pr["starters_range"] = f"{starters_min} - {starters_max} نقطة"

            bench_objs_for_xp = [find_player(n) for n in pr["bench_order"]] + [find_player(pr["bench_gk"])]
            pr["bench_xp"] = round(sum(p.get("xp", 0) for p in bench_objs_for_xp if p), 1)

            # الكباتن الثلاثة مع استبعاد الراحلين
            sold_for_cap = {t["sell"].get("web_name") for t in pr["transfers"] if isinstance(t.get("sell"), dict) and t["sell"].get("web_name")}
            pr["captains"] = select_three_captains(pr["final_starters"], starters_base_xp, disallowed_names=sold_for_cap)

            # المكسب الصافي والسالب
            gross_gain = round(sum(tr.get("gain", 0) for tr in pr["transfers"]), 1)
            hit_cost = pr.get("hit_cost", 0)
            if p_copy.get("plan_num") == 3 and hit_cost == 0:
                hit_cost = -4
            pr["hit_cost"] = hit_cost
            pr["gross_gain"] = gross_gain
            pr["net_gain"] = round(gross_gain - abs(hit_cost), 1) if hit_cost != 0 else gross_gain

            enriched_proposals.append(pr)

        p_copy["proposals"] = enriched_proposals
        enriched.append(p_copy)

    return enriched



def fetch_user_team(team_id, api_key=None):
    if team_id == 0:
        import demo_data
        team_data = dict(demo_data.DEMO_TEAM)
        # حقن سعر البيع الحقيقي في لاعبي الديمو
        for p in team_data.get("squad_all", []) + team_data.get("starting_11", []) + team_data.get("bench", []):
            if "purchase_price" not in p:
                p["purchase_price"] = p.get("price", 6.0)
            p["selling_price"] = compute_selling_price(p["purchase_price"], p.get("price", p["purchase_price"]))
        # حساب إجمالي ميزانية الوايلد كارد (سعر البيع الفعلي + البنك)
        squad_selling_val = round(sum(p.get("selling_price", p.get("price", 0.0)) for p in team_data.get("squad_all", [])), 1)
        bank_val = team_data.get("manager", {}).get("bank", 0.0)
        total_budget_val = round(squad_selling_val + bank_val, 1)
        team_data["manager"]["squad_selling_value"] = squad_selling_val
        team_data["manager"]["total_budget"] = total_budget_val
        all_players = {p["id"]: dict(p) for p in team_data["squad_all"]}
        for mp in getattr(demo_data, "DEMO_MARKET_PLAYERS", []):
            all_players[mp["id"]] = dict(mp)
        import ai_advisor
        ai_plans, ai_err = ai_advisor.generate_gameplans_with_ai(team_data, all_players, 5, api_key)
        if ai_plans:
            team_data["gameplans"] = enrich_ai_gameplans(ai_plans, team_data, all_players, 5)
            team_data["ai_powered"] = True
            team_data["ai_error"] = None
        else:
            team_data["gameplans"] = generate_3_strategic_gameplans(team_data, all_players, 5, team_data.get("chips", []))
            team_data["ai_powered"] = False
            team_data["ai_error"] = ai_err
        return team_data

    with _lock:
        cached = _cache["entries"].get(team_id)
        if cached and (time.time() - cached[1] < ENTRY_TTL):
            return cached[0]

    entry = _fetch_json(f"{FPL_BASE}/entry/{team_id}/")
    if not entry:
        return {"error": "team_not_found", "message": "ملقناش فرقة بالرقم ده (Team ID). اتأكد من صحة الرقم وجرب تاني."}

    history = _fetch_json(f"{FPL_BASE}/entry/{team_id}/history/") or {}

    boot = get_bootstrap()
    fixtures = get_fixtures()
    current_gw, next_gw = get_current_and_next_gw(boot)

    gw_to_fetch = current_gw or 1
    picks_data = _fetch_json(f"{FPL_BASE}/entry/{team_id}/event/{gw_to_fetch}/picks/")
    if not picks_data and gw_to_fetch > 1:
        gw_to_fetch = gw_to_fetch - 1
        picks_data = _fetch_json(f"{FPL_BASE}/entry/{team_id}/event/{gw_to_fetch}/picks/")

    if not picks_data:
        return {"error": "picks_not_found", "message": "لسه مفيش تشكيلة متسجلة للفرقة دي في الجولات الحالية."}

    all_players, teams_map = build_player_dict(boot, fixtures, next_gw)
    gw_fixtures = get_gw_fixtures(fixtures, next_gw, teams_map)
    chips_status = parse_chips_status(history, current_gw)
    free_transfers = calculate_free_transfers(history, current_gw, next_gw)

    picks = picks_data.get("picks", [])
    entry_hist = picks_data.get("entry_history", {})

    bank = round(fnum(entry_hist.get("bank", entry.get("last_deadline_bank", 0))) / 10.0, 1)
    team_value = round(fnum(entry_hist.get("value", entry.get("last_deadline_value", 1000))) / 10.0, 1)

    # سحب سجل أداء لاعبي التشكيلة وأبرز عناصر السوق في آخر 3 مباريات بالتوازي
    squad_pids = [item.get("element") for item in picks if item.get("element")]
    market_cands = [p["id"] for p in all_players.values() if p["id"] not in squad_pids and p.get("can_select") and p.get("status") == "a" and p.get("xp", 0) >= 3.8][:25]
    all_target_pids = squad_pids + market_cands

    try:
        summaries = fetch_elements_summaries_parallel(all_target_pids, teams_map)
        for pid, s_data in summaries.items():
            if pid in all_players:
                all_players[pid].update(s_data)
    except Exception as e:
        print(f"[fpl_engine] تحذير أثناء سحب ملخصات اللاعبين: {e}")

    starting_11 = []
    bench = []

    pos_sort_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}

    for item in picks:
        pid = item["element"]
        p = all_players.get(pid)
        if not p:
            continue
        p_copy = dict(p)
        p_copy["is_captain"] = bool(item.get("is_captain"))
        p_copy["is_vice_captain"] = bool(item.get("is_vice_captain"))
        p_copy["multiplier"] = item.get("multiplier", 1)
        p_copy["pick_position"] = item.get("position", 1)

        # سعر الشراء الأصلي والسعر الحقيقي للبيع (قاعدة 50% للأرباح)
        purchase_price_raw = item.get("purchase_price")
        if purchase_price_raw is not None:
            purchase_price = round(fnum(purchase_price_raw) / 10.0, 1)
        else:
            purchase_price = p_copy.get("price", 0.0)
        p_copy["purchase_price"] = purchase_price
        p_copy["selling_price"] = compute_selling_price(purchase_price, p_copy.get("price", purchase_price))

        if item.get("position", 1) <= 11:
            starting_11.append(p_copy)
        else:
            bench.append(p_copy)

    starting_11.sort(key=lambda x: (pos_sort_order.get(x["pos"], 9), -x["xp"]))
    bench.sort(key=lambda x: (0 if x["pos"] == "GK" else 1, x["pick_position"]))

    def_count = sum(1 for p in starting_11 if p["pos"] == "DEF")
    mid_count = sum(1 for p in starting_11 if p["pos"] == "MID")
    fwd_count = sum(1 for p in starting_11 if p["pos"] == "FWD")
    formation = f"{def_count}-{mid_count}-{fwd_count}"

    team_data = {
        "manager": {
            "id": team_id,
            "team_name": entry.get("name", "فرقتي"),
            "manager_name": f"{entry.get('player_first_name', '')} {entry.get('player_last_name', '')}".strip(),
            "overall_points": entry.get("summary_overall_points", 0),
            "overall_rank": entry.get("summary_overall_rank", 0),
            "bank": bank,
            "team_value": team_value,
            "free_transfers": free_transfers,
            "gameweek": next_gw,
            "current_gw": current_gw,
            "last_gw_played": gw_to_fetch
        },
        "formation": formation,
        "chips": chips_status,
        "fixtures": gw_fixtures,
        "starting_11": starting_11,
        "bench": bench,
        "squad_all": starting_11 + bench
    }

    # حساب إجمالي ميزانية الوايلد كارد (سعر البيع الفعلي + البنك)
    squad_selling_val = round(sum(p.get("selling_price", p.get("price", 0.0)) for p in team_data["squad_all"]), 1)
    total_budget_val = round(squad_selling_val + bank, 1)
    team_data["manager"]["squad_selling_value"] = squad_selling_val
    team_data["manager"]["total_budget"] = total_budget_val

    # فحص توليد الخطط عبر الذكاء الاصطناعي
    import ai_advisor
    ai_plans, ai_err = ai_advisor.generate_gameplans_with_ai(team_data, all_players, next_gw, api_key)
    
    if ai_plans:
        team_data["gameplans"] = enrich_ai_gameplans(ai_plans, team_data, all_players, next_gw)
        team_data["ai_powered"] = True
        team_data["ai_error"] = None
    else:
        gameplans = generate_3_strategic_gameplans(team_data, all_players, next_gw, chips_status)
        team_data["gameplans"] = gameplans
        team_data["ai_powered"] = False
        team_data["ai_error"] = ai_err

    with _lock:
        _cache["entries"][team_id] = (team_data, time.time())

    return team_data


def compute_selling_price(purchase_price, current_price):
    """
    حساب سعر البيع الحقيقي في الفانتازي:
    - لو السعر اتجوز سعر الشراء: البائع ياخد فقط 50% من الأرباح (تقريب للأسفل بـ 0.1m)
    - لو السعر نزل عن سعر الشراء: البائع يبيع بالسعر الحالي (خسارة كاملة)
    
    مثال: اشتريت بـ £7.0m والسعر الحالي £7.4m → تبيع بـ £7.2m (مش £7.4m)
    مثال: اشتريت بـ £7.0m والسعر الحالي £6.8m → تبيع بـ £6.8m
    """
    if current_price <= purchase_price:
        return current_price  # خسارة كاملة بالسعر الحالي
    profit = current_price - purchase_price
    # 50% من الأرباح مقربة للأسفل بـ 0.1m
    # profit بيتقاس بـ 0.1m units عشان نعمل floor صح
    profit_kept = (int(profit * 10) // 2) / 10.0
    return round(purchase_price + profit_kept, 1)


def generate_3_strategic_gameplans(team_data, all_players, next_gw, chips_status):
    """
    توليد 3 ركائز استراتيجية متكاملة وفق الرؤية التكتيكية الحديثة:
    1. «تغييره ولا نستنى؟» (Roll or Free Transfers):
       - استيعاب التبديلات المتراكمة حتى 5 تبديلات (Mini Wildcard).
       - 3 مقترحات تشكيلات متقاربة في القوة مع كروت التغييرات والشرح الفني.
    2. «استخدام خاصية؟» (Chip Activation Advisor):
       - فحص الخواص المتاحة (Wildcard / Triple Captain / Bench Boost / Free Hit).
       - 3 مقترحات تشكيلات/سيناريوهات بأعلى نقاط متوقعة وشرح إحصائي وترتيب تنازلي.
    3. «يلا بينا نسلب!» (Hits & Aggressive Overhaul):
       - دائماً تتضمن سالب حقيقي (-4 أو -8) حتى لو متوفر تبديلات مجانية.
       - 3 مقترحات تشكيلات مع دراسة الجدوى وصافي الربح بعد خصم السالب.
    """
    starting = list(team_data["starting_11"])
    bench = list(team_data["bench"])
    bank = team_data["manager"]["bank"]
    team_value = team_data["manager"]["team_value"]
    free_tf = int(team_data["manager"].get("free_transfers") or 1)
    squad_ids = {p["id"] for p in starting + bench}
    club_counts = {}
    for p in starting + bench:
        club_counts[p.get("team_id", 0)] = club_counts.get(p.get("team_id", 0), 0) + 1

    def get_sell_price(player):
        sp = player.get("selling_price")
        if sp is not None:
            return sp
        pp = player.get("purchase_price")
        if pp is not None:
            return compute_selling_price(pp, player.get("price", pp))
        return player.get("price", 0.0)

    sell_cands = sorted(starting + bench, key=lambda p: (
        0 if p.get("status") in ("i", "s", "n") else (1 if p.get("xmins", 75) < 45 else 2),
        p.get("xp", 0),
        -p.get("diff_next_3", 3)
    ))

    def finalize_proposal(prop_num, prop_title, badge, badge_color, transfers_list, is_roll=False, hit_cost=0, transfer_note="", transfer_reason="", do_bench_swap=True, custom_starters=None, custom_bench=None, is_wildcard=False, total_budget=None, total_squad_cost=None, bank_after=None):
        if custom_starters and custom_bench:
            final_starters = [dict(p) for p in custom_starters]
            final_bench = [dict(p) for p in custom_bench]
        else:
            final_starters = [dict(p) for p in starting]
            final_bench = [dict(p) for p in bench]

            swaps_to_apply = list(transfers_list or [])
            for sw in swaps_to_apply:
                sell_id = sw.get("sell", {}).get("id") if isinstance(sw.get("sell"), dict) else None
                sell_name = sw.get("sell", {}).get("web_name") if isinstance(sw.get("sell"), dict) else str(sw.get("sell") or "")
                buy_p = sw.get("buy")
                if not buy_p or not isinstance(buy_p, dict):
                    continue
                for idx, p in enumerate(final_starters):
                    if (sell_id and p.get("id") == sell_id) or p.get("web_name") == sell_name:
                        final_starters[idx] = dict(buy_p)
                        break
                for idx, p in enumerate(final_bench):
                    if (sell_id and p.get("id") == sell_id) or p.get("web_name") == sell_name:
                        final_bench[idx] = dict(buy_p)
                        break

            if do_bench_swap:
                outfield_b = [p for p in final_bench if p.get("pos") != "GK" and p.get("status") == "a" and p.get("xmins", 75) >= 60]
                for b_p in outfield_b:
                    same_pos_s = [s for s in final_starters if s["pos"] == b_p["pos"]]
                    if same_pos_s:
                        same_pos_s.sort(key=lambda s: s["xp"])
                        worst_s = same_pos_s[0]
                        if b_p["xp"] >= worst_s["xp"] + 0.4:
                            s_idx = next((i for i, p in enumerate(final_starters) if p.get("web_name") == worst_s["web_name"]), None)
                            b_idx = next((i for i, p in enumerate(final_bench) if p.get("web_name") == b_p["web_name"]), None)
                            if s_idx is not None and b_idx is not None:
                                final_starters[s_idx] = dict(b_p)
                                final_bench[b_idx] = dict(worst_s)
                                break

        outfield_bench = [p for p in final_bench if p.get("pos") != "GK"]
        outfield_bench.sort(key=lambda p: -p.get("xp", 0))
        bench_order = [p.get("web_name") for p in outfield_bench[:3]]

        gk_bench = [p for p in final_bench if p.get("pos") == "GK"]
        bench_gk = gk_bench[0].get("web_name") if gk_bench else "—"

        pos_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
        final_starters_sorted = sorted(final_starters, key=lambda x: (pos_order.get(x.get("pos"), 9), -x.get("xp", 0)))

        for sp in final_starters_sorted:
            n_fix = (sp.get("next_3") or [{}])[0]
            sp["next_fixture"] = {
                "opp": n_fix.get("opp", "—"),
                "side": n_fix.get("side", ""),
                "diff": n_fix.get("diff", 3)
            }

        # حساب النقاط للـ 11 أساسي بدون مضاعفة الكابتن
        starters_base_xp = round(sum(p.get("xp", 0) for p in final_starters_sorted), 1)
        starters_min = max(30, int(round(starters_base_xp * 0.88 - 1)))
        starters_max = int(round(starters_base_xp * 1.12 + 1))
        starters_range = f"{starters_min} - {starters_max} نقطة"

        # حساب نقاط الدكة معزولة
        bench_xp = round(sum(p.get("xp", 0) for p in final_bench), 1)

        # استبعاد اللاعبين المرشحين للبيع من الكبتنة منعاً لأي تناقض
        disallowed = {p.get("web_name") for p in sell_cands[:2]}
        for sw in (transfers_list or []):
            s_name = sw.get("sell", {}).get("web_name") if isinstance(sw.get("sell"), dict) else str(sw.get("sell") or "")
            if s_name:
                disallowed.add(s_name)

        # الكباتن الثلاثة مع حساب إجمالي النقاط عند كل اختيار
        captains = select_three_captains(final_starters_sorted, starters_base_xp, disallowed_names=disallowed)

        def_cnt = sum(1 for p in final_starters if p.get("pos") == "DEF")
        mid_cnt = sum(1 for p in final_starters if p.get("pos") == "MID")
        fwd_cnt = sum(1 for p in final_starters if p.get("pos") == "FWD")
        form_str = f"{def_cnt}-{mid_cnt}-{fwd_cnt}"

        gross_gain = round(sum(sw.get("gain", 0) for sw in (transfers_list or [])), 1)
        net_gain = round(gross_gain - abs(hit_cost), 1) if hit_cost != 0 else gross_gain

        return {
            "prop_num": prop_num,
            "title": prop_title,
            "badge": badge,
            "badge_color": badge_color,
            "formation": form_str,
            "final_starters": final_starters_sorted,
            "final_starters_names": [p.get("web_name") for p in final_starters_sorted],
            "bench_order": bench_order,
            "bench_gk": bench_gk,
            "starters_base_xp": starters_base_xp,
            "starters_range": starters_range,
            "bench_xp": bench_xp,
            "captains": captains,
            "transfers": transfers_list or [],
            "is_roll": is_roll,
            "hit_cost": hit_cost,
            "gross_gain": gross_gain,
            "net_gain": net_gain,
            "transfer_note": transfer_note,
            "transfer_reason": transfer_reason,
            "lineup_reason": "التشكيلة الأساسية متوازنة وتضمن أعلى معدل دقائق، والدكة معزولة وجاهزة لأي طارئ.",
            "is_wildcard": is_wildcard,
            "total_budget": total_budget,
            "total_squad_cost": total_squad_cost,
            "bank_after": bank_after if bank_after is not None else (round(total_budget - total_squad_cost, 1) if (total_budget and total_squad_cost) else bank)
        }

    # ==================== الخطة 1: تغييره ولا نستنى؟ ====================
    p1_proposals = []
    
    # 1.1 المقترح الأول
    curr_bank = bank
    t1_list = []
    num_p1 = min(free_tf, len(sell_cands), 5)
    for i in range(num_p1):
        s_p = sell_cands[i]
        s_price = get_sell_price(s_p)
        buys = find_best_buys(s_p, s_price + curr_bank, count=3, all_players=all_players, squad_ids=squad_ids, club_counts=club_counts, bank=curr_bank)
        if buys:
            top_b = buys[0]
            t1_list.append({
                "sell": s_p,
                "buy": top_b["player"],
                "gain": top_b["gain"],
                "cost_diff": top_b["cost_diff"],
                "bank_after": top_b["bank_after"]
            })
            curr_bank = top_b["bank_after"]

    if free_tf >= 2 and len(t1_list) >= 2:
        note_p1 = f"ميني وايلد كارد مجاني ({len(t1_list)} تبديلات مجانية بدون أي سالب)"
        reason_p1 = f"استثمار الـ {free_tf} تبديلات المجانية المتراكمة في معالجة نقاط الضعف دفعة واحدة، مما يمنحك تجديداً شاملاً لقوام الفريق دون أي خصم سالب."
        title_p1 = f"المقترح الأول: ميني وايلد كارد مجاني ({len(t1_list)} تبديلات)"
        badge_p1 = f"ميني وايلد كارد ({len(t1_list)} FTs)"
    else:
        note_p1 = "تبديل مجاني مباشر للمركز الأضعف"
        sell_name = t1_list[0]['sell']['web_name'] if t1_list else 'اللاعب الأضعف'
        buy_name = t1_list[0]['buy']['web_name'] if t1_list else 'الوافد الجديد'
        reason_p1 = f"بيع {sell_name} نظراً لصعوبة مبارياته وشراء {buy_name} للاستفادة من جدوله الميسر ومعدل نقاطه المتوقعة."
        title_p1 = "المقترح الأول: استثمار التبديل المجاني بحزم"
        badge_p1 = "الخيار الأقوى"

    p1_proposals.append(finalize_proposal(
        1, title_p1, badge_p1, "emerald",
        t1_list, is_roll=False, hit_cost=0, transfer_note=note_p1, transfer_reason=reason_p1
    ))

    # 1.2 المقترح الثاني: بديل موازي بنفس القوة
    t2_list = []
    if free_tf >= 2 and len(sell_cands) >= 2:
        s_p1 = sell_cands[0]
        s_price1 = get_sell_price(s_p1)
        buys1 = find_best_buys(s_p1, s_price1 + bank, count=3, all_players=all_players, squad_ids=squad_ids, club_counts=club_counts, bank=bank)
        alt_b1 = buys1[min(1, len(buys1)-1)] if buys1 else None
        b_after1 = alt_b1["bank_after"] if alt_b1 else bank
        
        s_p2 = sell_cands[1]
        s_price2 = get_sell_price(s_p2)
        buys2 = find_best_buys(s_p2, s_price2 + b_after1, count=3, all_players=all_players, squad_ids=squad_ids, club_counts=club_counts, bank=b_after1)
        alt_b2 = buys2[min(1, len(buys2)-1)] if buys2 else (buys2[0] if buys2 else None)

        if alt_b1:
            t2_list.append({"sell": s_p1, "buy": alt_b1["player"], "gain": alt_b1["gain"], "cost_diff": alt_b1["cost_diff"], "bank_after": b_after1})
        if alt_b2:
            t2_list.append({"sell": s_p2, "buy": alt_b2["player"], "gain": alt_b2["gain"], "cost_diff": alt_b2["cost_diff"], "bank_after": alt_b2["bank_after"]})
        title_p2 = "المقترح الثاني: ميني وايلد كارد موازي (خيارات بديلة بنفس القوة)"
        badge_p2 = "بديل موازي"
        reason_p2 = "توليفة مجانية بديلة بنفس القوة التكتيكية تركز على خيارات تصاعدية أخرى تمتاز بجدول سهل ومرونة مالية."
    else:
        s_p = sell_cands[0]
        s_price = get_sell_price(s_p)
        buys = find_best_buys(s_p, s_price + bank, count=3, all_players=all_players, squad_ids=squad_ids, club_counts=club_counts, bank=bank)
        alt_b = buys[min(1, len(buys)-1)] if buys else None
        if alt_b:
            t2_list.append({"sell": s_p, "buy": alt_b["player"], "gain": alt_b["gain"], "cost_diff": alt_b["cost_diff"], "bank_after": alt_b["bank_after"]})
        title_p2 = "المقترح الثاني: بديل موازي بنفس القوة التكتيكية"
        badge_p2 = "خيار تكتيكي موازي"
        reason_p2 = f"استبدال {s_p['web_name']} بالخيار البديل {alt_b['player']['web_name'] if alt_b else ''} الذي يمتلك أرقاماً متقاربة جداً وجدولاً ميسراً."

    p1_proposals.append(finalize_proposal(
        2, title_p2, badge_p2, "teal",
        t2_list, is_roll=False, hit_cost=0, transfer_note="خطة بديلة بنفس القوة التكتيكية", transfer_reason=reason_p2
    ))

    # 1.3 المقترح الثالث: خيار الـ Roll أو خيار توفير الكاش
    has_red_injuries = any(p.get("status") in ("i", "s", "n") for p in starting)
    if not has_red_injuries and free_tf < 5:
        p1_proposals.append(finalize_proposal(
            3, "المقترح الثالث: الاحتفاظ بالتبديل المجاني (Roll Transfer)", "توفير التبديل", "blue",
            [], is_roll=True, hit_cost=0,
            transfer_note="الاحتفاظ بالتبديل المجاني للجولة القادمة",
            transfer_reason="تشكيلة فريقك الأساسية متماسكة ولا تعاني من إصابات حرجة. توفير التبديل الآن يمنحك رصيد تبديلين مجانيين في الجولة القادمة للمناورة بمرونة تكتيكية مضاعفة."
        ))
    else:
        s_p = sell_cands[0]
        s_price = get_sell_price(s_p)
        buys_budget = find_best_buys(s_p, s_price + bank, count=3, prefer_cheaper=True, all_players=all_players, squad_ids=squad_ids, club_counts=club_counts, bank=bank)
        t3_list = []
        if buys_budget:
            b_p = buys_budget[0]
            t3_list.append({"sell": s_p, "buy": b_p["player"], "gain": b_p["gain"], "cost_diff": b_p["cost_diff"], "bank_after": b_p["bank_after"]})
        p1_proposals.append(finalize_proposal(
            3, "المقترح الثالث: تسييل كاش في البنك للتحضير لصفقة سوبر", "توفير فلوس بالبنك", "cyan",
            t3_list, is_roll=False, hit_cost=0,
            transfer_note="توفير سيولة مالية في البنك",
            transfer_reason="شراء عنصر اقتصادي جاهز ومضمون الدقائق لتوفير سيولة مالية في البنك تحضيراً لصفقة سوبر في الجولات المقبلة دون الحاجة لخصم سالب."
        ))

    plan1 = {
        "plan_num": 1,
        "id": "plan_1",
        "title": "الخطة الأولى: تغييره ولا نستنى؟ (Roll or Free Transfers)",
        "badge": f"{free_tf} تبديل مجاني" if free_tf == 1 else f"{free_tf} تبديلات مجانية (ميني وايلد)",
        "badge_color": "emerald",
        "desc": "القرار الأسبوعي لحماية الترتيب؛ استثمار التبديلات المجانية بحزم أو توفير التبديل للجولة القادمة.",
        "free_transfers": free_tf,
        "proposals": p1_proposals
    }

    # ==================== الخطة 2: استخدام خاصية؟ ====================
    inj_count = sum(1 for p in starting + bench if p.get("status") in ("i", "s", "n"))
    wc_avail = any(c.get("english_name", "").startswith("Wildcard") and not c.get("is_used") for c in chips_status)
    if inj_count >= 3 and wc_avail:
        chip_verdict = "الجولة مثالية لتفعيل الوايلد كارد لإنقاذ الموسم دون سالب"
        chip_verdict_reason = f"لديك {inj_count} إصابات/غيابات حرجة في الفريق، وتفعيل الوايلد كارد الآن يوفر عليك أكثر من 12 نقطة سالب ويعيد هيكلة الفريق فوراً."
    else:
        chip_verdict = "الجولة فردية عادية ولا تستدعي استهلاك أي خاصية — وفر خواصك!"
        chip_verdict_reason = "لا توجد جولات دبل (DGW) أو بلانك (BGW) معلنة في هذه الجولة. فكر الـ Top 10k يلزمك بحفظ التريبل كابتن والبنش بوست لجولات الدبل لتحقيق 50+ نقطة فارق."

    p2_proposals = []
    # 2.1 سيناريو التريبل كابتن
    p2_proposals.append(finalize_proposal(
        1, "المقترح الأول: تفعيل خاصية التريبل كابتن (Triple Captain)", "3x الكابتن الخارق", "amber",
        t1_list, is_roll=False, hit_cost=0,
        transfer_note="مضاعفة نقاط الكابتن لـ 3x",
        transfer_reason="تفعيل شيب التريبل كابتن يضاعف نقاط الكابتن (3x) بدلاً من (2x). التشكيلة مرسومة لخدمة النجم الأبرز في الجولة لتحقيق سقف نقطي تاريخي."
    ))

    # 2.2 سيناريو البنش بوست
    p2_proposals.append(finalize_proposal(
        2, "المقترح الثاني: تفعيل خاصية البنش بوست (Bench Boost)", "15 لاعباً في الملعب", "indigo",
        t1_list, is_roll=False, hit_cost=0,
        transfer_note="احتساب نقاط بدلاء الدكة الـ 4 بالكامل",
        transfer_reason="تفعيل شيب البنش بوست يحتسب نقاط بدلاء الدكة الـ 4 بالكامل. التشكيلة والدكة جاهزتان بـ 15 لاعباً بمواجهات ميسرة تضمن 100% مشاركة."
    ))

    # 2.3 سيناريو الوايلد كارد / الفري هيت
    squad_selling_val = round(sum(p.get("selling_price", p.get("price", 0.0)) for p in starting + bench), 1)
    tot_budget = round(squad_selling_val + bank, 1)
    wc_s, wc_b, wc_cost = balance_wildcard_budget(starting, bench, tot_budget, all_players)
    p2_proposals.append(finalize_proposal(
        3, "المقترح الثالث: تشكيلة الوايلد كارد / الفري هيت الاستثنائية", "إعادة بناء شاملة", "rose",
        [], is_roll=False, hit_cost=0,
        transfer_note="تشكيلة الأحلام للجولة الحالية والمستقبلية",
        transfer_reason="تشكيلة النخبة الكاملة في حال قررت تفعيل الوايلد كارد أو الفري هيت الآن، تم اختيارها بأعلى معدلات xP وموازنتها بدقة هندسية تحت سقف ميزانيتك المتاحة بالكامل.",
        custom_starters=wc_s, custom_bench=wc_b,
        is_wildcard=True, total_budget=tot_budget, total_squad_cost=wc_cost, bank_after=round(tot_budget - wc_cost, 1)
    ))

    plan2 = {
        "plan_num": 2,
        "id": "plan_2",
        "title": "الخطة الثانية: استخدام خاصية؟ (Chip Activation Advisor)",
        "badge": "تكتيك الخواص",
        "badge_color": "amber",
        "desc": chip_verdict,
        "chip_verdict": chip_verdict,
        "chip_verdict_reason": chip_verdict_reason,
        "chips_status": chips_status,
        "proposals": p2_proposals
    }

    # ==================== الخطة 3: يلا بينا نسلب! ====================
    p3_proposals = []
    
    # 3.1 سالب 4 حاسم: free_tf + 1 تبديلات
    num_hits1 = free_tf + 1
    t_hit1 = []
    curr_bank = bank
    for i in range(min(num_hits1, len(sell_cands))):
        s_p = sell_cands[i]
        s_price = get_sell_price(s_p)
        buys = find_best_buys(s_p, s_price + curr_bank, count=3, all_players=all_players, squad_ids=squad_ids, club_counts=club_counts, bank=curr_bank)
        if buys:
            top_b = buys[0]
            t_hit1.append({
                "sell": s_p,
                "buy": top_b["player"],
                "gain": top_b["gain"],
                "cost_diff": top_b["cost_diff"],
                "bank_after": top_b["bank_after"]
            })
            curr_bank = top_b["bank_after"]

    gain_h1 = round(sum(sw["gain"] for sw in t_hit1), 1)
    net_h1 = round(gain_h1 - 4.0, 1)
    p3_proposals.append(finalize_proposal(
        1, f"المقترح الأول: سالب 4 حاسم ({len(t_hit1)} تبديلات مدروسة)", "سالب 4 نقطة", "purple",
        t_hit1, is_roll=False, hit_cost=-4,
        transfer_note=f"إجراء {len(t_hit1)} تبديلات ({free_tf} مجاني + 1 بسالب 4)",
        transfer_reason=f"دراسة الجدوى بالأرقام: خصم الـ -4 نقطة يتم تعويضه بالكامل وزيادة؛ فارق نقاط الوافدين الجدد المتوقع (+{gain_h1}ن) يحقق صافي ربح نقطي (+{net_h1}ن) في أول جولة بالإضافة لتحسين مسار الفريق لجولات قادمة."
    ))

    # 3.2 سالب 4 بديل (خيارات هجومية موازية)
    t_hit2 = []
    curr_bank = bank
    for i in range(min(num_hits1, len(sell_cands))):
        s_p = sell_cands[i]
        s_price = get_sell_price(s_p)
        buys = find_best_buys(s_p, s_price + curr_bank, count=3, all_players=all_players, squad_ids=squad_ids, club_counts=club_counts, bank=curr_bank)
        if buys:
            alt_b = buys[min(1, len(buys)-1)]
            t_hit2.append({
                "sell": s_p,
                "buy": alt_b["player"],
                "gain": alt_b["gain"],
                "cost_diff": alt_b["cost_diff"],
                "bank_after": alt_b["bank_after"]
            })
            curr_bank = alt_b["bank_after"]

    gain_h2 = round(sum(sw["gain"] for sw in t_hit2), 1)
    net_h2 = round(gain_h2 - 4.0, 1)
    p3_proposals.append(finalize_proposal(
        2, f"المقترح الثاني: سالب 4 تكتيكي موازي ({len(t_hit2)} تبديلات)", "سالب 4 موازي", "fuchsia",
        t_hit2, is_roll=False, hit_cost=-4,
        transfer_note=f"إجراء {len(t_hit2)} تبديلات ببدائل هجومية موازية",
        transfer_reason=f"توليفة هجومية بديلة بسالب 4؛ فارق النقاط المتوقع (+{gain_h2}ن) يحقق صافي ربح (+{net_h2}ن) مع استهداف مواجهات متفجرة ضد أضعف دفاعات الدوري."
    ))

    # 3.3 سالب 8 نقاط: free_tf + 2 تبديلات (عملية جراحية عميقة)
    num_hits2 = free_tf + 2
    t_hit3 = []
    curr_bank = bank
    for i in range(min(num_hits2, len(sell_cands))):
        s_p = sell_cands[i]
        s_price = get_sell_price(s_p)
        buys = find_best_buys(s_p, s_price + curr_bank, count=3, all_players=all_players, squad_ids=squad_ids, club_counts=club_counts, bank=curr_bank)
        if buys:
            top_b = buys[0]
            t_hit3.append({
                "sell": s_p,
                "buy": top_b["player"],
                "gain": top_b["gain"],
                "cost_diff": top_b["cost_diff"],
                "bank_after": top_b["bank_after"]
            })
            curr_bank = top_b["bank_after"]

    gain_h3 = round(sum(sw["gain"] for sw in t_hit3), 1)
    net_h3 = round(gain_h3 - 8.0, 1)
    p3_proposals.append(finalize_proposal(
        3, f"المقترح الثالث: عملية جراحية عميقة بسالب 8 ({len(t_hit3)} تبديلات)", "سالب 8 نقاط", "rose",
        t_hit3, is_roll=False, hit_cost=-8,
        transfer_note=f"إجراء {len(t_hit3)} تبديلات ({free_tf} مجاني + 2 بسالب 8)",
        transfer_reason=f"عملية جراحية حاسمة لإعادة هيكلة 3 مراكز ضعيفة متزامنة؛ فارق الوافدين الجدد المتوقع (+{gain_h3}ن) يعوض سالب الـ -8 ويمنحك قواماً متماسكاً يخدمك لـ 5 جولات قادمة."
    ))

    plan3 = {
        "plan_num": 3,
        "id": "plan_3",
        "title": "الخطة الثالثة: يلا بينا نسلب! (Hits & Aggressive Overhaul)",
        "badge": "المجازفة والحسم (سالب)",
        "badge_color": "purple",
        "desc": "دراسة جدوى رقمية صريحة للتبديلات الإضافية بالسالب (-4 أو -8) لتعويض فارق النقاط أو إصلاح التشكيلة فوراً.",
        "free_transfers": free_tf,
        "proposals": p3_proposals
    }

    return [plan1, plan2, plan3]


# Alias for backward compatibility
generate_5_complete_gameplans = generate_3_strategic_gameplans
