import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// The typefaces travel with the page, so it looks the same with no network.
import '@fontsource/silkscreen/latin-400.css'
import '@fontsource/silkscreen/latin-700.css'
import '@fontsource/space-mono/latin-400.css'
import '@fontsource/space-mono/latin-700.css'
import App from './App.jsx'
import './styles.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
