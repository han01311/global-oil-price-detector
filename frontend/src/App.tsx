import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './App.css'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import { ToastRenderer } from './components/common/Toast'
import { Dashboard } from './components/Dashboard/Dashboard'
import { AdminPanel } from './components/Admin/AdminPanel'
import { DashboardProvider } from './context/DashboardContext'
import { ToastProvider } from './context/ToastContext'

function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route
              path="/"
              element={
                <DashboardProvider>
                  <Dashboard />
                </DashboardProvider>
              }
            />
            <Route path="/admin" element={<AdminPanel />} />
          </Routes>
        </BrowserRouter>
        <ToastRenderer />
      </ToastProvider>
    </ErrorBoundary>
  )
}

export default App
