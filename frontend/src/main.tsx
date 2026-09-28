import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Inter servito dall'app e non da Google: la PWA deve aprirsi anche offline, e un
// carattere preso da un terzo a ogni avvio è una chiamata che nessuno ha chiesto
import "@fontsource-variable/inter";
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
