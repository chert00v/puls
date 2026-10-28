// dev: бэкенд на :8000 того же хоста; после npm run build бэкенд отдаёт сайт сам — тот же origin
const BASE = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? `${window.location.protocol}//${window.location.hostname}:8000` : '')

async function req(path, { method = 'GET', body, key } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (key) headers['X-Teacher-Key'] = key
  let res
  try {
    res = await fetch(BASE + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  } catch {
    throw { status: 0, code: 'NETWORK', message: 'Нет связи с сервером' }
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw { status: res.status, code: data?.error?.code || 'ERROR', message: data?.error?.message || 'Ошибка' }
  return data
}

export const getKey = (id) => sessionStorage.getItem(`teacherKey:${id}`)

// публичные
export const createSession = (body = { topic_id: 'python_range' }) => req('/api/sessions', { method: 'POST', body })
export const generateQuestions = (topic, count) => req('/api/generate-questions', { method: 'POST', body: { topic, count } })
export const fetchPublicQuiz = (code) => req(`/api/public/${code}`)
export const submitAnswers = (code, payload) => req(`/api/public/${code}/submit`, { method: 'POST', body: payload })

// преподаватель
export const getStats = (id) => req(`/api/admin/sessions/${id}/stats`, { key: getKey(id) })
export const analyze = (id) => req(`/api/admin/sessions/${id}/analyze`, { method: 'POST', body: {}, key: getKey(id) })
export const getProposal = (id) => req(`/api/admin/sessions/${id}/proposal`, { key: getKey(id) })
export const putProposal = (id, body) => req(`/api/admin/sessions/${id}/proposal`, { method: 'PUT', body, key: getKey(id) })
export const activatePost = (id) => req(`/api/admin/sessions/${id}/activate-post`, { method: 'POST', body: {}, key: getKey(id) })
export const getComparison = (id) => req(`/api/admin/sessions/${id}/comparison`, { key: getKey(id) })
