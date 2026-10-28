import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { fetchPublicQuiz, submitAnswers } from '../api.js'

export default function StudentQuiz({ code: codeProp }) {
  const params = useParams()
  const code = codeProp || params.code
  const [quiz, setQuiz] = useState(null)
  const [sel, setSel] = useState({})
  const [phase, setPhase] = useState('loading') // loading | quiz | done | error
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setPhase('loading'); setMsg('')
    try {
      const q = await fetchPublicQuiz(code)
      setQuiz(q); setSel({})
      setPhase(sessionStorage.getItem(`submitted:${code}:${q.round}`) ? 'done' : 'quiz')
    } catch (e) {
      setMsg(e.status === 404 ? 'Сессия не найдена' : e.status === 409 ? 'Урок завершён' : 'Не удалось загрузить тест')
      setPhase('error')
    }
  }, [code])

  useEffect(() => { load() }, [load])

  async function send() {
    if (busy) return
    setBusy(true); setMsg('')
    try {
      await submitAnswers(code, { round: quiz.round, answers: quiz.questions.map((q) => ({ question_id: q.question_id, selected_index: sel[q.question_id] })) })
      sessionStorage.setItem(`submitted:${code}:${quiz.round}`, '1')
      setPhase('done')
    } catch (e) {
      setMsg(e.status === 409 ? 'Раунд завершён — обновите страницу' : e.status === 404 ? 'Сессия не найдена' : 'Не удалось отправить, попробуйте снова')
    }
    setBusy(false)
  }

  if (phase === 'loading') return <p className="p-6">Загрузка…</p>
  if (phase === 'error') return (
    <main className="p-6"><p className="text-red-600">{msg}</p>
      <button className="mt-3 rounded bg-slate-800 px-4 py-2 text-white" onClick={load}>Обновить</button></main>
  )
  if (phase === 'done') return (
    <main className="mx-auto max-w-md p-6 text-center">
      <h1 className="mt-10 text-2xl font-bold">Спасибо! Ответы учтены</h1>
      <p className="mt-2 text-slate-600">Когда преподаватель запустит второй этап, откройте эту же ссылку.</p>
      <button className="mt-6 min-h-[44px] rounded-xl border px-4" onClick={load}>Проверить, открыт ли следующий этап</button>
    </main>
  )

  const done = quiz.questions.filter((q) => sel[q.question_id] !== undefined).length
  const all = done === quiz.questions.length
  return (
    <main className="mx-auto max-w-md p-4">
      <p className="text-sm text-slate-500">{quiz.topic} · {quiz.round === 'pre' ? 'Проверка знаний' : 'Повторная проверка'} · {done} из {quiz.questions.length}</p>
      {quiz.questions.map((q, n) => (
        <fieldset key={q.question_id} className="mt-4 rounded-xl bg-white p-4 shadow">
          <legend className="font-semibold">{n + 1}. {q.text}</legend>
          {q.options.map((o, i) => (
            <label key={i} className={`mt-2 flex min-h-[44px] cursor-pointer items-center rounded-lg border px-3 font-mono ${sel[q.question_id] === i ? 'border-indigo-600 bg-indigo-50' : ''}`}>
              <input type="radio" className="mr-3" name={q.question_id} checked={sel[q.question_id] === i}
                onChange={() => setSel({ ...sel, [q.question_id]: i })} />
              {o}
            </label>
          ))}
        </fieldset>
      ))}
      {msg && <p className="mt-3 text-red-600">{msg}</p>}
      <button disabled={!all || busy} onClick={send}
        className="mt-4 min-h-[48px] w-full rounded-xl bg-indigo-600 text-lg font-semibold text-white disabled:opacity-40">
        {busy ? 'Отправляем…' : 'Отправить'}
      </button>
    </main>
  )
}
