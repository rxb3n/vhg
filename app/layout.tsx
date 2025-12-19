import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Viral Hook Generator',
  description: 'Generate viral video hooks from product images',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}

