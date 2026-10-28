import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getKey, getStats } from '../api.js'
import SessionQR from '../components/SessionQR.jsx'

function Bar({ label, n, total, ok }) {
  const pct = total ? Math.round((n / total) * 100) : 0
  return (
    <div className="mb-1 flex items-center gap-2 text-sm">
      <span className="w-40 shrink-0 truncate font-mono">{label}</span>
      <div className="h-4 flex-1 rounded bg-slate-200">
        <div className={`h-4 rounded ${ok ? 'bg-green-500' : 'bg-rose-400'}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-16 text-right">{n} ({pct}%)</span>
    </div>
  )
}

export default function TeacherDashboard() {
  const { id } = useParams()
  const [stats, setStats] = useState(null)
  const [err, setErr] = useState('')
  const [copied, setCopied] = useState(false)
  const code = sessionStorage.getItem(`code:${id}`)
  const hasKey = !!getKey(id)
  const alive = useRef(true)

  useEffect(() => {
    if (!hasKey) return
    alive.current = true
    let timer
    async function tick() {
      try { const s = await getStats(id); if (alive.current) { setStats(s); setErr('') } }
      catch (e) { if (alive.current) setErr(e.message) }
      if (alive.current) timer = setTimeout(tick, 3000)
    }
    tick()
    return () => { alive.current = false; clearTimeout(timer) }
  }, [id, hasKey])

  if (!hasKey) return (
    <main className="p-6"><p>Ключ преподавателя не найден в этой вкладке. <Link className="text-indigo-600 underline" to="/">Создайте новую сессию</Link>.</p></main>
  )

  const link = code ? `${window.location.origin}/join/${code}` : ''
  const round = stats?.state === 'post_open' ? 'post' : 'pre'
  const r = stats?.rounds?.[round]

  return (
    <main className="mx-auto max-w-4xl p-4 sm:p-6">
      {sessionStorage.getItem(`synthetic:${id}`) && <p className="mb-2 rounded bg-amber-100 p-2 font-bold text-amber-900">СИНТЕТИЧЕСКИЕ ОТВЕТЫ — тестовые данные, не реальные ученики</p>}
      <h1 className="text-2xl font-bold">Панель преподавателя · {stats?.topic || 'Python: range()'}</h1>
      <div className="mt-4 grid gap-4 sm:grid-cols-[auto,1fr]">
        <div>{code && <SessionQR code={code} baseUrl={window.location.origin} />}</div>
        <div>
          <p className="text-sm text-slate-500">Ссылка для учеников</p>
          <p className="break-all font-mono text-lg">{link}</p>
          <p className="text-sm text-slate-500">Код: <b>{code}</b></p>
          <button className="mt-2 rounded bg-slate-800 px-3 py-1 text-white"
            onClick={() => { navigator.clipboard?.writeText(link); setCopied(true); setTimeout(() => setCopied(false), 1500) }}>
            {copied ? 'Скопировано' : 'Копировать ссылку'}
          </button>
          {window.location.hostname === 'localhost' && (
            <p className="mt-2 text-sm text-amber-700">Вы на localhost: телефон по этой ссылке не откроется. Используйте HTTPS-туннель или IP в сети.</p>
          )}
        </div>
      </div>

      <Link to={`/teacher/${id}/review`} className="mt-4 inline-block rounded-xl bg-indigo-600 px-4 py-2 font-semibold text-white">Разбор ответов и повторная проверка →</Link>
      <Link to={`/teacher/${id}/results`} className="ml-2 mt-4 inline-block rounded-xl border border-indigo-600 px-4 py-2 font-semibold text-indigo-700">Результаты до/после</Link>
      {err && <p className="mt-4 text-red-600">{err}</p>}
      {!stats && !err && <p className="mt-6 text-slate-500">Загрузка…</p>}

      {r && (
        <section className="mt-6">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-white p-4 shadow"><div className="text-sm text-slate-500">Отправок ({round === 'pre' ? 'до' : 'после'})</div><div className="text-3xl font-bold">{r.submissions}</div></div>
            <div className="rounded-xl bg-white p-4 shadow"><div className="text-sm text-slate-500">Верных ответов</div><div className="text-3xl font-bold">{r.correct_percent ?? '—'}{r.correct_percent != null && '%'}</div></div>
          </div>
          <p className="mt-1 text-xs text-slate-500">Это отправки, а не уникальные ученики: без аккаунтов повторы исключить нельзя.</p>
          {r.questions.map((q) => (
            <div key={q.question_id} className="mt-4 rounded-xl bg-white p-4 shadow">
              <p className="mb-2 font-semibold">{q.text}</p>
              {q.options.map((o, i) => <Bar key={i} label={o} n={q.counts[i]} total={r.submissions} ok={i === q.correct_index} />)}
            </div>
          ))}
        </section>
      )}
    </main>
  )
}
