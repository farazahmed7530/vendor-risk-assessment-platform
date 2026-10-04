import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Vendor Risk',
  description: 'Send security questionnaires, score the responses, show the working.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
