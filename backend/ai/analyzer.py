import json, os, random
from typing import Literal
import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

class AIUnavailableError(Exception): pass

class NewQ(BaseModel):
    text: str = Field(min_length=3, max_length=300)
    options: list[str]
    correct_index: int
    concept_id: str
    @field_validator("options")
    @classmethod
    def _o(cls, v):
        if not 3 <= len(v) <= 4 or len(set(v)) != len(v) or any(not o.strip() for o in v):
            raise ValueError("3-4 unique options")
        return v
    def model_post_init(self, _):
        if not 0 <= self.correct_index < len(self.options): raise ValueError("correct_index")

class Proposal(BaseModel):
    status: Literal["pending", "approved", "rejected"] = "pending"
    concept_id: str
    concept: str = Field(min_length=2)
    misconception: str = Field(min_length=5)
    evidence_question_ids: list[str] = Field(min_length=1)
    evidence: str = Field(min_length=5)
    explanation: str = Field(min_length=5)
    example: str = Field(min_length=2)
    duration_minutes: int = Field(ge=1, le=3)
    recommendation: Literal["repeat", "continue"]
    new_questions: list[NewQ] = Field(min_length=2, max_length=15)

SYSTEM = ("Ты помощник учителя. Тебе даны АГРЕГИРОВАННЫЕ ответы класса. Сформулируй осторожную гипотезу о типичном "
 "заблуждении (не утверждай, что ученики точно так думают), опираясь на реальные числа. Верни ТОЛЬКО JSON без markdown: "
 '{"concept_id","concept","misconception","evidence_question_ids":[...],"evidence":"числа и варианты","explanation",'
 '"example","duration_minutes":1-3,"recommendation":"repeat|continue","new_questions":[ровно post_questions_count объектов '
 '{"text","options":[3-4],"correct_index":0-based,"concept_id"}]}. Новые вопросы НЕ должны копировать исходные.')

def _summary(pre):
    out = []
    for q in pre["questions"]:
        c = q["counts"]; wrong = [(n, i) for i, n in enumerate(c) if i != q["correct_index"]]
        n, i = max(wrong) if wrong else (0, 0)
        out.append({"question_id": q["question_id"], "concept_id": q["concept_id"], "text": q["text"],
                    "options": q["options"], "correct_index": q["correct_index"], "counts": c,
                    "top_wrong_index": i, "top_wrong_share": round(n / pre["submissions"], 2)})
    return {"submissions": pre["submissions"], "post_questions_count": 2 if len(out) <= 3 else len(out), "questions": out}

async def _llm(summary, system=None):
    base, key, model = os.getenv("LLM_BASE_URL"), os.getenv("LLM_API_KEY"), os.getenv("LLM_MODEL")
    if not (base and key and model): raise AIUnavailableError("LLM не настроена")
    try:
        async with httpx.AsyncClient(timeout=40) as cl:
            r = await cl.post(base.rstrip("/") + "/chat/completions", headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "temperature": 0.3, "messages": [{"role": "system", "content": system or SYSTEM},
                      {"role": "user", "content": json.dumps(summary, ensure_ascii=False)}]})
            r.raise_for_status()
            t = r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise AIUnavailableError(str(type(e).__name__))
    return t.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

async def analyze_aggregates(payload: dict) -> dict:
    pre = payload["rounds"]["pre"]
    if pre["submissions"] < 5:
        return {"status": "insufficient_data", "reason": "Для вывода о типичной ошибке нужно минимум 5 отправок", "min_submissions": 5}
    for q in pre["questions"]:
        if len(q["counts"]) != len(q["options"]) or sum(q["counts"]) != pre["submissions"]:
            raise ValueError("inconsistent aggregates")
    summary = _summary(pre); ids = {q["question_id"] for q in pre["questions"]}
    concepts = {q["concept_id"] for q in pre["questions"]}; texts = {q["text"].strip() for q in pre["questions"]}
    for _ in range(2):
        try:
            p = Proposal(**{**json.loads(await _llm(summary)), "status": "pending"})
            if len(p.new_questions) != summary["post_questions_count"]: continue
            if len(concepts) == 1:
                only = next(iter(concepts)); p.concept_id = only
                for q in p.new_questions: q.concept_id = only
            if not set(p.evidence_question_ids) <= ids or p.concept_id not in concepts: continue
            if any(q.concept_id not in concepts or q.text.strip() in texts for q in p.new_questions): continue
            return {"status": "pending", "proposal": p.model_dump()}
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
            continue
    raise AIUnavailableError("LLM вернула невалидный ответ")


GEN_SYSTEM = ("Ты методист. По теме от учителя составь РОВНО {n} коротких вопроса с выбором ответа (по 3 варианта), "
 "проверяющих понимание темы; вопросы не должны повторять друг друга. Один вариант строго верный, два других отражают типичные ошибки. "
 'Без двусмысленностей, по-русски. Верни ТОЛЬКО JSON без markdown: {{"questions":[{{"text","options":[3 строки],"correct_index":0-based}}]}}')

async def generate_questions(topic: str, n: int = 5) -> list[dict]:
    for _ in range(2):
        try:
            raw = json.loads(await _llm({"topic": topic, "count": n}, GEN_SYSTEM.format(n=n)))["questions"]
            out = []
            for q in raw:
                v = NewQ(text=q["text"], options=q["options"], correct_index=q["correct_index"], concept_id="custom_topic")
                right = v.options[v.correct_index]; opts = v.options[:]; random.shuffle(opts)  # верный не всегда первый
                out.append({"text": v.text, "options": opts, "correct_index": opts.index(right)})
            if len(out) == n and len({q["text"] for q in out}) == n: return out
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError, KeyError):
            continue
    raise AIUnavailableError("LLM вернула невалидные вопросы")
