import React from 'react'
import { createRoot } from 'react-dom/client'
// Fontes empacotadas no build: o app precisa funcionar sem internet.
import '@fontsource/space-grotesk/500.css'
import '@fontsource/space-grotesk/700.css'
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import './styles.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
