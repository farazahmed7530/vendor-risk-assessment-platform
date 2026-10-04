'use client'

import { useEffect, useState } from 'react'

import { getAssessment, getVendors, sendAssessment, type VendorRow } from '@/lib/api'

const BAND_ORDER = ['low', 'moderate', 'high', 'critical'] as const

export default function Dashboard() {
  const [vendors, setVendors] = useState<VendorRow[]>([])
  const [detail, setDetail] = useState<any | null>(null)
  const [copied, setCopied] = useState<number | null>(null)

  const refresh = () => getVendors().then(setVendors)
  useEffect(() => { refresh() }, [])

  const assessed = vendors.filter((v) => v.latest_assessment?.score.answered)

  return (
    <main>
      <header>
        <h1>Vendor risk</h1>
        <p className="sub">
          Questionnaires out, responses scored, and every score traceable to the answers that
          produced it.
        </p>
      </header>

      <section className="matrix">
        {BAND_ORDER.map((band) => {
          const inBand = assessed.filter((v) => v.latest_assessment!.score.band === band)
          return (
            <div key={band} className={`bucket ${band}`}>
              <span className="count">{inBand.length}</span>
              <label>{band}</label>
              <ul>
                {inBand.map((vendor) => <li key={vendor.id}>{vendor.name}</li>)}
              </ul>
            </div>
          )
        })}
      </section>

      <h2>Vendors</h2>
      {vendors.map((vendor) => {
        const assessment = vendor.latest_assessment
        const score = assessment?.score
        const complete = score && score.answered === score.total_questions

        return (
          <article key={vendor.id} className="card">
            <div className="card-head">
              <div>
                <h3>{vendor.name}</h3>
                <p className="muted">{vendor.service}</p>
                <p className="muted">
                  Criticality <strong>{vendor.criticality}</strong> · {vendor.contact_email}
                </p>
              </div>

              <div className="right">
                {complete ? (
                  <>
                    <span className={`score ${score!.band}`}>{score!.residual_risk}</span>
                    <label className="muted">residual risk</label>
                  </>
                ) : (
                  <span className="pill warn">
                    {score ? `${score.answered}/${score.total_questions} answered` : 'not sent'}
                  </span>
                )}
              </div>
            </div>

            <div className="actions">
              {assessment && (
                <>
                  <button
                    className="ghost"
                    onClick={async () =>
                      setDetail(await getAssessment(vendor.id, assessment.id))
                    }
                  >
                    {complete ? 'View scoring' : 'View responses'}
                  </button>
                  <button
                    className="ghost"
                    onClick={() => {
                      navigator.clipboard?.writeText(
                        `${location.origin}/vendor/${assessment.access_token}`,
                      )
                      setCopied(vendor.id)
                      setTimeout(() => setCopied(null), 2000)
                    }}
                  >
                    {copied === vendor.id ? 'Link copied' : 'Copy vendor link'}
                  </button>
                </>
              )}
              <button
                className="ghost"
                onClick={async () => { await sendAssessment(vendor.id); refresh() }}
              >
                Send new assessment
              </button>
            </div>
          </article>
        )
      })}

      {detail && (
        <div className="panel">
          <div className="card-head">
            <div>
              <h2>{detail.vendor.name}</h2>
              <p className="muted">{detail.assessment.questionnaire}</p>
            </div>
            <button className="ghost" onClick={() => setDetail(null)}>Close</button>
          </div>

          <div className="working">
            <h4>How this score was reached</h4>
            <p>
              Inherent risk <strong>{detail.score.inherent_risk}</strong> — the weighted mean
              of every answered question.
            </p>
            <p>
              Vendor criticality is <strong>{detail.score.criticality}</strong>, multiplier ×
              {detail.score.criticality_multiplier}.
            </p>
            <p>
              Residual risk{' '}
              <strong className={detail.score.band}>{detail.score.residual_risk}</strong> —
              band <strong>{detail.score.band}</strong>.
            </p>
          </div>

          <h4>By section</h4>
          <table>
            <tbody>
              {Object.entries(detail.score.section_scores).map(([section, value]) => (
                <tr key={section}>
                  <td>{section}</td>
                  <td className="num">{String(value)}</td>
                  <td className="bar">
                    <span style={{ width: `${value}%` }} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <h4>Biggest contributors</h4>
          <table>
            <thead>
              <tr><th>Question</th><th>Answer</th><th>Risk</th><th>Weight</th></tr>
            </thead>
            <tbody>
              {detail.score.top_risks.map((risk: any) => (
                <tr key={risk.key}>
                  <td>{risk.question}</td>
                  <td>{risk.answer}</td>
                  <td className="num">{risk.risk}</td>
                  <td className="num">×{risk.weight}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {detail.score.unanswered.length > 0 && (
            <p className="pill warn">
              {detail.score.unanswered.length} question(s) unanswered — not counted, not assumed.
            </p>
          )}
        </div>
      )}
    </main>
  )
}
