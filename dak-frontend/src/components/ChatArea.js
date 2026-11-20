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
        <div className="welcome-hero w-full max-w-3xl mx-auto px-4 py-4 md:py-6 flex flex-col items-center text-center space-y-3 md:space-y-5">
          <div className="welcome-logo w-11 h-11 md:w-14 md:h-14 text-xl md:text-2xl rounded-xl md:rounded-2xl !mb-0 md:!mb-1">
            <i className="fa-solid fa-envelope-open-text"></i>
          </div>
          <h1 className="welcome-title text-2xl sm:text-3xl md:text-4xl font-bold">
            Namaste, I am <span>Dak Sahayak</span>
          </h1>
          <p className="welcome-desc text-xs sm:text-sm md:text-base text-gray-400 max-w-xl">
            Your official India Post AI assistant. Ask about savings schemes, mail tariffs, bank charges, or PIN directory.
          </p>

          <div className="prompt-suggestions grid grid-cols-1 md:grid-cols-2 gap-2.5 md:gap-3 w-full max-w-2xl mt-4 md:mt-6">
            {PROMPT_SUGGESTIONS.map((item, idx) => (
              <div
                key={idx}
                className="suggestion-card flex items-start gap-2.5 md:gap-3 p-3.5 md:p-4 rounded-xl transition-all cursor-pointer w-full text-left"
                onClick={() => onSelectPrompt(item.query)}
              >
                <i className={`${item.icon} suggestion-icon shrink-0 mt-0.5 text-sm md:text-base`}></i>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-xs sm:text-sm md:text-[0.92rem] text-[var(--text-bright)] mb-0.5">
                    {item.title}
                  </div>
                  <div className="text-[0.78rem] sm:text-xs md:text-[0.82rem] text-[var(--text-muted)] line-clamp-2">
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
