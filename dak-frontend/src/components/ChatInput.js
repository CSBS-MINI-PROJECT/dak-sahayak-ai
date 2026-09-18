'use client';

import { useState, useRef, useEffect } from 'react';

const PLACEHOLDERS = {
  'English': 'Ask Dak Sahayak or speak in English...',
  'Hindi': 'डाक सहायक से पूछें या हिन्दी में बोलें...',
  'Kannada': 'ಡಾಕ್ ಸಹಾಯಕ್ ಅವರನ್ನು ಕೇಳಿ ಅಥವಾ ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡಿ...',
  'Tamil': 'தபால் உதவியாளரிடம் கேளுங்கள் அல்லது தமிழில் பேசவும்...',
  'Telugu': 'డాక్ సహాయక్‌ని అడగండి లేదా తెలుగులో మాట్లాడండి...',
  'Marathi': 'डाक सहाय्यकला विचारा किंवा मराठीत बोला...',
  'Bengali': 'ডাক সহায়ককে জিজ্ঞাসা করুন বা বাংলায় বলুন...'
};

const SPEECH_LANG_MAP = {
  'English': 'en-IN',
  'Hindi': 'hi-IN',
  'Kannada': 'kn-IN',
  'Tamil': 'ta-IN',
  'Telugu': 'te-IN',
  'Marathi': 'mr-IN',
  'Bengali': 'bn-IN'
};

export default function ChatInput({ onSend, disabled, language = 'English' }) {
  const [text, setText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const textareaRef = useRef(null);
  const recognitionRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [text]);

  // Initialize and clean up speech recognition
  useEffect(() => {
    const SpeechRecognition = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition);
    if (!SpeechRecognition) {
      setSpeechSupported(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = SPEECH_LANG_MAP[language] || 'en-IN';

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event) => {
        let transcript = '';
        for (let i = 0; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        if (transcript) {
          setText(transcript);
        }
      };

      recognition.onerror = (event) => {
        console.warn('Speech recognition status:', event.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    } catch (e) {
      console.warn('Speech recognition setup failed:', e);
      setSpeechSupported(false);
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
    };
  }, [language]);

  const toggleListening = () => {
    if (!speechSupported) {
      alert('Speech recognition is supported in Chrome, Edge, Safari, and Brave browsers.');
      return;
    }

    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    } else {
      try {
        if (recognitionRef.current) {
          recognitionRef.current.lang = SPEECH_LANG_MAP[language] || 'en-IN';
          recognitionRef.current.start();
          setIsListening(true);
        }
      } catch (err) {
        console.error('Error starting speech recognition:', err);
      }
    }
  };

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!text.trim() || disabled) return;
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    }
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

  const placeholder = isListening
    ? `🎙️ Listening in ${language} (${SPEECH_LANG_MAP[language] || 'en-IN'})... Speak now.`
    : (PLACEHOLDERS[language] || PLACEHOLDERS['English']);

  return (
    <div className="input-section">
      <form onSubmit={handleSubmit} className={`input-container ${isListening ? 'listening-active' : ''}`}>
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

        <div className="input-actions-group">
          {/* Speech-to-Text Microphone Button */}
          <button
            type="button"
            className={`mic-action-btn ${isListening ? 'recording' : ''}`}
            onClick={toggleListening}
            disabled={disabled}
            title={isListening ? "Stop listening" : `Speak in ${language}`}
          >
            <i className={`fa-solid ${isListening ? 'fa-microphone-lines pulse-icon' : 'fa-microphone'}`}></i>
          </button>

          {/* Send Action Button */}
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
        </div>
      </form>

      {isListening && (
        <div className="listening-banner">
          <span className="live-dot"></span>
          <span>Listening to your voice in <strong>{language}</strong>. Click the mic button or press enter when done.</span>
        </div>
      )}

      <p className="input-disclaimer">
        Dak Sahayak supports Voice & Text with Indian accents across 7 Indian languages.
      </p>
    </div>
  );
}
