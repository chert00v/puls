# Пульс класса

Анонимный pre-тест → ИИ-гипотеза о типичной ошибке → учитель правит и утверждает → post-тест по той же ссылке → результат класса в п.п.
Хранятся только агрегированные счётчики. «Отправки» ≠ уникальные ученики.

## Запуск (Windows PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
$env:LLM_BASE_URL = "https://api.openai.com/v1"
$env:LLM_API_KEY  = "ключ"
$env:LLM_MODEL    = "gpt-4o-mini"
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Второе окно (режим разработки):
```powershell
cd frontend
npm install
npm run dev
```
Открыть http://localhost:5173

## Для показа с телефонов (один адрес, один туннель)
```powershell
cd frontend
npm install
npm run build
cd ..
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Теперь сайт целиком на http://<IP>:8000 (и API, и интерфейс). Для HTTPS: `cloudflared tunnel --url http://localhost:8000` или `ngrok http 8000`, откройте выданный адрес **на ноутбуке** — QR будет вести на него же.

## Тесты backend
```powershell
pip install -r backend/requirements-dev.txt
python -m pytest backend/tests -q
```

## Синтетическое демо 35% → 80%
См. `scripts/seed_demo.py` (3 шага в docstring). Сессия помечается баннером «СИНТЕТИЧЕСКИЕ ОТВЕТЫ».

## Если ИИ недоступен
Анализ вернёт ошибку 503, подменной «аналитики» нет. Для показа: используйте синтетическую сессию и честно скажите жюри, что ИИ-шаг не работал.
