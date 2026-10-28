import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import { getComparison, getKey } from '../api.js'

export default function TeacherResults() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [wait, setWait] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (!getKey(id)) return
    let alive = true, timer
    async function tick() {
      try { const d = await getComparison(id); if (alive) { setData(d); setWait(false); setErr('') } }
      catch (e) {
        if (!alive) return
        if (e.code === 'POST_NOT_READY') setWait(true); else setErr(e.message)
      }
      if (alive) timer = setTimeout(tick, 3000)
    }
    tick()
    return () => { alive = false; clearTimeout(timer) }
  }, [id])

  if (!getKey(id)) return <main className="p-6">Ключ не найден. <Link className="text-indigo-600 underline" to="/">Создайте новую сессию</Link>.</main>

  const chart = data && [{ name: 'До объяснения', v: data.pre.correct_percent }, { name: 'После', v: data.post.correct_percent }]
  const d = data?.delta_percentage_points
  return (
    <main className="mx-auto max-w-3xl p-4 sm:p-6">
      <Link className="text-sm text-indigo-600 underline" to={`/teacher/${id}`}>← К панели</Link>
      <h1 className="mt-2 text-2xl font-bold">Результаты класса: до и после</h1>
      {sessionStorage.getItem(`synthetic:${id}`) && <p className="mt-2 rounded bg-amber-100 p-2 font-bold text-amber-900">СИНТЕТИЧЕСКИЕ ОТВЕТЫ — тестовые данные</p>}
      {err && <p className="mt-3 text-red-600">{err}</p>}
      {wait && !data && <p className="mt-4 text-slate-600">Результаты появятся, когда будет хотя бы одна отправка второго этапа. Страница обновляется сама.</p>}
      {data && (<>
        <div className="mt-4 rounded-xl bg-white p-5 text-center shadow">
          <div className={`text-5xl font-bold ${d >= 0 ? 'text-green-600' : 'text-rose-600'}`}>{d > 0 ? '+' : ''}{d} п.п.</div>
          <div className="mt-1 text-slate-600">{data.pre.correct_percent}% → {data.post.correct_percent}% верных ответов</div>
          <div className="mt-1 text-xs text-slate-500">Отправок: до — {data.pre.submissions}, после — {data.post.submissions}</div>
        </div>
        <div className="mt-4 h-72 rounded-xl bg-white p-3 shadow">
          <ResponsiveContainer>
            <BarChart data={chart}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis domain={[0, 100]} unit="%" />
              <Bar dataKey="v" fill="#4f46e5" radius={[6, 6, 0, 0]} isAnimationActive={false}>
                <LabelList dataKey="v" position="top" formatter={(x) => `${x}%`} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-3 rounded bg-slate-100 p-3 text-sm text-slate-700">{data.note}</p>
      </>)}
    </main>
  )
}
