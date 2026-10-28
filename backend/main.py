import hashlib, hmac, json, os, secrets, sqlite3, string, uuid
from pathlib import Path
from contextlib import contextmanager
from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from backend.ai.analyzer import AIUnavailableError, NewQ, Proposal, analyze_aggregates, generate_questions

DB = os.getenv("PULSE_DB", "pulse.db")
PRE = [("pre_q1", "Что напечатает print(list(range(3)))?", ["[0, 1, 2]", "[1, 2, 3]", "[0, 1, 2, 3]"], 0),
       ("pre_q2", "Что вернёт list(range(1, 4))?", ["[1, 2, 3]", "[1, 2, 3, 4]", "[0, 1, 2, 3]"], 0),
       ("pre_q3", "Что вернёт list(range(2, 5))?", ["[2, 3, 4]", "[2, 3, 4, 5]", "[1, 2, 3, 4]"], 0)]
SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, code TEXT UNIQUE, key_hash TEXT, topic_id TEXT, topic TEXT, state TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS questions(sid TEXT, qid TEXT, round TEXT, concept_id TEXT, text TEXT, options TEXT, correct_index INT, n INT, PRIMARY KEY(sid,qid));
CREATE TABLE IF NOT EXISTS option_counts(sid TEXT, qid TEXT, idx INT, count INT DEFAULT 0, PRIMARY KEY(sid,qid,idx));
CREATE TABLE IF NOT EXISTS round_counts(sid TEXT, round TEXT, submissions INT DEFAULT 0, PRIMARY KEY(sid,round));
CREATE TABLE IF NOT EXISTS proposals(sid TEXT PRIMARY KEY, status TEXT, body TEXT);
"""

class ApiError(Exception):
    def __init__(s, status, code, msg): s.status, s.code, s.msg = status, code, msg

app = FastAPI(title="Пульс класса")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(ApiError)
async def _api(_, e): return JSONResponse({"error": {"code": e.code, "message": e.msg}}, e.status)
@app.exception_handler(RequestValidationError)
async def _val(_, e): return JSONResponse({"error": {"code": "INVALID_REQUEST", "message": "Некорректный запрос"}}, 422)

@contextmanager
def db():
    c = sqlite3.connect(DB, timeout=10, isolation_level=None); c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=10000"); c.execute("PRAGMA journal_mode=WAL")
    try: yield c
    finally: c.close()

def init_db():
    with db() as c: c.executescript(SCHEMA)

init_db()

def add_question(c, sid, qid, rnd, concept, text, options, ci, n):
    c.execute("INSERT INTO questions VALUES(?,?,?,?,?,?,?,?)", (sid, qid, rnd, concept, text, json.dumps(options, ensure_ascii=False), ci, n))
    for i in range(len(options)): c.execute("INSERT INTO option_counts(sid,qid,idx) VALUES(?,?,?)", (sid, qid, i))

def auth(c, sid, key):
    s = c.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if not s: raise ApiError(404, "SESSION_NOT_FOUND", "Сессия не найдена")
    if not key or not hmac.compare_digest(hashlib.sha256(key.encode()).hexdigest(), s["key_hash"]):
        raise ApiError(401, "UNAUTHORIZED", "Неверный или отсутствует ключ преподавателя")
    return s

@app.post("/api/sessions", status_code=201)
async def create_session(body: dict):
    topic_id, topic, pre, concept = "python_range", "Python: range()", PRE, "python_range"
    if "questions" in body:  # своя тема: 3 вопроса, проверенные учителем
        topic, qs = str(body.get("topic", "")).strip(), body["questions"]
        if not 3 <= len(topic) <= 100 or not isinstance(qs, list) or not 3 <= len(qs) <= 15: raise ApiError(422, "INVALID_TOPIC", "Нужна тема и от 3 до 15 вопросов")
        pre = []
        try:
            for n, q in enumerate(qs, 1):
                v = NewQ(text=q.get("text"), options=q.get("options"), correct_index=q.get("correct_index"), concept_id="custom_topic")
                pre.append((f"pre_q{n}", v.text, v.options, v.correct_index))
        except (ValueError, TypeError, AttributeError): raise ApiError(422, "INVALID_QUESTIONS", "Вопросы не прошли проверку")
        topic_id, concept = "custom", "custom_topic"
    elif body.get("topic_id") != "python_range": raise ApiError(422, "UNKNOWN_TOPIC", "Нужна своя тема с вопросами или topic_id=python_range")
    sid, key = str(uuid.uuid4()), secrets.token_urlsafe(32)
    with db() as c:
        while True:
            code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            if not c.execute("SELECT 1 FROM sessions WHERE code=?", (code,)).fetchone(): break
        c.execute("BEGIN IMMEDIATE")
        c.execute("INSERT INTO sessions(id,code,key_hash,topic_id,topic,state) VALUES(?,?,?,?,?,?)",
                  (sid, code, hashlib.sha256(key.encode()).hexdigest(), topic_id, topic, "pre_open"))
        for n, (qid, t, o, ci) in enumerate(pre): add_question(c, sid, qid, "pre", concept, t, o, ci, n)
        c.execute("INSERT INTO round_counts(sid,round) VALUES(?,'pre')", (sid,)); c.execute("COMMIT")
    return {"session_id": sid, "code": code, "topic_id": topic_id, "topic": topic, "state": "pre_open", "teacher_key": key}

@app.post("/api/generate-questions")
async def gen_questions(body: dict):
    topic = str(body.get("topic", "")).strip()
    if not 3 <= len(topic) <= 100: raise ApiError(422, "INVALID_TOPIC", "Тема: от 3 до 100 символов")
    try: n = max(3, min(15, int(body.get("count", 5))))
    except (TypeError, ValueError): raise ApiError(422, "INVALID_COUNT", "Число вопросов: от 3 до 15")
    try: qs = await generate_questions(topic, n)
    except AIUnavailableError as e: raise ApiError(503, "AI_UNAVAILABLE", f"ИИ недоступен: {e}")
    return {"topic": topic, "questions": qs}

def open_round(s):
    if s["state"] == "pre_open": return "pre"
    if s["state"] == "post_open": return "post"
    raise ApiError(409, "SESSION_CLOSED", "Сессия завершена")

@app.get("/api/public/{code}")
async def public(code: str):
    with db() as c:
        s = c.execute("SELECT * FROM sessions WHERE code=?", (code.upper(),)).fetchone()
        if not s: raise ApiError(404, "SESSION_NOT_FOUND", "Сессия не найдена")
        r = open_round(s)
        qs = c.execute("SELECT * FROM questions WHERE sid=? AND round=? ORDER BY n", (s["id"], r)).fetchall()
    return {"code": s["code"], "topic": s["topic"], "round": r, "state": s["state"],
            "questions": [{"question_id": q["qid"], "concept_id": q["concept_id"], "text": q["text"], "options": json.loads(q["options"])} for q in qs]}

@app.post("/api/public/{code}/submit")
async def submit(code: str, body: dict):
    with db() as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            s = c.execute("SELECT * FROM sessions WHERE code=?", (code.upper(),)).fetchone()
            if not s: raise ApiError(404, "SESSION_NOT_FOUND", "Сессия не найдена")
            r = open_round(s)
            if body.get("round") != r: raise ApiError(409, "ROUND_CLOSED", "Раунд завершён — обновите страницу")
            qs = {q["qid"]: q for q in c.execute("SELECT * FROM questions WHERE sid=? AND round=?", (s["id"], r))}
            ans = body.get("answers")
            bad = ApiError(422, "INVALID_ANSWERS", "Некорректные ответы")
            if not isinstance(ans, list) or len(ans) != len(qs): raise bad
            seen = {}
            for a in ans:
                qid, i = a.get("question_id") if isinstance(a, dict) else None, a.get("selected_index") if isinstance(a, dict) else None
                if qid not in qs or qid in seen or not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(json.loads(qs[qid]["options"])): raise bad
                seen[qid] = i
            for qid, i in seen.items(): c.execute("UPDATE option_counts SET count=count+1 WHERE sid=? AND qid=? AND idx=?", (s["id"], qid, i))
            c.execute("UPDATE round_counts SET submissions=submissions+1 WHERE sid=? AND round=?", (s["id"], r))
            n = c.execute("SELECT submissions FROM round_counts WHERE sid=? AND round=?", (s["id"], r)).fetchone()[0]
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK"); raise
    return {"accepted": True, "round": r, "submissions": n}

def round_stats(c, sid, r):
    rc = c.execute("SELECT submissions FROM round_counts WHERE sid=? AND round=?", (sid, r)).fetchone()
    if not rc: return None
    subs, qs, conc = rc[0], [], {}
    for q in c.execute("SELECT * FROM questions WHERE sid=? AND round=? ORDER BY n", (sid, r)).fetchall():
        opts = json.loads(q["options"])
        counts = [c.execute("SELECT count FROM option_counts WHERE sid=? AND qid=? AND idx=?", (sid, q["qid"], i)).fetchone()[0] for i in range(len(opts))]
        cc = counts[q["correct_index"]]
        qs.append({"question_id": q["qid"], "concept_id": q["concept_id"], "text": q["text"], "options": opts, "correct_index": q["correct_index"],
                   "counts": counts, "correct_count": cc, "correct_percent": round(cc / subs * 100, 1) if subs else None})
        d = conc.setdefault(q["concept_id"], [0, 0]); d[0] += cc; d[1] += subs
    tot_c, tot_a = sum(d[0] for d in conc.values()), sum(d[1] for d in conc.values())
    return {"submissions": subs, "correct_percent": round(tot_c / tot_a * 100, 1) if tot_a else None, "questions": qs,
            "concepts": [{"concept_id": k, "correct_count": v[0], "total_answers": v[1], "correct_percent": round(v[0] / v[1] * 100, 1) if v[1] else None} for k, v in conc.items()]}

def full_stats(c, s):
    return {"session_id": s["id"], "topic": s["topic"], "state": s["state"],
            "rounds": {"pre": round_stats(c, s["id"], "pre"), "post": round_stats(c, s["id"], "post")}}

@app.get("/api/admin/sessions/{sid}/stats")
async def stats(sid: str, x_teacher_key: str | None = Header(None)):
    with db() as c: return full_stats(c, auth(c, sid, x_teacher_key))

@app.post("/api/admin/sessions/{sid}/analyze")
async def analyze(sid: str, x_teacher_key: str | None = Header(None)):
    with db() as c:
        s = auth(c, sid, x_teacher_key); st = full_stats(c, s)
        if s["state"] != "pre_open": raise ApiError(409, "INVALID_STATE", "Анализ доступен только до запуска post")
        p = c.execute("SELECT status FROM proposals WHERE sid=?", (sid,)).fetchone()
        if p and p[0] == "approved": raise ApiError(409, "INVALID_STATE", "Предложение уже утверждено")
    try: res = await analyze_aggregates(st)
    except AIUnavailableError as e: raise ApiError(503, "AI_UNAVAILABLE", f"ИИ недоступен: {e}")
    except ValueError: raise ApiError(503, "AI_UNAVAILABLE", "Агрегаты несогласованы")
    if res["status"] == "pending":
        with db() as c: c.execute("INSERT INTO proposals VALUES(?,?,?) ON CONFLICT(sid) DO UPDATE SET status=excluded.status, body=excluded.body",
                                  (sid, "pending", json.dumps(res["proposal"], ensure_ascii=False)))
    return res

def get_prop(c, sid):
    p = c.execute("SELECT * FROM proposals WHERE sid=?", (sid,)).fetchone()
    if not p: raise ApiError(404, "PROPOSAL_NOT_FOUND", "Предложение не найдено")
    return p

@app.get("/api/admin/sessions/{sid}/proposal")
async def get_proposal(sid: str, x_teacher_key: str | None = Header(None)):
    with db() as c:
        auth(c, sid, x_teacher_key); p = get_prop(c, sid)
        return {"proposal": {**json.loads(p["body"]), "status": p["status"]}}

@app.put("/api/admin/sessions/{sid}/proposal")
async def put_proposal(sid: str, body: dict, x_teacher_key: str | None = Header(None)):
    with db() as c:
        s = auth(c, sid, x_teacher_key); p = get_prop(c, sid); act = body.get("action")
        if s["state"] != "pre_open": raise ApiError(409, "INVALID_STATE", "Редактирование закрыто")
        cur = json.loads(p["body"])
        if act == "save":
            if p["status"] != "pending": raise ApiError(409, "INVALID_STATE", "Карточка не в статусе pending")
            try: new = Proposal(**{**body.get("proposal", {}), "status": "pending"}).model_dump()
            except (ValueError, TypeError): raise ApiError(422, "INVALID_PROPOSAL", "Карточка не прошла проверку")
            c.execute("UPDATE proposals SET body=? WHERE sid=?", (json.dumps(new, ensure_ascii=False), sid))
            return {"status": "pending", "proposal": new}
        if act == "approve":
            if p["status"] != "pending": raise ApiError(409, "INVALID_STATE", "Утвердить можно только pending")
            c.execute("BEGIN IMMEDIATE")
            for n, q in enumerate(cur["new_questions"], 1):
                add_question(c, sid, f"post_q{n}", "post", q["concept_id"], q["text"], q["options"], q["correct_index"], n)
            c.execute("UPDATE proposals SET status='approved' WHERE sid=?", (sid,)); c.execute("COMMIT")
            return {"status": "approved", "proposal": {**cur, "status": "approved"}}
        if act == "reject":
            if p["status"] != "pending": raise ApiError(409, "INVALID_STATE", "Отклонить можно только pending")
            c.execute("UPDATE proposals SET status='rejected' WHERE sid=?", (sid,))
            return {"status": "rejected", "proposal": {**cur, "status": "rejected"}}
    raise ApiError(422, "INVALID_ACTION", "Неизвестное действие")

@app.post("/api/admin/sessions/{sid}/activate-post")
async def activate(sid: str, x_teacher_key: str | None = Header(None)):
    with db() as c:
        s = auth(c, sid, x_teacher_key); p = c.execute("SELECT status FROM proposals WHERE sid=?", (sid,)).fetchone()
        n = c.execute("SELECT COUNT(*) FROM questions WHERE sid=? AND round='post'", (sid,)).fetchone()[0]
        if s["state"] != "pre_open" or not p or p[0] != "approved" or n < 2: raise ApiError(409, "INVALID_STATE", "Нужно утвердить предложение до запуска post")
        c.execute("BEGIN IMMEDIATE")
        c.execute("UPDATE sessions SET state='post_open' WHERE id=?", (sid,))
        c.execute("INSERT OR IGNORE INTO round_counts(sid,round) VALUES(?,'post')", (sid,)); c.execute("COMMIT")
    return {"state": "post_open", "round": "post", "questions_count": n}

@app.get("/api/admin/sessions/{sid}/comparison")
async def comparison(sid: str, x_teacher_key: str | None = Header(None)):
    with db() as c:
        s = auth(c, sid, x_teacher_key); pre, post = round_stats(c, sid, "pre"), round_stats(c, sid, "post")
    if not pre or not post or pre["submissions"] < 1 or post["submissions"] < 1: raise ApiError(409, "POST_NOT_READY", "Нет ответов post-раунда")
    return {"pre": {"submissions": pre["submissions"], "correct_percent": pre["correct_percent"]},
            "post": {"submissions": post["submissions"], "correct_percent": post["correct_percent"]},
            "delta_percentage_points": round(post["correct_percent"] - pre["correct_percent"], 1),
            "note": "Сравниваются агрегированные результаты разных наборов вопросов одной темы; индивидуальный прогресс и причинность не измеряются."}

# Если фронтенд собран (npm run build) — отдаём его с того же адреса: один порт, один туннель.
DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}

    @app.get("/{path:path}")
    async def spa(path: str):
        f = (DIST / path).resolve()
        ok = path and f.is_file() and f.is_relative_to(DIST.resolve())
        return FileResponse(f if ok else DIST / "index.html", headers=NO_CACHE)
