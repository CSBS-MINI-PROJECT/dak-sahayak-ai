'use client';

import { useState, useRef, useEffect } from 'react';

const PLACEHOLDERS = {
  'English': 'Ask anything here...',
  'Hindi': 'यहाँ कुछ भी पूछें...',
  'Kannada': 'ಇಲ್ಲಿ ಏನಾದರೂ ಕೇಳಿ...',
  'Tamil': 'இங்கே எதையும் கேளுங்கள்...',
  'Telugu': 'ఇక్కడ ఏదైనా అడగండి...',
  'Marathi': 'येथे काहीही विचारा...',
  'Bengali': 'এখানে যেকোনো কিছু জিজ্ঞাসা করুন...'
};

export default function ChatInput({ onSend, disabled, language = 'English' }) {
  const [text, setText] = useState('');
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [text]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!text.trim() || disabled) return;
    onSend(text.trim());
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const placeholder = PLACEHOLDERS[language] || PLACEHOLDERS['English'];

  return (
    <div className="input-section">
      <form onSubmit={handleSubmit} className="input-container">
        <textarea
          ref={textareaRef}
          className="chat-input"
          placeholder={placeholder}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={disabled}
        />
        <button
          type="submit"
          className="send-action-btn"
          disabled={!text.trim() || disabled}
          title="Send message"
        >
          {disabled ? (
            <i className="fa-solid fa-spinner fa-spin"></i>
          ) : (
            <i className="fa-solid fa-arrow-up"></i>
          )}
        </button>
      </form>
      <p className="input-disclaimer">
        Dak Sahayak uses Google Gemini + Supabase Vector RAG. Answers are grounded in official India Post rules.
      </p>
    </div>
  );
}
