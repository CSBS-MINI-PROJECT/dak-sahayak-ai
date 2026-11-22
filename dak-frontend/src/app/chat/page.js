'use client';

import { useState, useEffect, useCallback } from 'react';
import AuthGuard from '../../components/AuthGuard';
import Sidebar from '../../components/Sidebar';
import ChatArea from '../../components/ChatArea';
import ChatInput from '../../components/ChatInput';
import TariffCalculator from '../../components/TariffCalculator';
import PincodeLookup from '../../components/PincodeLookup';
import FinancialCalculator from '../../components/FinancialCalculator';
import ThemeToggle from '../../components/ThemeToggle';
import { supabase } from '../../lib/supabase';
import {
  fetchConversations,
  createConversation,
  deleteConversation,
  fetchMessages,
  sendChatMessageStream,
  reversePincode
} from '../../lib/api';

export default function ChatPage() {
  const [user, setUser] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [streamingText, setStreamingText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [language, setLanguage] = useState('English');
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Modals state
  const [activeModal, setActiveModal] = useState(null);
  const [locationToast, setLocationToast] = useState('');

  // 1. Initial Load: User & Conversations
  useEffect(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setSidebarOpen(false);
    }

    supabase.auth.getUser()
      .then(({ data: { user } = {} }) => {
        if (user) {
          setUser(user);
          loadConversations();
        }
      })
      .catch((err) => {
        console.warn('Error fetching user in chat page:', err);
      });
  }, []);

  const closeMobileSidebar = () => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  };

  const loadConversations = async () => {
    try {
      const list = await fetchConversations();
      setConversations(list);
      // Keep on New Chat screen by default on initial load; older chats remain accessible in sidebar history
      setActiveConvId(null);
      setMessages([]);
    } catch (err) {
      console.error('Error loading conversations:', err);
    }
  };

  const selectConversation = async (convId) => {
    closeMobileSidebar();
    setActiveConvId(convId);
    setStreamingText('');
    setIsStreaming(false);
    try {
      const msgs = await fetchMessages(convId);
      setMessages(msgs);
    } catch (err) {
      console.error('Error loading messages:', err);
      setMessages([]);
    }
  };

  const handleNewChat = () => {
    closeMobileSidebar();
    setActiveConvId(null);
    setMessages([]);
    setStreamingText('');
    setIsStreaming(false);
  };

  const handleDeleteConv = async (convId) => {
    try {
      await deleteConversation(convId);
      setConversations(prev => prev.filter(c => c.id !== convId));
      if (activeConvId === convId) {
        setActiveConvId(null);
        setMessages([]);
      }
    } catch (err) {
      console.error('Error deleting conversation:', err);
    }
  };

  // 2. Sending Chat Message with Real-time Token Streaming
  const handleSendMessage = async (text) => {
    if (!text.trim() || isStreaming) return;

    let currentConvId = activeConvId;

    // If no active conversation, create one first
    if (!currentConvId) {
      try {
        const newConv = await createConversation(text.slice(0, 35));
        currentConvId = newConv.conversation_id || newConv.id;
        setActiveConvId(currentConvId);
        setConversations(prev => [{ id: currentConvId, title: text.slice(0, 35) }, ...prev]);
      } catch (err) {
        console.error('Failed to create auto conversation:', err);
      }
    }

    // Append user message immediately to UI
    const userMsg = { id: `temp-${Date.now()}`, role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setIsStreaming(true);
    setStreamingText('');

    await sendChatMessageStream({
      message: text,
      conversationId: currentConvId,
      language,
      onChunk: (_chunk, accumulated) => {
        setStreamingText(accumulated);
      },
      onDone: (finalText) => {
        setIsStreaming(false);
        setStreamingText('');
        setMessages(prev => [
          ...prev,
          { id: `resp-${Date.now()}`, role: 'assistant', content: finalText }
        ]);
        // Refresh conversation list to get updated title/timestamp
        fetchConversations().then(setConversations).catch(() => { });
      },
      onError: (err) => {
        setIsStreaming(false);
        setStreamingText('');
        const rawMsg = err?.message || '';
        const isFetchError = rawMsg.includes('Failed to fetch') || rawMsg.includes('NetworkError');
        const content = isFetchError
          ? '⚠️ Backend Server Unreachable: Could not connect to http://localhost:5000. Please ensure the Python Flask backend is running (`start_backend.bat` or `cd dak-backend && python app.py`).'
          : `⚠️ Connection error: ${rawMsg || 'Failed to reach AI service'}`;

        setMessages(prev => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: 'assistant',
            content
          }
        ]);
      }
    });
  };

  // 3. Geolocation "My PIN" Handler
  const handleDetectLocation = () => {
    if (!navigator.geolocation) {
      setLocationToast('Geolocation is not supported by your browser.');
      return;
    }

    setLocationToast('Locating your coordinates...');
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        try {
          const res = await reversePincode(latitude, longitude);
          if (res.status === 'Success' && res.pincode) {
            setLocationToast(`📍 Resolved PIN: ${res.pincode}`);
            handleSendMessage(`What are the post office details for PIN code ${res.pincode}?`);
          } else {
            setLocationToast('Could not resolve PIN automatically. Please enter your PIN.');
          }
        } catch (err) {
          setLocationToast('Location lookup failed. Please type your PIN.');
        }
      },
      (err) => {
        setLocationToast('Location access denied. Please enter your 6-digit PIN manually.');
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  const handleOpenModal = (modalName) => {
    closeMobileSidebar();
    if (modalName === 'location') {
      handleDetectLocation();
    } else {
      setActiveModal(modalName);
    }
  };

  return (
    <AuthGuard>
      <div className="app-layout min-h-[100dvh] h-[100dvh] w-full max-w-[100vw] overflow-x-hidden overflow-y-hidden flex flex-col md:flex-row relative">
        {/* Mobile Drawer Backdrop */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden transition-opacity duration-300"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        <Sidebar
          isOpen={sidebarOpen}
          conversations={conversations}
          activeConvId={activeConvId}
          onSelectConv={selectConversation}
          onNewChat={handleNewChat}
          onDeleteConv={handleDeleteConv}
          onOpenModal={handleOpenModal}
          onClose={() => setSidebarOpen(false)}
          userEmail={user?.email}
        />

        <div className="main-chat flex-1 flex flex-col min-h-[100dvh] h-[100dvh] w-full max-w-full overflow-x-hidden relative">
          <header className="chat-header flex items-center justify-between px-3 md:px-6 py-2.5 md:py-3 border-b border-[var(--border-color)] bg-[var(--header-bg)] z-10 shrink-0">
            <div className="header-left flex items-center gap-2 md:gap-3 shrink-0">
              <button
                className="toggle-sidebar-btn flex items-center justify-center p-2 rounded-lg text-gray-300 hover:text-white hover:bg-white/10 transition-colors"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                title="Toggle Sidebar"
                aria-label="Toggle Navigation Sidebar"
              >
                <i className="fa-solid fa-bars text-lg"></i>
              </button>
              <div className="md:hidden flex items-center gap-1.5 font-semibold text-sm text-[var(--text-bright)] whitespace-nowrap">
                <i className="fa-solid fa-envelope-open-text text-[var(--accent-red)] text-base"></i>
                <span className="whitespace-nowrap font-bold">Dak Sahayak</span>
              </div>
            </div>

            <div className="header-right flex items-center gap-1.5 md:gap-3 shrink-0">
              <ThemeToggle />
              <div className="relative inline-flex items-center shrink-0">
                <i className="fa-solid fa-globe absolute left-2 md:left-2.5 text-[11px] md:text-xs text-[var(--text-muted)] pointer-events-none z-10"></i>
                <select
                  className="lang-select pl-6 pr-5 md:pl-7 md:pr-7 py-1 text-xs md:text-sm rounded-lg shrink-0 appearance-none bg-[var(--bg-secondary)] text-[var(--text-main)] border border-[var(--border-color)] cursor-pointer"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  aria-label="Select Language"
                >
                  <option value="English">English</option>
                  <option value="Hindi">हिन्दी (Hindi)</option>
                  <option value="Kannada">ಕನ್ನಡ (Kannada)</option>
                  <option value="Tamil">தமிழ் (Tamil)</option>
                  <option value="Telugu">తెలుగు (Telugu)</option>
                  <option value="Marathi">मराठी (Marathi)</option>
                  <option value="Bengali">বাংলা (Bengali)</option>
                </select>
                <i className="fa-solid fa-chevron-down absolute right-1.5 md:right-2 text-[9px] md:text-[10px] text-[var(--text-muted)] pointer-events-none"></i>
              </div>
            </div>
          </header>

          {locationToast && (
            <div style={{ backgroundColor: 'rgba(245, 166, 35, 0.15)', borderBottom: '1px solid rgba(245, 166, 35, 0.3)', color: 'var(--accent-gold)', padding: '8px 24px', fontSize: '0.85rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span><i className="fa-solid fa-location-dot"></i> {locationToast}</span>
              <button onClick={() => setLocationToast('')} style={{ color: 'var(--accent-gold)' }}>&times;</button>
            </div>
          )}

          <ChatArea
            messages={messages}
            streamingText={streamingText}
            isStreaming={isStreaming}
            language={language}
            onSelectPrompt={(prompt) => handleSendMessage(prompt)}
          />

          <ChatInput
            onSend={handleSendMessage}
            disabled={isStreaming}
            language={language}
          />
        </div>

        {/* Feature Modals */}
        <TariffCalculator
          isOpen={activeModal === 'tariff'}
          onClose={() => setActiveModal(null)}
        />

        <PincodeLookup
          isOpen={activeModal === 'pincode'}
          onClose={() => setActiveModal(null)}
        />

        <FinancialCalculator
          isOpen={activeModal === 'financial'}
          onClose={() => setActiveModal(null)}
        />
      </div>
    </AuthGuard>
  );
}
