import './App.css'
import { ErrorBoundary } from './components/common/ErrorBoundary'
import { Dashboard } from './components/Dashboard/Dashboard'

function App() {
  return (
    <ErrorBoundary>
      <Dashboard />
    </ErrorBoundary>
  )
}

export default App
