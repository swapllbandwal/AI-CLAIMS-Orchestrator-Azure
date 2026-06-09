import React, { useState } from 'react'
import { Bot } from 'lucide-react'
import ClaimSubmissionForm from './components/ClaimSubmissionForm'
import Dashboard from './components/Dashboard'

function App() {
  const [activeTab, setActiveTab] = useState('submit')
  const [jumpToClaimId, setJumpToClaimId] = useState(null)

  const handleSubmitted = (claimId) => {
    setJumpToClaimId(claimId)
    setActiveTab('dashboard')
  }

  return (
    <div className="app">
      <header className="header">
        <div className="container">
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <Bot size={48} />
            <div>
              <h1>
                AI Claims Orchestrator
                <span className="azure-chip">Microsoft Azure AI</span>
              </h1>
              <p>
                Azure-Powered Insurance Claims Processing with Computer Vision &
                Claude Sonnet 4.6 (Foundry)
              </p>
            </div>
          </div>
        </div>
      </header>

      <div className="container">
        <div className="tabs">
          <button
            className={`tab-button ${activeTab === 'submit' ? 'active' : ''}`}
            onClick={() => setActiveTab('submit')}
          >
            📝 Submit Claim
          </button>
          <button
            className={`tab-button ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            📊 Claims Dashboard
          </button>
        </div>

        {activeTab === 'submit' && <ClaimSubmissionForm onSubmitted={handleSubmitted} />}
        {activeTab === 'dashboard' && (
          <Dashboard initialClaimId={jumpToClaimId} clearInitialClaimId={() => setJumpToClaimId(null)} />
        )}
      </div>
    </div>
  )
}

export default App
