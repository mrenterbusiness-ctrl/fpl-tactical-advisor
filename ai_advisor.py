# -*- coding: utf-8 -*-
"""
FPL Advisor AI Engine — العقل التحليلي بالذكاء الاصطناعي (Gemini Integration)
تكامل فائق الذكاء والدقة مع أحدث نماذج Google Gemini لصياغة خطط واستراتيجيات
فانتازي الدوري الإنجليزي الممتاز (FPL) بأسلوب كبار نقاد ومحللي الاستوديوهات الكروية.
"""

import os
import sys
import json
import urllib.request
import urllib.error

# ضبط ترميز الإخراج لمنع أخطاء charmap في ويندوز
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
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_env_file()

# المفتاح يتم قراءته بأمان من متغيرات البيئة
DEFAULT_API_KEY = os.environ.get("GEMINI_API_KEY", "")


def get_available_models(api_key):
    """استعلام مباشر لمعرفة الموديلات المتاحة لمفتاح API"""
    clean_key = api_key.strip()
    urls = [
        f"https://generativelanguage.googleapis.com/v1beta/models?key={clean_key}",
        "https://generativelanguage.googleapis.com/v1beta/models"
    ]
    for ep in urls:
        try:
            headers = {} if "?key=" in ep else {"x-goog-api-key": clean_key}
            req = urllib.request.Request(ep, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = []
                for m in data.get("models", []):
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods:
                        name = m.get("name", "").replace("models/", "")
                        if name:
                            models.append(name)
                if models:
                    return models
        except Exception:
            continue
    return []


def call_gemini_json(prompt, api_key):
    """استدعاء سريع ومحمي لـ Gemini مع دعم أحدث الموديلات النشطة"""
    clean_key = api_key.strip()
    discovered = get_available_models(clean_key)
    
    # قائمة الموديلات الحديثة النشطة مع تفضيل الموديلات السريعة والمستقرة
    priority_models = [
        "gemini-3-flash-preview",
        "gemini-flash-latest",
        "gemini-2.5-flash",
        "gemini-3.1-flash-lite-preview",
        "gemini-3.8-flash",
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-2.5-pro"
    ]
    
    if discovered:
        models_to_try = [m for m in priority_models if m in discovered]
        for dm in discovered:
            if "flash" in dm.lower() and dm not in models_to_try:
                models_to_try.append(dm)
        if not models_to_try:
            models_to_try = discovered[:3]
    else:
        models_to_try = priority_models

    last_err = None

    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.25
            }
        }
        data = json.dumps(payload).encode("utf-8")
        
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": clean_key
            }
        )
        
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                try:
                    print(f"[AI Advisor] تم التحليل بنجاح بواسطة الذكاء الاصطناعي ({model})!")
                except Exception:
                    pass
                return parsed, None
        except urllib.error.HTTPError as e:
            last_err = f"HTTP Error {e.code}: {e.reason}"
            if e.code in (404, 503, 429):
                continue
            break
        except Exception as e:
            last_err = str(e)
            break
    
    return None, last_err or "تعذر الاتصال بسيرفرات جوجل"


