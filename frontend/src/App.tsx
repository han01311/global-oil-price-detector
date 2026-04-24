import './App.css'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import { Dashboard } from './components/Dashboard/Dashboard'
import { DashboardProvider } from './context/DashboardContext'

function App() {
  return (
    <ErrorBoundary>
      <DashboardProvider>
        <Dashboard />
      </DashboardProvider>
    </ErrorBoundary>
  )
}

export default App
