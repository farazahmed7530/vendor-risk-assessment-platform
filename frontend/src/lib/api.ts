export interface Score {
  inherent_risk: number
  residual_risk: number
  band: 'low' | 'moderate' | 'high' | 'critical'
  criticality: string
  criticality_multiplier: number
  answered: number
  total_questions: number
  unanswered: string[]
  section_scores: Record<string, number>
  top_risks: Array<{
    key: string; section: string; question: string; answer: string
    risk: number; weight: number; contribution: number
  }>
}

export interface AssessmentView {
  id: number; status: string; questionnaire: string
  sent_at: string; due_at: string; submitted_at: string | null
  access_token: string; reviewer_note: string; score: Score
}

export interface VendorRow {
  id: number; name: string; service: string; contact_email: string
  criticality: string; latest_assessment: AssessmentView | null
}

export interface PortalQuestion {
  key: string; section: string; text: string
  options: string[]; answer: string | null; note: string
}

export interface Portal {
  vendor_name: string; questionnaire: string; status: string
  due_at: string; submitted: boolean; questions: PortalQuestion[]
}

async function call<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
    ...options,
  })
  if (!response.ok) throw new Error((await response.json()).detail ?? response.statusText)
  return response.json() as Promise<T>
}

export const getVendors = () => call<VendorRow[]>('/vendors')
export const getAssessment = (vendorId: number, assessmentId: number) =>
  call<any>(`/vendors/${vendorId}/assessments/${assessmentId}`)
export const sendAssessment = (vendorId: number) =>
  call(`/vendors/${vendorId}/assessments`, { method: 'POST' })

export const getPortal = (token: string) => call<Portal>(`/portal/${token}`)
export const saveAnswers = (
  token: string,
  answers: Array<{ question_key: string; value: string; note: string }>,
  submit = false,
) => call(`/portal/${token}`, { method: 'POST', body: JSON.stringify({ answers, submit }) })
