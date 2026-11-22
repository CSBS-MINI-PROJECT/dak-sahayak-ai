'use client';

import { useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble';

const PROMPT_SUGGESTIONS = [
  {
    icon: 'fa-solid fa-truck-fast',
    title: 'Track Parcel & Speed Post',
    query: 'How do I track my India Post parcel or consignment?'
  },
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
        <div className="welcome-hero w-full max-w-3xl mx-auto px-4 py-6 md:py-8 flex flex-col items-center justify-center text-center space-y-3.5 md:space-y-5 my-auto">
          <div className="welcome-logo w-14 h-14 md:w-16 md:h-16 text-2xl md:text-3xl rounded-2xl flex items-center justify-center shadow-[0_0_24px_rgba(196,18,47,0.55)] !mb-1 md:!mb-2">
            <i className="fa-solid fa-envelope-open-text"></i>
          </div>
          <h1 className="welcome-title text-2xl sm:text-3xl md:text-4xl font-bold tracking-tight">
            Namaste, I am <span>Dak Sahayak</span>
          </h1>
          <p className="welcome-desc text-xs sm:text-sm md:text-base text-gray-400 max-w-md md:max-w-xl leading-relaxed">
            Your official India Post AI assistant. Ask about savings schemes, mail tariffs, bank charges, or PIN directory.
          </p>

          <div className="prompt-suggestions hidden md:grid md:grid-cols-2 gap-3 w-full max-w-2xl mt-6">
            {PROMPT_SUGGESTIONS.map((item, idx) => (
              <div
                key={idx}
                className="suggestion-card flex items-start gap-3 p-4 rounded-xl transition-all cursor-pointer w-full text-left"
                onClick={() => onSelectPrompt(item.query)}
              >
                <i className={`${item.icon} suggestion-icon shrink-0 mt-1`}></i>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-[0.92rem] text-[var(--text-bright)] mb-1">
                    {item.title}
                  </div>
                  <div className="text-[0.82rem] text-[var(--text-muted)] line-clamp-2">
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
