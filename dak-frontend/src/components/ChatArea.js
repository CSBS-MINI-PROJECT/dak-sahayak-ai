'use client';

import { useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble';

const PROMPT_SUGGESTIONS = [
  {
    icon: 'fa-solid fa-bolt',
    title: 'Speed Post Rates & Timelines',
    query: 'What are domestic Speed Post tariff rates and delivery timelines?'
  },
  {
    icon: 'fa-solid fa-piggy-bank',
    title: 'Sukanya Samriddhi (SSA)',
    query: 'Tell me about Sukanya Samriddhi Account (SSA) interest rate, tax benefits and eligibility.'
  },
  {
    icon: 'fa-solid fa-hand-holding-dollar',
    title: 'Public Provident Fund (PPF)',
    query: 'What are the features, interest rate, and tax deductions under PPF?'
  },
  {
    icon: 'fa-solid fa-file-invoice',
    title: 'India Post Bank Fees',
    query: 'What are the official fees for duplicate passbook, account transfer, and cheque book?'
  }
];

export default function ChatArea({
  messages = [],
  streamingText = '',
  isStreaming = false,
  language = 'English',
  onSelectPrompt
}) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText]);

  const showWelcome = messages.length === 0 && !streamingText;

  return (
    <div className="message-thread">
      {showWelcome ? (
        <div className="welcome-hero">
          <div className="welcome-logo">
            <i className="fa-solid fa-envelope-open-text"></i>
          </div>
          <h1 className="welcome-title">
            Namaste, I am <span>Dak Sahayak</span>
          </h1>
          <p className="welcome-desc">
            Your official India Post assistant powered by Gemini AI and Supabase Vector DB. Ask about savings schemes, mail tariffs, bank charges, or PIN directory.
          </p>

          <div className="prompt-suggestions">
            {PROMPT_SUGGESTIONS.map((item, idx) => (
              <div
                key={idx}
                className="suggestion-card"
                onClick={() => onSelectPrompt(item.query)}
              >
                <i className={`${item.icon} suggestion-icon`}></i>
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-bright)', marginBottom: '4px' }}>
                    {item.title}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                    {item.query}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <>
          {messages.map((msg, index) => (
            <MessageBubble
              key={msg.id || index}
              role={msg.role}
              content={msg.content}
              language={language}
            />
          ))}

          {isStreaming && (
            <MessageBubble
              role="assistant"
              content={streamingText}
              isStreaming={true}
              language={language}
            />
          )}

          <div ref={bottomRef} />
        </>
      )}
    </div>
  );
}
