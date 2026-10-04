'use client'

import { useEffect, useState } from 'react'

import { getPortal, saveAnswers, type Portal, type PortalQuestion } from '@/lib/api'

export default function VendorPortal({ params }: { params: { token: string } }) {
  const [portal, setPortal] = useState<Portal | null>(null)
  const [answers, setAnswers] = useState<Record<string, { value: string; note: string }>>({})
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getPortal(params.token)
      .then((data) => {
        setPortal(data)
        setAnswers(
          Object.fromEntries(
            data.questions
              .filter((question) => question.answer)
              .map((question) => [question.key, { value: question.answer!, note: question.note }]),
          ),
        )
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false))
  }, [params.token])

  const payload = () =>
    Object.entries(answers).map(([key, item]) => ({
      question_key: key,
      value: item.value,
      note: item.note,
    }))

  const save = async (submit: boolean) => {
    setError(null)
    try {
      await saveAnswers(params.token, payload(), submit)
      if (submit) {
        setPortal({ ...portal!, submitted: true })
        setStatus('Submitted. Thank you — nothing further is needed from you.')
      } else {
        setStatus('Progress saved. You can close this and come back to the same link.')
      }
    } catch (e) {
      setError((e as Error).message)
    }
  }

  if (loading) return <main><p className="muted">Loading…</p></main>
  if (error && !portal) return <main><p className="banner bad">{error}</p></main>
  if (!portal) return null

  const sections = portal.questions.reduce<Record<string, PortalQuestion[]>>((acc, question) => {
    acc[question.section] = [...(acc[question.section] ?? []), question]
    return acc
  }, {})

  const answeredCount = Object.keys(answers).length

  return (
    <main>
      <header>
        <h1>{portal.questionnaire}</h1>
        <p className="sub">
          For <strong>{portal.vendor_name}</strong> · due{' '}
          {new Date(portal.due_at).toLocaleDateString()}
        </p>
        <p className="muted">
          You can answer in stages — save at any point and return to this same link. There is
          nothing to sign up for.
        </p>
      </header>

      {status && <p className="banner ok">{status}</p>}
      {error && <p className="banner bad">{error}</p>}

      {portal.submitted ? (
        <p className="muted">This assessment has been submitted and can no longer be edited.</p>
      ) : (
        <>
          <p className="progress">
            {answeredCount} of {portal.questions.length} answered
          </p>

          {Object.entries(sections).map(([section, questions]) => (
            <section key={section} className="card">
              <h3>{section}</h3>
              {questions.map((question) => (
                <div key={question.key} className="question">
                  <p className="text">{question.text}</p>
                  <div className="options">
                    {question.options.map((option) => (
                      <label key={option} className={answers[question.key]?.value === option ? 'on' : ''}>
                        <input
                          type="radio"
                          name={question.key}
                          checked={answers[question.key]?.value === option}
                          onChange={() =>
                            setAnswers({
                              ...answers,
                              [question.key]: {
                                value: option,
                                note: answers[question.key]?.note ?? '',
                              },
                            })
                          }
                        />
                        {option}
                      </label>
                    ))}
                  </div>
                  <input
                    type="text"
                    className="note"
                    placeholder="Add context or reference a document (optional)"
                    value={answers[question.key]?.note ?? ''}
                    onChange={(event) =>
                      setAnswers({
                        ...answers,
                        [question.key]: {
                          value: answers[question.key]?.value ?? '',
                          note: event.target.value,
                        },
                      })
                    }
                  />
                </div>
              ))}
            </section>
          ))}

          <div className="actions sticky">
            <button className="ghost" onClick={() => save(false)}>Save progress</button>
            <button
              onClick={() => save(true)}
              disabled={answeredCount < portal.questions.length}
            >
              Submit
            </button>
          </div>
        </>
      )}
    </main>
  )
}
