import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Toaster } from '@/components/ui/sonner'
import './index.css'
import App from './App.tsx'
import { initializePreferences } from './lib/local-preference-store'

void initializePreferences().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
      <Toaster position="bottom-right" closeButton />
    </StrictMode>,
  )
})
