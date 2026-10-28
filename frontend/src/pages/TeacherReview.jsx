import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { activatePost, analyze, getKey, getProposal, getStats, putProposal } from '../api.js'

const inp = 'w-full rounded border border-slate-300 px-2 py-1'

export default function TeacherReview() {
  const { id } = useParams()
  const nav = useNavigate()
  const [subs, setSubs] = useState(null)
  const [state, setState] = useState('')
  const [p, setP] = useState(null) // текущая карточка (черновик в форме)
  const [busy, setBusy] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(async () => {
    try {
      const s = await getStats(id)
      setSubs(s.rounds.pre?.submissions ?? 0); setState(s.state)
      try { setP((await getProposal(id)).proposal) } catch (e) { if (e.status !== 404) throw e }
    } catch (e) { setErr(e.message) }
  }, [id])
  useEffect(() => { if (getKey(id)) load() }, [id, load])

  if (!getKey(id)) return <main className="p-6">Ключ не найден. <Link className="text-indigo-600 underline" to="/">Создайте новую сессию</Link>.</main>

  async function run(name, fn) {
    if (busy) return
    setBusy(name); setErr(''); setMsg('')
    try { await fn() } catch (e) { setErr(e.code === 'AI_UNAVAILABLE' ? `ИИ недоступен: ${e.message}` : e.message) }
    setBusy('')
  }

  const generate = () => run('gen', async () => {
    const r = await analyze(id)
    if (r.status === 'insufficient_data') setMsg(r.reason)
    else setP(r.proposal)
  })
  const save = () => run('save', async () => { setP((await putProposal(id, { action: 'save', proposal: p })).proposal); setMsg('Изменения сохранены') })
  const approve = () => run('approve', async () => {
    await putProposal(id, { action: 'save', proposal: p })           // сначала сохраняем правки
    setP((await putProposal(id, { action: 'approve' })).proposal); setMsg('Утверждено. Можно запускать повторную проверку.')
  })
  const reject = () => run('reject', async () => { setP((await putProposal(id, { action: 'reject' })).proposal) })
  const start = () => run('start', async () => { await activatePost(id); nav(`/teacher/${id}`) })

  const set = (k, v) => setP({ ...p, [k]: v })
  const setQ = (i, patch) => setP({ ...p, new_questions: p.new_questions.map((q, j) => (j === i ? { ...q, ...patch } : q)) })
  const setOpt = (i, k, v) => setQ(i, { options: p.new_questions[i].options.map((o, j) => (j === k ? v : o)) })

  const locked = p?.status !== 'pending' || state !== 'pre_open'
  const canGen = subs >= 5 && state === 'pre_open' && p?.status !== 'approved'

  return (
    <main className="mx-auto max-w-3xl p-4 sm:p-6">
      <Link className="text-sm text-indigo-600 underline" to={`/teacher/${id}`}>← К панели</Link>
      <h1 className="mt-2 text-2xl font-bold">Разбор и повторная проверка</h1>
      <p className="mt-1 text-sm text-slate-500">ИИ видит только суммарные счётчики по вариантам, не ответы отдельных учеников. Это гипотеза: решение за вами.</p>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button onClick={generate} disabled={!canGen || !!busy} className="rounded-xl bg-indigo-600 px-4 py-2 font-semibold text-white disabled:opacity-40">
          {busy === 'gen' ? 'ИИ анализирует…' : p ? 'Сгенерировать заново' : 'Проанализировать ответы'}
        </button>
        {subs !== null && subs < 5 && <span className="text-sm text-amber-700">Нужно минимум 5 отправок (сейчас {subs}).</span>}
      </div>
      {err && <p className="mt-3 rounded bg-red-50 p-2 text-red-700">{err}</p>}
      {msg && <p className="mt-3 rounded bg-green-50 p-2 text-green-800">{msg}</p>}

      {p && (
        <section className="mt-5 space-y-4 rounded-xl bg-white p-4 shadow">
          <div className="text-sm">Статус: <b>{{ pending: 'ждёт проверки', approved: 'утверждено', rejected: 'отклонено' }[p.status]}</b></div>
          <div className="rounded bg-slate-50 p-3 text-sm">
            <div className="text-slate-500">На чём основан вывод ({p.evidence_question_ids.join(', ')})</div>
            <div className="font-medium">{p.evidence}</div>
          </div>
          <label className="block"><span className="text-sm text-slate-500">Возможное заблуждение (гипотеза)</span>
            <textarea disabled={locked} rows={2} className={inp} value={p.misconception} onChange={(e) => set('misconception', e.target.value)} /></label>
          <label className="block"><span className="text-sm text-slate-500">Объяснение (~{p.duration_minutes} мин)</span>
            <textarea disabled={locked} rows={3} className={inp} value={p.explanation} onChange={(e) => set('explanation', e.target.value)} /></label>
          <label className="block"><span className="text-sm text-slate-500">Пример</span>
            <input disabled={locked} className={`${inp} font-mono`} value={p.example} onChange={(e) => set('example', e.target.value)} /></label>

          <h2 className="font-semibold">Новые вопросы для повторной проверки ({p.new_questions.length})</h2>
          <p className="text-xs text-slate-500">Отметьте верный вариант и проверьте его сами: ИИ может ошибиться.</p>
          {p.new_questions.map((q, i) => (
            <div key={i} className="rounded-lg border p-3">
              <input disabled={locked} className={`${inp} mb-2 font-semibold`} value={q.text} onChange={(e) => setQ(i, { text: e.target.value })} />
              {q.options.map((o, k) => (
                <div key={k} className="mb-1 flex items-center gap-2">
                  <input type="radio" disabled={locked} name={`ok${i}`} checked={q.correct_index === k} onChange={() => setQ(i, { correct_index: k })} />
                  <input disabled={locked} className={`${inp} font-mono`} value={o} onChange={(e) => setOpt(i, k, e.target.value)} />
                </div>
              ))}
            </div>
          ))}

          <div className="flex flex-wrap gap-2">
            {p.status === 'pending' && state === 'pre_open' && (<>
              <button onClick={save} disabled={!!busy} className="rounded border px-4 py-2 disabled:opacity-40">{busy === 'save' ? 'Сохраняем…' : 'Сохранить изменения'}</button>
              <button onClick={approve} disabled={!!busy} className="rounded bg-green-600 px-4 py-2 font-semibold text-white disabled:opacity-40">{busy === 'approve' ? 'Утверждаем…' : 'Одобрить'}</button>
              <button onClick={reject} disabled={!!busy} className="rounded border border-red-300 px-4 py-2 text-red-700 disabled:opacity-40">Отклонить</button>
            </>)}
            {p.status === 'approved' && state === 'pre_open' && (
              <button onClick={start} disabled={!!busy} className="rounded-xl bg-indigo-600 px-5 py-3 text-lg font-semibold text-white disabled:opacity-40">
                {busy === 'start' ? 'Запускаем…' : 'Начать повторную проверку'}</button>
            )}
            {state === 'post_open' && <span className="text-green-700">Повторная проверка идёт по той же ссылке.</span>}
          </div>
        </section>
      )}
    </main>
  )
}
