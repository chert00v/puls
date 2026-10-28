import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createSession, generateQuestions } from '../api.js'

const inp = 'w-full rounded border border-slate-300 px-2 py-1'

export default function Home() {
  const nav = useNavigate()
  const [topic, setTopic] = useState('')
  const [qs, setQs] = useState(null)
const [count, setCount] = useState('5')
const fixCount = () => {
  const n = Math.max(3, Math.min(15, parseInt(count, 10) || 3))
  setCount(String(n))
  return n
}
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')

  async function run(name, fn) {
    if (busy) return
    setBusy(name); setErr('')
    try { await fn() } catch (e) { setErr(e.message) }
    setBusy('')
  }
  const open = async (body) => {
   const gen = () => run('gen', async () => setQs((await generateQuestions(topic.trim(), fixCount())).questions))
    sessionStorage.setItem(`teacherKey:${s.session_id}`, s.teacher_key)
    sessionStorage.setItem(`code:${s.session_id}`, s.code)
    nav(`/teacher/${s.session_id}`)
  }
  const gen = () => run('gen', async () => setQs((await generateQuestions(topic.trim(), count)).questions))
  const start = () => run('start', () => open({ topic: topic.trim(), questions: qs }))
  const demo = () => run('demo', () => open({ topic_id: 'python_range' }))

  const addQ = () => setQs([...qs, { text: '', options: ['', '', ''], correct_index: 0 }])
  const delQ = (i) => setQs(qs.filter((_, j) => j !== i))
  const setQ = (i, patch) => setQs(qs.map((q, j) => (j === i ? { ...q, ...patch } : q)))
  const setOpt = (i, k, v) => setQ(i, { options: qs[i].options.map((o, j) => (j === k ? v : o)) })

  return (
    <main className="mx-auto max-w-2xl p-6">
      <h1 className="mt-10 text-center text-3xl font-bold">Пульс класса</h1>
      <p className="mt-3 text-center text-slate-600">Короткий анонимный тест → типичная ошибка → объяснение → повторная проверка.</p>
      <label className="mt-3 block text-sm text-slate-600">Сколько вопросов (3–15)
        <input type="text" inputMode="numeric" pattern="[0-9]*" maxLength={2}
          className="ml-2 w-20 rounded border border-slate-300 px-2 py-1" value={count}
          onChange={(e) => setCount(e.target.value.replace(/\D/g, ''))}
          onBlur={fixCount} />
      </label>
      <label className="mt-3 block text-sm text-slate-600">Сколько вопросов (3–15)
        <input type="number" min="3" max="15" className="ml-2 w-20 rounded border border-slate-300 px-2 py-1" value={count}
          onChange={(e) => setCount(Math.max(3, Math.min(15, Number(e.target.value) || 3)))} />
      </label>
      <button onClick={gen} disabled={topic.trim().length < 3 || !!busy}
        className="mt-3 rounded-xl bg-indigo-600 px-5 py-3 font-semibold text-white disabled:opacity-40">
        {busy === 'gen' ? 'ИИ составляет вопросы…' : qs ? 'Составить заново' : 'Составить вопросы с помощью ИИ'}
      </button>
      {err && <p className="mt-3 rounded bg-red-50 p-2 text-red-700">{err}</p>}

      {qs && (
        <section className="mt-5 space-y-3">
          <p className="rounded bg-amber-50 p-2 text-sm text-amber-900">Проверьте вопросы: ИИ может ошибиться. Точкой отмечен верный ответ, текст можно править.</p>
          {qs.map((q, i) => (
            <div key={i} className="rounded-xl bg-white p-3 shadow">
              <div className="mb-2 flex gap-2">
                <input className={`${inp} font-semibold`} placeholder={`Вопрос ${i + 1}`} value={q.text} onChange={(e) => setQ(i, { text: e.target.value })} />
                {qs.length > 3 && <button onClick={() => delQ(i)} className="rounded border px-2 text-red-600" title="Удалить вопрос">✕</button>}
              </div>
              {q.options.map((o, k) => (
                <div key={k} className="mb-1 flex items-center gap-2">
                  <input type="radio" name={`c${i}`} checked={q.correct_index === k} onChange={() => setQ(i, { correct_index: k })} />
                  <input className={inp} value={o} onChange={(e) => setOpt(i, k, e.target.value)} />
                </div>
              ))}
            </div>
          ))}
          {qs.length < 15 && <button onClick={addQ} className="rounded border border-dashed border-slate-400 px-4 py-2 text-slate-700">+ Добавить свой вопрос</button>}
          <button onClick={start} disabled={!!busy || qs.some((q) => !q.text.trim() || q.options.some((o) => !o.trim()))} className="w-full rounded-xl bg-green-600 py-3 text-lg font-semibold text-white disabled:opacity-40">
            {busy === 'start' ? 'Создаём…' : 'Начать урок'}
          </button>
        </section>
      )}

      <p className="mt-8 text-center text-sm text-slate-500">
        Нет ключа ИИ? <button onClick={demo} disabled={!!busy} className="text-indigo-600 underline">Запустить готовую демо-тему «Python range()»</button>
      </p>
    </main>
  )
}
