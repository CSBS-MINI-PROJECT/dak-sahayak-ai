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

  const loadConversations = async () => {
    try {
      const list = await fetchConversations();
      setConversations(list);
      if (list.length > 0 && !activeConvId) {
        selectConversation(list[0].id);
      }
    } catch (err) {
      console.error('Error loading conversations:', err);
    }
  };

  const selectConversation = async (convId) => {
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

  const handleNewChat = async () => {
    try {
      const newConv = await createConversation('New Chat');
      setConversations(prev => [newConv, ...prev]);
      setActiveConvId(newConv.conversation_id || newConv.id);
      setMessages([]);
      setStreamingText('');
      setIsStreaming(false);
    } catch (err) {
      console.error('Error creating new chat:', err);
    }
  };

  const handleDeleteConv = async (convId) => {
    try {
      await deleteConversation(convId);
      setConversations(prev => prev.filter(c => c.id !== convId));
      if (activeConvId === convId) {
        const remaining = conversations.filter(c => c.id !== convId);
        if (remaining.length > 0) {
          selectConversation(remaining[0].id);
        } else {
          setActiveConvId(null);
          setMessages([]);
        }
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
        setMessages(prev => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: 'assistant',
            content: `⚠️ Connection error: ${err.message || 'Failed to reach AI service'}`
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
    if (modalName === 'location') {
      handleDetectLocation();
    } else {
      setActiveModal(modalName);
    }
  };

  return (
    <AuthGuard>
      <div className="app-layout">
        <Sidebar
          isOpen={sidebarOpen}
          conversations={conversations}
          activeConvId={activeConvId}
          onSelectConv={selectConversation}
          onNewChat={handleNewChat}
          onDeleteConv={handleDeleteConv}
          onOpenModal={handleOpenModal}
          userEmail={user?.email}
        />

        <div className="main-chat">
          <header className="chat-header">
            <div className="header-left">
              <button
                className="toggle-sidebar-btn"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                title="Toggle Sidebar"
              >
                <i className="fa-solid fa-bars"></i>
              </button>
              <div className="chat-model-badge">
                <i className="fa-solid fa-envelope-open-text"></i>
                <span>Your official India Post AI assistant</span>
              </div>
            </div>

            <div className="header-right">
              <ThemeToggle />
              <select
                className="lang-select"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              >
                <option value="English">English</option>
                <option value="Hindi">हिन्दी (Hindi)</option>
                <option value="Kannada">ಕನ್ನಡ (Kannada)</option>
                <option value="Tamil">தமிழ் (Tamil)</option>
                <option value="Telugu">తెలుగు (Telugu)</option>
                <option value="Marathi">मराठी (Marathi)</option>
                <option value="Bengali">বাংলা (Bengali)</option>
              </select>
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
