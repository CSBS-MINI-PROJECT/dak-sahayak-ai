'use client';

import { supabase } from '../lib/supabase';
import { useRouter } from 'next/navigation';

export default function Sidebar({
  isOpen,
  conversations = [],
  activeConvId,
  onSelectConv,
  onNewChat,
  onDeleteConv,
  onOpenModal,
  userEmail
}) {
  const router = useRouter();

  const handleLogout = async () => {
    await supabase.auth.signOut();
    router.replace('/login');
  };

  const avatarLetter = userEmail ? userEmail.charAt(0).toUpperCase() : 'U';

  return (
    <aside className={`sidebar ${!isOpen ? 'closed' : ''}`}>
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <div className="brand-icon">
            <i className="fa-solid fa-envelope-open-text"></i>
          </div>
          <div className="brand-title">
            Dak <span>Sahayak</span>
          </div>
        </div>
      </div>

      <button className="new-chat-btn" onClick={onNewChat}>
        <i className="fa-solid fa-plus"></i>
        <span>New Chat</span>
      </button>

      <div className="sidebar-tools-grid">
        <button className="tool-btn tool-tariff" onClick={() => onOpenModal('tariff')}>
          <i className="fa-solid fa-calculator"></i>
          <span>Tariff Calc</span>
        </button>
        <button className="tool-btn tool-pincode" onClick={() => onOpenModal('pincode')}>
          <i className="fa-solid fa-location-dot"></i>
          <span>PIN Search</span>
        </button>
        <button className="tool-btn tool-financial" onClick={() => onOpenModal('financial')}>
          <i className="fa-solid fa-coins"></i>
          <span>Savings ROI</span>
        </button>
        <button className="tool-btn tool-location" onClick={() => onOpenModal('location')}>
          <i className="fa-solid fa-location-crosshairs"></i>
          <span>My PIN</span>
        </button>
      </div>

      <div className="conv-list">
        {conversations.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '24px 0' }}>
            No conversations yet
          </p>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conv-item ${activeConvId === conv.id ? 'active' : ''}`}
              onClick={() => onSelectConv(conv.id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
                <i className="fa-regular fa-message" style={{ fontSize: '0.85rem', opacity: 0.7 }}></i>
                <span className="conv-title" title={conv.title || 'New Chat'}>
                  {conv.title || 'New Chat'}
                </span>
              </div>
              <button
                className="conv-del-btn"
                title="Delete Chat"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteConv(conv.id);
                }}
              >
                <i className="fa-regular fa-trash-can"></i>
              </button>
            </div>
          ))
        )}
      </div>

      <div className="sidebar-footer">
        <div className="user-profile-row">
          <div className="user-info">
            <div className="user-avatar">{avatarLetter}</div>
            <div className="user-email" title={userEmail}>
              {userEmail || 'Account'}
            </div>
          </div>
          <button className="logout-btn" title="Sign Out" onClick={handleLogout}>
            <i className="fa-solid fa-arrow-right-from-bracket"></i>
          </button>
        </div>
      </div>
    </aside>
  );
}
