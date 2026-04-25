import './App.css'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import { ToastRenderer } from './components/common/Toast'
import { Dashboard } from './components/Dashboard/Dashboard'
import { DashboardProvider } from './context/DashboardContext'
import { ToastProvider } from './context/ToastContext'

function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <DashboardProvider>
          <Dashboard />
        </DashboardProvider>
        <ToastRenderer />
      </ToastProvider>
    </ErrorBoundary>
  )
}

export default App