def build_ai_prompt(team_data, all_players, next_gw):
    """بناء برومبت احترافي متكامل يتضمن سجل الـ 3 مباريات وأسلوب التحليل الكروي الراقي"""
    m = team_data["manager"]
    starting = team_data["starting_11"]
    bench = team_data["bench"]
    fixtures = team_data.get("fixtures", [])
    chips = team_data.get("chips", [])
    
    starters_summary = []
    for p in starting:
        nxt = p.get("next_3", [])
        fix_str = " -> ".join([f"{x['opp']} {x['side']} (صعوبة {x['diff']})" for x in nxt]) if nxt else "—"
        starters_summary.append({
            "name": p["web_name"],
            "pos": p["pos"],
            "team": p["team_short"],
            "price": p["price"],
            "xP": p["xp"],
            "form": p.get("form", 0),
            "status": p.get("status_ar", "جاهز"),
            "ownership": f"{p.get('selected_by_percent', 0)}%",
            "last_3": p.get("last_3_summary", "غير متوفر"),
            "penalties": p.get("is_pen_taker", False),
            "next_3": fix_str
        })

    bench_summary = []
    for p in bench:
        nxt = p.get("next_3", [])
        fix_str = " -> ".join([f"{x['opp']} {x['side']} (صعوبة {x['diff']})" for x in nxt]) if nxt else "—"
        bench_summary.append({
            "name": p["web_name"],
            "pos": p["pos"],
            "team": p["team_short"],
            "price": p["price"],
            "xP": p["xp"],
            "ownership": f"{p.get('selected_by_percent', 0)}%",
            "last_3": p.get("last_3_summary", "غير متوفر"),
            "next_3": fix_str
        })

    market_picks = []
    squad_ids = {p["id"] for p in starting + bench}
    for p in all_players.values():
        if p["id"] in squad_ids or not p.get("can_select") or p.get("status") not in ("a", "d"):
            continue
        if p.get("diff_next_3", 3) <= 2.8 and p.get("xmins", 0) >= 65 and p.get("xp", 0) >= 4.0:
            market_picks.append({
                "name": p["web_name"],
                "pos": p["pos"],
                "team": p["team_short"],
                "price": p["price"],
                "xP": p["xp"],
                "ownership": f"{p.get('selected_by_percent', 0)}%",
                "last_3": p.get("last_3_summary", "جاهز"),
                "next_match": (p.get("next_3") or [{}])[0]
            })
    market_picks.sort(key=lambda x: -x["xP"])
    market_picks = market_picks[:10]

    squad_all = team_data.get("squad_all", [])
    squad_selling_val = round(sum(p.get("selling_price", p.get("price", 0.0)) for p in squad_all if p.get("price")), 1)
    if squad_selling_val <= 0:
        squad_selling_val = round(float(m.get("team_value", 100.0)), 1)
    bank_val = round(float(m.get("bank", 0.0)), 1)
    total_budget_val = round(squad_selling_val + bank_val, 1)

    free_transfers = int(m.get("free_transfers") or 1)
    prompt = f"""
أنت خبير ومحلل تكتيكي لفانتازي الدوري الإنجليزي الممتاز (FPL) يضع خططه بناءً على معايير نخبة مدربي الـ Top 10,000 عالمياً.
أسلوبك في الكتابة: لغة عربية عامية مصرية راقية، هادئة، وسلسة (بأسلوب كبار المحللين والنقاد الرياضيين في البرامج والبودكاستات الكروية)، بدون أي مبالغة أو تهويل أو مصطلحات شعبية فجة (ممنوع الأفورة، ممنوع التناقضات، ممنوع الجمل المعلبة)، مع التركيز الكامل على الأرقام، الدقائق، ونقاط القوة والضعف الدفاعية والهجومية.

مهمتك: فحص تشكيلة المدرب وأداء لاعبيه في آخر 3 ماتشات، وماتشات الجولة القادمة ({next_gw}) وتوليد 3 ركائز استراتيجية متكاملة بصيغة JSON، وداخل كل خطة 3 مقترحات تشكيلات جاهزة في الملعب:

بيانات تشكيلة المدرب والميزانية المالية الرسمية:
- التبديلات المجانية المتاحة: {free_transfers} تبديل
- الكاش المتاح في البنك للتبديلات: £{bank_val}m
- القيمة البيعية الحالية لتشكيلة المدرب (Selling Value): £{squad_selling_val}m
- إجمالي الميزانية القصوى المتاحة للوايلد كارد (سعر البيع + البنك): £{total_budget_val}m
- التشكيل الحالي: {team_data['formation']}
- رصيد خواص الفانتازي (Chips): {json.dumps(chips, ensure_ascii=False)}

اللاعبون الأساسيون (11 لاعب):
{json.dumps(starters_summary, ensure_ascii=False, indent=2)}

مقاعد البدلاء (4 لاعبين):
{json.dumps(bench_summary, ensure_ascii=False, indent=2)}

أبرز خيارات السوق المتاحة بجدول ميسر:
{json.dumps(market_picks, ensure_ascii=False, indent=2)}

القواعد الفنية والمالية الصارمة:
1. الركائز الثلاثة المطلوبة حصراً:
   - الخطة 1: «تغييره ولا نستنى؟ (Roll or Free Transfers)»:
     * إذا كان مع المدرب {free_transfers} تبديلات (2 أو أكثر): الاقتراح الأول ميني وايلد كارد مجاني يستغل التبديلات بالكامل بدون سالب!
     * المقترح الثاني بديل موازي بنفس القوة التكتيكية.
     * المقترح الثالث الاحتفاظ بالتبديل (Roll Transfer) إذا لم تكن هناك إصابات، أو توفير كاش.
   - الخطة 2: «استخدام خاصية؟ (Chip Activation Advisor)»:
     * تقديم تقرير حاسم هل الجولة مناسبة لخاصية أم لا (لو جولة فردية عادية: وفر خواصك!).
     * 3 مقترحات/سيناريوهات لتفعيل الخواص المتاحة (تريبل كابتن، بنش بوست، وايلد كارد/فري هيت) مع تشكيلاتها وشرحها.
   - الخطة 3: «يلا بينا نسلب! (Hits & Aggressive Overhaul)»:
     * تتضمن دائماً سالب حقيقي (-4 أو -8) حتى لو متوفر تبديلات مجانية!
     * دراسة جدوى رقمية لحساب صافي الربح بعد خصم السالب.
2. قواعد الميزانية وسلامة التشكيلة (Financial & Squad Rules - غير قابلة للمخالفة):
   - في التبديلات العادية (الخطة 1 والخطة 3 وسيناريوهات التريبل والبنش بوست):
     * التشكيلة الأساسية (11) والدكة (4) تتكون حصراً من لاعبي تشكيلة المدرب الحالية بعد تبديل المغادرين بالقادمين المذكورين في transfers فقط! ممنوع بتاتاً إضافة أي لاعب جديد في final_starters لم يتم ذكره صراحة في transfers.
     * فارق السعر الصافي للتبديل (تكلفة القادمين - سعر بيع المغادرين) يجب ألا يتجاوز رصيد البنك المتاح (£{bank_val}m).
   - في مقترح الوايلد كارد / الفري هيت (الخطة 2 المقترح 3):
     * يحق لك إعادة بناء تشكيلة كاملة بـ 15 لاعباً.
     * شـرط مـالـي صـارم: مجموع أسعار الـ 15 لاعباً بالكامل (11 أساسياً + 4 بدلاء) ممنوع منعاً باتاً أن يتجاوز إجمالي الميزانية (£{total_budget_val}m)!
     * التزم بذكاء محترفي الفانتازي: اختر نجمين أو 3 نجوم كبار (مثل هالاند أو صلاح أو ترينت)، وباقي التشكيلة عناصر وسط ودفاع متميزة مع دكة اقتصادية بأسعار 4.0m و 4.5m حتى تتسع الميزانية ويبقى رصيد كاش في البنك.
3. منظومة الكباتن الثلاثة في كل مقترح:
   - safe: الكبتنة المضمونة (Safe) لحماية الترتيب العام.
   - tactical: كبتنة فيها فكرة (Tactical) مدعومة بالأرقام و xG/xA.
   - risky: كبتنة ريسكي (Differential) بملكية منخفضة لصناعة الفارق.
   * قاعدة الاتساق الصارمة (ممنوع التناقض نهائياً): ممنوع منعاً باتاً كبتنة أي لاعب تم ترشيح بيعه في أي مقترح آخر أو في نفس الخطة، أو لاعب مصاب، أو لاعب يواجه مباراة دفاعية صعبة خارج ملعبه. الكباتن الثلاثة يجب أن يكونوا حصراً من أقوى وأجهز عناصر التشكيلة الأساسية وأسهلهم مواجهات!
4. التشكيلة الأساسية 11 لاعب (final_starters) والدكة 3 لاعبي ميدان (bench_order) وحارس مرمى منفصل (bench_gk).

المطلوب إرجاع مصفوفة من 3 خطط كالتالي بصيغة JSON حصراً:
[
  {{
    "plan_num": 1,
    "id": "plan_1",
    "title": "الخطة الأولى: تغييره ولا نستنى؟ (Roll or Free Transfers)",
    "badge": "القرار الأسبوعي",
    "badge_color": "emerald",
    "desc": "استثمار التبديلات المجانية لحماية الترتيب أو الاحتفاظ بالتبديل للجولة المقبلة.",
    "free_transfers": {free_transfers},
    "proposals": [
      {{
        "prop_num": 1,
        "title": "المقترح الأول: استثمار التبديل المجاني بحزم",
        "badge": "الخيار الأقوى",
        "badge_color": "emerald",
        "final_starters": ["لاعب 1", "لاعب 2", "..."],
        "bench_order": ["بديل 1", "بديل 2", "بديل 3"],
        "bench_gk": "اسم الحارس الاحتياطي",
        "transfers": [
          {{"sell": "اسم المغادر", "buy": "اسم القادم", "gain": 2.5, "cost_diff": -0.2}}
        ],
        "is_roll": false,
        "hit_cost": 0,
        "transfer_note": "ملخص التبديل في جملة واحدة",
        "transfer_reason": "شرح تكتيكي فني مفصل بالعامية المصرية الراقية لسبب هذا التبديل...",
        "captains": {{
          "safe": {{"name": "اسم الكابتن المضمون", "reason": "سبب الكبتنة المضمونة..."}},
          "tactical": {{"name": "اسم كابتن الفكرة", "reason": "سبب كبتنة الفكرة..."}},
          "risky": {{"name": "اسم الكابتن الريسكي", "reason": "سبب الكبتنة الريسكي..."}}
        }}
      }},
      {{
        "prop_num": 2,
        "title": "المقترح الثاني: بديل موازي بنفس القوة التكتيكية",
        "badge": "بديل موازي",
        "badge_color": "teal",
        "final_starters": ["..."],
        "bench_order": ["..."],
        "bench_gk": "...",
        "transfers": [],
        "is_roll": false,
        "hit_cost": 0,
        "transfer_note": "...",
        "transfer_reason": "...",
        "captains": {{"safe": {{"name": "...", "reason": "..."}}, "tactical": {{"name": "...", "reason": "..."}}, "risky": {{"name": "...", "reason": "..."}}}}
      }},
      {{
        "prop_num": 3,
        "title": "المقترح الثالث: الاحتفاظ بالتبديل المجاني (Roll Transfer)",
        "badge": "توفير التبديل",
        "badge_color": "blue",
        "final_starters": ["..."],
        "bench_order": ["..."],
        "bench_gk": "...",
        "transfers": [],
        "is_roll": true,
        "hit_cost": 0,
        "transfer_note": "الاحتفاظ بالتبديل للجولة القادمة",
        "transfer_reason": "...",
        "captains": {{"safe": {{"name": "...", "reason": "..."}}, "tactical": {{"name": "...", "reason": "..."}}, "risky": {{"name": "...", "reason": "..."}}}}
      }}
    ]
  }},
  {{
    "plan_num": 2,
    "id": "plan_2",
    "title": "الخطة الثانية: استخدام خاصية؟ (Chip Activation Advisor)",
    "badge": "تكتيك الخواص",
    "badge_color": "amber",
    "desc": "تقرير حاسم حول مدى جدوى تفعيل وسائل المساعدة في هذه الجولة.",
    "chip_verdict": "الجولة فردية عادية ولا تستدعي استهلاك أي خاصية — وفر خواصك!",
    "chip_verdict_reason": "شرح إحصائي لسبب توفير أو تفعيل الخاصية...",
    "proposals": [
      {{
        "prop_num": 1,
        "title": "المقترح الأول: تفعيل خاصية التريبل كابتن (Triple Captain)",
        "badge": "3x الكابتن الخارق",
        "badge_color": "amber",
        "final_starters": ["..."],
        "bench_order": ["..."],
        "bench_gk": "...",
        "transfers": [],
        "is_roll": false,
        "hit_cost": 0,
        "transfer_note": "مضاعفة نقاط الكابتن لـ 3x",
        "transfer_reason": "...",
        "captains": {{"safe": {{"name": "...", "reason": "..."}}, "tactical": {{"name": "...", "reason": "..."}}, "risky": {{"name": "...", "reason": "..."}}}}
      }},
      {{
        "prop_num": 2,
        "title": "المقترح الثاني: تفعيل خاصية البنش بوست (Bench Boost)",
        "badge": "15 لاعباً في الملعب",
        "badge_color": "indigo",
        "final_starters": ["..."],
        "bench_order": ["..."],
        "bench_gk": "...",
        "transfers": [],
        "is_roll": false,
        "hit_cost": 0,
        "transfer_note": "احتساب نقاط بدلاء الدكة بالكامل",
        "transfer_reason": "...",
        "captains": {{"safe": {{"name": "...", "reason": "..."}}, "tactical": {{"name": "...", "reason": "..."}}, "risky": {{"name": "...", "reason": "..."}}}}
      }},
      {{
        "prop_num": 3,
        "title": "المقترح الثالث: تشكيلة الوايلد كارد / الفري هيت الاستثنائية",
        "badge": "إعادة بناء شاملة",
        "badge_color": "rose",
        "final_starters": ["..."],
        "bench_order": ["..."],
        "bench_gk": "...",
        "transfers": [],
        "is_roll": false,
        "hit_cost": 0,
        "transfer_note": "تشكيلة الأحلام للجولة الحالية والمستقبلية",
        "transfer_reason": "...",
        "captains": {{"safe": {{"name": "...", "reason": "..."}}, "tactical": {{"name": "...", "reason": "..."}}, "risky": {{"name": "...", "reason": "..."}}}}
      }}
    ]
  }},
  {{
    "plan_num": 3,
    "id": "plan_3",
    "title": "الخطة الثالثة: يلا بينا نسلب! (Hits & Aggressive Overhaul)",
    "badge": "المجازفة والحسم (سالب)",
    "badge_color": "purple",
    "desc": "دراسة جدوى صريحة للتبديلات الإضافية بالسالب (-4 أو -8) لتعويض فارق النقاط فوراً.",
    "free_transfers": {free_transfers},
    "proposals": [
      {{
        "prop_num": 1,
        "title": "المقترح الأول: سالب 4 حاسم",
        "badge": "سالب 4 نقطة",
        "badge_color": "purple",
        "final_starters": ["..."],
        "bench_order": ["..."],
        "bench_gk": "...",
        "transfers": [],
        "is_roll": false,
        "hit_cost": -4,
        "transfer_note": "إجراء تبديل إضافي بسالب 4 مدروس بالأرقام",
        "transfer_reason": "دراسة الجدوى بالأرقام: خصم الـ -4 يتم تعويضه من فارق النقاط...",
        "captains": {{"safe": {{"name": "...", "reason": "..."}}, "tactical": {{"name": "...", "reason": "..."}}, "risky": {{"name": "...", "reason": "..."}}}}
      }},
      {{
        "prop_num": 2,
        "title": "المقترح الثاني: سالب 4 تكتيكي موازي",
        "badge": "سالب 4 موازي",
        "badge_color": "fuchsia",
        "final_starters": ["..."],
        "bench_order": ["..."],
        "bench_gk": "...",
        "transfers": [],
        "is_roll": false,
        "hit_cost": -4,
        "transfer_note": "...",
        "transfer_reason": "...",
        "captains": {{"safe": {{"name": "...", "reason": "..."}}, "tactical": {{"name": "...", "reason": "..."}}, "risky": {{"name": "...", "reason": "..."}}}}
      }},
      {{
        "prop_num": 3,
        "title": "المقترح الثالث: عملية جراحية عميقة بسالب 8",
        "badge": "سالب 8 نقاط",
        "badge_color": "rose",
        "final_starters": ["..."],
        "bench_order": ["..."],
        "bench_gk": "...",
        "transfers": [],
        "is_roll": false,
        "hit_cost": -8,
        "transfer_note": "...",
        "transfer_reason": "...",
        "captains": {{"safe": {{"name": "...", "reason": "..."}}, "tactical": {{"name": "...", "reason": "..."}}, "risky": {{"name": "...", "reason": "..."}}}}
      }}
    ]
  }}
]
"""
    return prompt


