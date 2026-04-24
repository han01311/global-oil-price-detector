import './App.css'
import { Card } from './components/common/Card'
import { Badge } from './components/common/Badge'
import { PriceDisplay } from './components/common/PriceDisplay'
import { Skeleton } from './components/common/Skeleton'
import { ErrorBoundary } from './components/common/ErrorBoundary'

function App() {
  return (
    <ErrorBoundary>
      <div className="dashboard-grid">
        <header className="dashboard-header">
          <h1>Petro-AX Dashboard</h1>
        </header>

        <main className="dashboard-main">
          <Card title="Live WTI Price">
            <PriceDisplay value={85.54} change={2.33} size="large" />
          </Card>
          <Card title="Market Factors">
            <div className="badge-container">
              <Badge category="geopolitics">Geopolitics</Badge>
              <Badge category="supply">Supply</Badge>
              <Badge category="demand">Demand</Badge>
              <Badge category="macro">Macro</Badge>
              <Badge category="climate">Climate</Badge>
              <Badge category="speculation">Speculation</Badge>
            </div>
          </Card>
          <Card title="Loading State Example">
            <Skeleton height="2rem" width="50%" />
            <Skeleton height="1rem" style={{ marginTop: '1rem' }} />
            <Skeleton height="1rem" style={{ marginTop: '0.5rem' }} />
          </Card>
        </main>

        <aside className="dashboard-sidebar">
          <Card title="AI Briefing">
            <p>Briefing content will go here.</p>
          </Card>
        </aside>
      </div>
    </ErrorBoundary>
  )
}

export default App
