import { useState, useEffect, useCallback } from 'react'
import Sidebar from './components/Sidebar.jsx'
import Topbar from './components/Topbar.jsx'
import ControlsBar from './components/ControlsBar.jsx'
import TopicsChips from './components/TopicsChips.jsx'
import ChatWindow from './components/ChatWindow.jsx'
import InputBar from './components/InputBar.jsx'
import { useChat } from './hooks/useChat.js'
import { useDocuments } from './hooks/useDocuments.js'

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const {
    conversations, activeConversation, activeId,
    selectConversation, startNewChat, deleteConversation,
    sendMessage, isLoading, error, clearError,
    court, setCourt, style, setStyle,
  } = useChat()

  const {
    documents, activeDocIds, isUploading,
    uploadFile, removeDocument, toggleDocActive,
  } = useDocuments()

  const handleSend = useCallback((text) => {
    sendMessage(text, activeDocIds)
  }, [sendMessage, activeDocIds])

  // Auto-close sidebar on mobile
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)')
    if (mq.matches) setSidebarOpen(false)
    const h = (e) => { if (e.matches) setSidebarOpen(false) }
    mq.addEventListener('change', h)
    return () => mq.removeEventListener('change', h)
  }, [])

  return (
    <div className="app-root">
      <Sidebar
        open={sidebarOpen}
        conversations={conversations}
        activeId={activeId}
        onSelect={selectConversation}
        onNewChat={startNewChat}
        onDelete={deleteConversation}
        documents={documents}
        activeDocIds={activeDocIds}
        onRemoveDoc={removeDocument}
        onToggleDoc={toggleDocActive}
      />

      <div className="main-area">
        <Topbar
          title={activeConversation?.title || 'New conversation'}
          msgCount={activeConversation?.messages?.length || 0}
          onToggleSidebar={() => setSidebarOpen(v => !v)}
          sidebarOpen={sidebarOpen}
        />
        <ControlsBar court={court} setCourt={setCourt} style={style} setStyle={setStyle} />
        <TopicsChips onSelect={handleSend} disabled={isLoading} />
        <ChatWindow
          messages={activeConversation?.messages || []}
          isLoading={isLoading}
          error={error}
          onClearError={clearError}
          onSuggestionSelect={handleSend}
        />
        <InputBar
          onSend={handleSend}
          disabled={isLoading}
          documents={documents}
          activeDocIds={activeDocIds}
          onUpload={uploadFile}
          onRemoveDoc={removeDocument}
          onToggleDoc={toggleDocActive}
          isUploading={isUploading}
        />
      </div>
    </div>
  )
}