def sanitize_ai_plans(plans, team_data):
    """تنقية ردود الذكاء الاصطناعي وربط كروت اللاعبين وعزل نقاط الدكة وحساب الكباتن الثلاثة"""
    squad_map = {p["web_name"]: p for p in team_data.get("squad_all", [])}
    starting = team_data.get("starting_11", [])
    bench = team_data.get("bench", [])
    bench_gk_name = next((p["web_name"] for p in bench if p["pos"] == "GK"), "—")
    outfield_bench_names = [p["web_name"] for p in bench if p["pos"] != "GK"]

    sanitized = []
    for plan in plans:
        p_clean = dict(plan)
        proposals = p_clean.get("proposals", [])
        clean_props = []

        for prop in proposals:
            pr = dict(prop)
            # التأكد من التشكيلة الأساسية
            raw_starters = pr.get("final_starters", [])
            starters_names = []
            for item in raw_starters:
                name = item.get("web_name") if isinstance(item, dict) else str(item)
                if name:
                    starters_names.append(name)
            if len(starters_names) < 11:
                for sp in starting:
                    if sp["web_name"] not in starters_names:
                        starters_names.append(sp["web_name"])
                    if len(starters_names) >= 11:
                        break
            pr["final_starters"] = starters_names[:11]

            # التأكد من الدكة
            raw_bench = pr.get("bench_order", [])
            clean_b = [b for b in raw_bench if b and b not in starters_names and b != bench_gk_name]
            for ob in outfield_bench_names:
                if ob not in clean_b and ob not in starters_names:
                    clean_b.append(ob)
            pr["bench_order"] = clean_b[:3]
            pr["bench_gk"] = pr.get("bench_gk") or bench_gk_name

            # حساب النقاط للـ 11 أساسي
            starters_sum = sum(squad_map[name]["xp"] for name in pr["final_starters"] if name in squad_map)
            pr["starters_base_xp"] = round(starters_sum if starters_sum > 20 else 65.0, 1)

            # حساب نقاط الدكة
            bench_sum = sum(squad_map[name]["xp"] for name in pr["bench_order"] if name in squad_map)
            if pr["bench_gk"] in squad_map:
                bench_sum += squad_map[pr["bench_gk"]]["xp"]
            pr["bench_xp"] = round(bench_sum if bench_sum > 0 else 12.0, 1)

            clean_props.append(pr)

        p_clean["proposals"] = clean_props
        sanitized.append(p_clean)

    return sanitized


def generate_gameplans_with_ai(team_data, all_players, next_gw, api_key=None):
    """توليد الخطط الـ 3 الاستراتيجية عبر Gemini مع معالجة الأخطاء والتنقية التلقائية"""
    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or DEFAULT_API_KEY
    if not key:
        return None, "لم يتم العثور على مفتاح API"
    
    try:
        prompt = build_ai_prompt(team_data, all_players, next_gw)
        plans, err = call_gemini_json(prompt, key)
        if plans and isinstance(plans, list) and len(plans) == 3:
            plans = sanitize_ai_plans(plans, team_data)
            return plans, None
        return None, err or f"الرد لم يطابق صيغة الـ 3 خطط المطلوبة (عُثر على {len(plans) if isinstance(plans, list) else 0})"
    except Exception as e:
        err_str = str(e)
        print(f"[AI Advisor Exception]: {err_str}")
        return None, err_str
