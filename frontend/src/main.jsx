import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

/**
 * The entry point for the DSR-CRAG frontend application.
 *
 * This file initializes the React application, renders the root App component,
 * and sets up strict mode for development.
 */
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)