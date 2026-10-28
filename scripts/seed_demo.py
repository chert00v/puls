"""Синтетический демо-сценарий (20 pre + 20 post). Только стандартная библиотека.
Шаг 1:  python scripts/seed_demo.py pre            -> создаёт ОТДЕЛЬНУЮ тестовую сессию и шлёт 20 pre-отправок
Шаг 2:  в UI: Разбор -> Проанализировать -> Одобрить -> Начать повторную проверку
Шаг 3:  python scripts/seed_demo.py post <session_id> <teacher_key> <code>   -> шлёт 20 post-отправок
Ожидание: 35.0% -> 80.0% (+45.0 п.п.)  (post: q1 верно 17/20, q2 верно 15/20)
"""
import json, os, sys, urllib.request

BASE = os.getenv("API", "http://localhost:8000")

def call(path, method="GET", body=None, key=None):
    h = {"Content-Type": "application/json"}
    if key: h["X-Teacher-Key"] = key
    r = urllib.request.Request(BASE + path, method=method, headers=h, data=None if body is None else json.dumps(body).encode())
    with urllib.request.urlopen(r) as resp: return json.load(resp)

def pre(code):
    for i in range(20):
        a = [(0 if i < 7 else 1), (0 if i < 8 else 1), (0 if i < 6 else 2)]  # верных 7, 8, 6 из 20 => 35%
        call(f"/api/public/{code}/submit", "POST", {"round": "pre", "answers": [{"question_id": f"pre_q{n+1}", "selected_index": x} for n, x in enumerate(a)]})

def post(code, sid, key):
    qs = call(f"/api/admin/sessions/{sid}/stats", key=key)["rounds"]["post"]["questions"]
    ok = [17, 15]  # верных из 20
    for i in range(20):
        ans = []
        for n, q in enumerate(qs):
            c = q["correct_index"]; ans.append({"question_id": q["question_id"], "selected_index": c if i < ok[n] else (c + 1) % len(q["options"])})
        call(f"/api/public/{code}/submit", "POST", {"round": "post", "answers": ans})

if __name__ == "__main__":
    if sys.argv[1:2] == ["pre"]:
        s = call("/api/sessions", "POST", {"topic_id": "python_range"}); pre(s["code"])
        print("СИНТЕТИЧЕСКАЯ тестовая сессия создана, 20 pre-отправок отправлено.")
        print(f"Ссылка: http://localhost:5173/teacher/{s['session_id']}\nВставьте в консоль браузера (F12) на странице сайта, затем откройте ссылку:")
        print(f"sessionStorage.setItem('teacherKey:{s['session_id']}','{s['teacher_key']}');sessionStorage.setItem('code:{s['session_id']}','{s['code']}');sessionStorage.setItem('synthetic:{s['session_id']}','1')")
        print(f"\nДля шага 3 сохраните: {s['session_id']} {s['teacher_key']} {s['code']}")
    elif sys.argv[1:2] == ["post"] and len(sys.argv) == 5:
        post(sys.argv[4], sys.argv[2], sys.argv[3]); print("20 post-отправок отправлено. Откройте /results.")
    else:
        print(__doc__)
