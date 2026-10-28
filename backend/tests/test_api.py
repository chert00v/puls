import pytest
from fastapi.testclient import TestClient
from backend import main

NEWQ = [{"text": "Что выведет list(range(4))?", "options": ["[0, 1, 2, 3]", "[1, 2, 3, 4]", "[0, 1, 2, 3, 4]"], "correct_index": 0, "concept_id": "python_range"},
        {"text": "Что выведет list(range(3, 6))?", "options": ["[3, 4, 5]", "[3, 4, 5, 6]", "[1, 2, 3]"], "correct_index": 0, "concept_id": "python_range"}]

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB", str(tmp_path / "t.db")); main.init_db()
    async def fake(payload):
        if payload["rounds"]["pre"]["submissions"] < 5: return {"status": "insufficient_data", "reason": "x", "min_submissions": 5}
        return {"status": "pending", "proposal": {"status": "pending", "concept_id": "python_range", "concept": "Python range()", "misconception": "range(3) начинается с 1",
                "evidence_question_ids": ["pre_q1"], "evidence": "13 из 20 выбрали [1, 2, 3]", "explanation": "range(3) начинает с нуля", "example": "list(range(3))",
                "duration_minutes": 2, "recommendation": "repeat", "new_questions": NEWQ}}
    monkeypatch.setattr(main, "analyze_aggregates", fake)
    return TestClient(main.app)

def new(c):
    s = c.post("/api/sessions", json={"topic_id": "python_range"}).json(); return s, {"X-Teacher-Key": s["teacher_key"]}

def send(c, code, rnd, ans): return c.post(f"/api/public/{code}/submit", json={"round": rnd, "answers": [{"question_id": q, "selected_index": i} for q, i in ans]})

def test_create_and_public(client):
    r = client.post("/api/sessions", json={"topic_id": "x"}); assert r.status_code == 422
    s, _ = new(client); assert len(s["code"]) == 6
    pub = client.get(f"/api/public/{s['code']}").json()
    assert "correct_index" not in str(pub) and len(pub["questions"]) == 3
    assert client.get("/api/public/ZZZZZZ").status_code == 404

def test_auth(client):
    s, _ = new(client)
    assert client.get(f"/api/admin/sessions/{s['session_id']}/stats").status_code == 401
    assert client.get(f"/api/admin/sessions/{s['session_id']}/stats", headers={"X-Teacher-Key": "bad"}).status_code == 401

def test_invalid_submit_keeps_counters(client):
    s, h = new(client); c = s["code"]
    assert send(client, c, "pre", [("pre_q1", 0), ("pre_q1", 0), ("pre_q3", 0)]).status_code == 422
    assert send(client, c, "pre", [("pre_q1", 0), ("pre_q2", 0)]).status_code == 422
    assert send(client, c, "pre", [("pre_q1", 9), ("pre_q2", 0), ("pre_q3", 0)]).status_code == 422
    assert send(client, c, "post", [("pre_q1", 0), ("pre_q2", 0), ("pre_q3", 0)]).status_code == 409
    assert client.get(f"/api/admin/sessions/{s['session_id']}/stats", headers=h).json()["rounds"]["pre"]["submissions"] == 0

def test_full_flow(client):
    s, h = new(client); c, sid = s["code"], s["session_id"]
    assert client.post(f"/api/admin/sessions/{sid}/analyze", headers=h, json={}).json()["status"] == "insufficient_data"
    for i in range(20):
        assert send(client, c, "pre", [("pre_q1", 0 if i < 7 else 1), ("pre_q2", 0 if i < 8 else 1), ("pre_q3", 0 if i < 6 else 2)]).status_code == 200
    st = client.get(f"/api/admin/sessions/{sid}/stats", headers=h).json()["rounds"]
    assert st["pre"]["submissions"] == 20 and st["pre"]["questions"][0]["counts"] == [7, 13, 0] and st["pre"]["correct_percent"] == 35.0 and st["post"] is None
    assert client.post(f"/api/admin/sessions/{sid}/activate-post", headers=h, json={}).status_code == 409
    assert client.put(f"/api/admin/sessions/{sid}/proposal", headers=h, json={"action": "approve"}).status_code == 404
    assert client.post(f"/api/admin/sessions/{sid}/analyze", headers=h, json={}).json()["status"] == "pending"
    prop = client.get(f"/api/admin/sessions/{sid}/proposal", headers=h).json()["proposal"]
    prop["explanation"] = "Отредактировано учителем"
    assert client.put(f"/api/admin/sessions/{sid}/proposal", headers=h, json={"action": "save", "proposal": prop}).status_code == 200
    assert client.put(f"/api/admin/sessions/{sid}/proposal", headers=h, json={"action": "approve"}).json()["status"] == "approved"
    assert client.get(f"/api/admin/sessions/{sid}/comparison", headers=h).status_code == 409
    assert client.post(f"/api/admin/sessions/{sid}/activate-post", headers=h, json={}).json()["questions_count"] == 2
    assert client.post(f"/api/admin/sessions/{sid}/activate-post", headers=h, json={}).status_code == 409
    assert send(client, c, "pre", [("pre_q1", 0), ("pre_q2", 0), ("pre_q3", 0)]).status_code == 409
    assert [q["question_id"] for q in client.get(f"/api/public/{c}").json()["questions"]] == ["post_q1", "post_q2"]
    for i in range(20): assert send(client, c, "post", [("post_q1", 0 if i < 17 else 1), ("post_q2", 0 if i < 15 else 1)]).status_code == 200
    cmp = client.get(f"/api/admin/sessions/{sid}/comparison", headers=h).json()
    assert cmp["post"]["correct_percent"] == 80.0 and cmp["delta_percentage_points"] == 45.0


def test_custom_topic(client):
    qs = [{"text": f"Вопрос {i}?", "options": ["а", "б", "в"], "correct_index": i % 3} for i in range(3)]
    r = client.post("/api/sessions", json={"topic": "Дроби", "questions": qs}); assert r.status_code == 201 and r.json()["topic"] == "Дроби"
    pub = client.get(f"/api/public/{r.json()['code']}").json(); assert len(pub["questions"]) == 3 and "correct_index" not in str(pub)
    assert client.post("/api/sessions", json={"topic": "Дроби", "questions": qs[:2]}).status_code == 422
    bad = [{**qs[0], "correct_index": 9}] + qs[1:]; assert client.post("/api/sessions", json={"topic": "Дроби", "questions": bad}).status_code == 422


def test_many_questions_and_dynamic_post(client):
    qs = [{"text": f"Вопрос {i}?", "options": ["а", "б", "в"], "correct_index": i % 3} for i in range(12)]
    r = client.post("/api/sessions", json={"topic": "Дроби", "questions": qs}); assert r.status_code == 201
    assert len(client.get(f"/api/public/{r.json()['code']}").json()["questions"]) == 12
    assert client.post("/api/sessions", json={"topic": "Дроби", "questions": qs + qs}).status_code == 422
