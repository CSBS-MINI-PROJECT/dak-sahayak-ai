'use client';

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fetchTTSAudio, translateToEnglish } from '../lib/api';

export default function MessageBubble({ role, content, isStreaming = false, language = 'English' }) {
  const [copied, setCopied] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoadingAudio, setIsLoadingAudio] = useState(false);
  const [translatedText, setTranslatedText] = useState('');
  const [isTranslating, setIsTranslating] = useState(false);
  const [showTranslation, setShowTranslation] = useState(false);
  const [showDownloadMenu, setShowDownloadMenu] = useState(false);
  const audioRef = useRef(null);
  const audioUrlRef = useRef(null);

  const isBot = role === 'assistant' || role === 'bot';

  // Cleanup audio object & URL when component unmounts
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
      }
    };
  }, []);

  // Reset cached audio when content changes (e.g. different message)
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    setIsPlaying(false);
    setIsLoadingAudio(false);
  }, [content]);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleToggleSpeech = async () => {
    // Stop if already playing
    if (isPlaying) {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
      setIsPlaying(false);
      return;
    }

    try {
      // If audio was already fetched and ready, replay it
      if (audioRef.current && audioUrlRef.current) {
        audioRef.current.currentTime = 0;
        await audioRef.current.play();
        setIsPlaying(true);
        return;
      }

      setIsLoadingAudio(true);

      // Fetch the audio from backend TTS API
      const audioUrl = await fetchTTSAudio(content, effectiveLanguage);
      audioUrlRef.current = audioUrl;

      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      audio.onended = () => {
        setIsPlaying(false);
      };

      audio.onerror = (e) => {
        console.error('Audio playback error:', e);
        setIsPlaying(false);
        setIsLoadingAudio(false);
        // Clear broken audio reference
        audioRef.current = null;
        if (audioUrlRef.current) {
          URL.revokeObjectURL(audioUrlRef.current);
          audioUrlRef.current = null;
        }
      };

      await audio.play();
      setIsPlaying(true);
    } catch (err) {
      console.error('TTS speech synthesis error:', err);
      setIsPlaying(false);
      // Clear broken references on error
      audioRef.current = null;
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
    } finally {
      setIsLoadingAudio(false);
    }
  };

  const handleTranslate = async () => {
    // Toggle: if already showing translation, hide it
    if (showTranslation && translatedText) {
      setShowTranslation(false);
      return;
    }

    // If already translated before, just show it
    if (translatedText) {
      setShowTranslation(true);
      return;
    }

    try {
      setIsTranslating(true);
      const result = await translateToEnglish(content, effectiveLanguage);
      setTranslatedText(result);
      setShowTranslation(true);
    } catch (err) {
      console.error('Translation error:', err);
      setTranslatedText(`⚠️ Translation failed: ${err.message || 'Please try again.'}`);
      setShowTranslation(true);
    } finally {
      setIsTranslating(false);
    }
  };

  const handleDownload = (format = 'pdf') => {
    if (!content) return;
    const title = 'Dak_Sahayak_Information';
    const timestamp = new Date().toISOString().split('T')[0];

    if (format === 'doc' || format === 'txt') {
      const blob = new Blob([
        `DAK SAHAYAK (INDIA POST AI ASSISTANT)\nDate: ${new Date().toLocaleString('en-IN')}\n\n` +
        content +
        (translatedText ? `\n\n--- ENGLISH TRANSLATION ---\n${translatedText}` : '')
      ], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${title}_${timestamp}.${format === 'doc' ? 'doc' : 'txt'}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } else {
      // PDF print / save
      const printWindow = window.open('', '_blank');
      if (!printWindow) {
        alert('Please allow popups to download/print the PDF.');
        return;
      }
      
      const htmlContent = `
        <!DOCTYPE html>
        <html>
        <head>
          <title>${title} - ${timestamp}</title>
          <meta charset="utf-8" />
          <style>
            body {
              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
              line-height: 1.6;
              color: #1a1a1a;
              padding: 40px;
              max-width: 800px;
              margin: 0 auto;
            }
            .header {
              border-bottom: 2px solid #c4122f;
              padding-bottom: 12px;
              margin-bottom: 24px;
              display: flex;
              justify-content: space-between;
              align-items: center;
            }
            .header h1 {
              margin: 0;
              font-size: 20px;
              color: #c4122f;
            }
            .header .date {
              font-size: 12px;
              color: #666;
            }
            .content {
              font-size: 14px;
              white-space: pre-wrap;
              word-break: break-word;
            }
            .translation {
              margin-top: 24px;
              padding: 16px;
              background-color: #f8f9fa;
              border-left: 4px solid #f5a623;
              border-radius: 4px;
            }
            .footer {
              margin-top: 40px;
              padding-top: 12px;
              border-top: 1px solid #e0e0e0;
              font-size: 11px;
              color: #888;
              text-align: center;
            }
            @media print {
              body { padding: 20px; }
            }
          </style>
        </head>
        <body>
          <div class="header">
            <div>
              <h1>डाक सहायक (Dak Sahayak)</h1>
              <div style="font-size: 13px; color: #555;">Official India Post AI Information Report</div>
            </div>
            <div class="date">Generated: ${new Date().toLocaleString('en-IN')}</div>
          </div>
          <div class="content">${content.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
          ${translatedText ? `
            <div class="translation">
              <h3 style="margin-top:0; color:#333; font-size:15px;">English Translation</h3>
              <div style="white-space: pre-wrap;">${translatedText.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
            </div>
          ` : ''}
          <div class="footer">
            Generated via Dak Sahayak AI Assistant • Department of Posts, Government of India
          </div>
          <script>
            window.onload = function() {
              window.print();
            };
          </script>
        </body>
        </html>
      `;
      printWindow.document.open();
      printWindow.document.write(htmlContent);
      printWindow.document.close();
    }
  };

  // Detect script/language directly from the text content if dropdown is default 'English'
  const detectedNonEnglish = (() => {
    if (!content) return false;
    // Check for Devanagari, Kannada, Tamil, Telugu, Bengali scripts
    const nonLatinRegex = /[\u0900-\u097F\u0C80-\u0CFF\u0B80-\u0BFF\u0C00-\u0C7F\u0980-\u09FF]/;
    return nonLatinRegex.test(content);
  })();

  // Detect which specific Indian language is present in the text for accurate TTS
  const effectiveLanguage = (() => {
    if (language && language !== 'English') return language;
    if (!content) return 'English';
    if (/[\u0C80-\u0CFF]/.test(content)) return 'Kannada';
    if (/[\u0900-\u097F]/.test(content)) return 'Hindi';
    if (/[\u0B80-\u0BFF]/.test(content)) return 'Tamil';
    if (/[\u0C00-\u0C7F]/.test(content)) return 'Telugu';
    if (/[\u0980-\u09FF]/.test(content)) return 'Bengali';
    return 'English';
  })();

  // Show translate button if either language selector is non-English or the text itself contains Indian script
  const showTranslateBtn = isBot && (language !== 'English' || detectedNonEnglish);

  return (
    <div className={`message-row ${isBot ? 'bot' : 'user'}`}>
      {isBot && (
        <div className="message-avatar bot">
          <i className="fa-solid fa-robot"></i>
        </div>
      )}

      <div className="message-bubble">
        {isBot ? (
          <div className="bot-markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
            {isStreaming && <span className="typing-cursor"></span>}

            {/* Translation Display */}
            {showTranslation && translatedText && (
              <div className="translation-box">
                <div className="translation-header">
                  <i className="fa-solid fa-language"></i>
                  <span>English Translation</span>
                </div>
                <div className="translation-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {translatedText}
                  </ReactMarkdown>
                </div>
              </div>
            )}

            {!isStreaming && content && (
              <div style={{ marginTop: '12px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {/* TTS Speak / Stop Button */}
                <button
                  onClick={handleToggleSpeech}
                  disabled={isLoadingAudio}
                  className={`bubble-action-btn ${isPlaying ? 'playing' : ''}`}
                  title={isPlaying ? "Stop speech" : "Read response aloud in Indian accent"}
                >
                  {isLoadingAudio ? (
                    <>
                      <i className="fa-solid fa-spinner fa-spin"></i>
                      <span>Generating Voice...</span>
                    </>
                  ) : isPlaying ? (
                    <>
                      <i className="fa-solid fa-volume-high speech-pulse"></i>
                      <span style={{ color: 'var(--accent-gold)' }}>Stop Speaking</span>
                    </>
                  ) : (
                    <>
                      <i className="fa-solid fa-volume-high"></i>
                      <span>Listen</span>
                    </>
                  )}
                </button>

                {/* Translate to English Button */}
                {showTranslateBtn && (
                  <button
                    onClick={handleTranslate}
                    disabled={isTranslating}
                    className={`bubble-action-btn ${showTranslation ? 'translate-active' : ''}`}
                    title={showTranslation ? "Hide translation" : "Translate to English"}
                  >
                    {isTranslating ? (
                      <>
                        <i className="fa-solid fa-spinner fa-spin"></i>
                        <span>Translating...</span>
                      </>
                    ) : showTranslation ? (
                      <>
                        <i className="fa-solid fa-language"></i>
                        <span>Hide Translation</span>
                      </>
                    ) : (
                      <>
                        <i className="fa-solid fa-language"></i>
                        <span>Translate</span>
                      </>
                    )}
                  </button>
                )}

                {/* Copy Button */}
                <button
                  onClick={handleCopy}
                  className="bubble-action-btn"
                  title="Copy response"
                >
                  <i className={copied ? 'fa-solid fa-check text-green' : 'fa-regular fa-copy'}></i>
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>

                {/* Single Download Dropdown Button */}
                <div style={{ position: 'relative' }}>
                  <button
                    className="bubble-action-btn"
                    title="Download response"
                    onClick={() => setShowDownloadMenu(prev => !prev)}
                  >
                    <i className="fa-solid fa-download" style={{ color: '#ef5350' }}></i>
                    <span>Download</span>
                    <i className="fa-solid fa-chevron-down" style={{ fontSize: '0.6rem', marginLeft: '3px', opacity: 0.7 }}></i>
                  </button>

                  {showDownloadMenu && (
                    <div
                      style={{
                        position: 'absolute',
                        bottom: '110%',
                        left: 0,
                        background: '#1e2022',
                        border: '1px solid rgba(255,255,255,0.12)',
                        borderRadius: '10px',
                        overflow: 'hidden',
                        boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
                        minWidth: '170px',
                        zIndex: 100,
                      }}
                    >
                      {[
                        { format: 'pdf', label: 'PDF (Print)', icon: 'fa-file-pdf', color: '#ef5350' },
                        { format: 'doc', label: 'Word Doc (.doc)', icon: 'fa-file-word', color: '#42a5f5' },
                        { format: 'txt', label: 'Plain Text (.txt)', icon: 'fa-file-lines', color: '#66bb6a' },
                      ].map(({ format, label, icon, color }) => (
                        <button
                          key={format}
                          onClick={() => { handleDownload(format); setShowDownloadMenu(false); }}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '10px',
                            width: '100%',
                            padding: '10px 14px',
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--text-bright)',
                            cursor: 'pointer',
                            fontSize: '0.85rem',
                            textAlign: 'left',
                            transition: 'background 0.15s',
                          }}
                          onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.07)'}
                          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                        >
                          <i className={`fa-solid ${icon}`} style={{ color, width: '14px' }}></i>
                          {label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div>{content}</div>
        )}
      </div>

      {!isBot && (
        <div className="message-avatar user">
          <i className="fa-solid fa-user"></i>
        </div>
      )}
    </div>
  );
}
