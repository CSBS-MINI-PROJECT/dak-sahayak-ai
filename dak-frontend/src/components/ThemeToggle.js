'use client';

import { useState, useEffect } from 'react';

export default function ThemeToggle() {
  const [theme, setTheme] = useState('dark');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    // Read from existing attribute or localStorage
    const currentTheme =
      document.documentElement.getAttribute('data-theme') ||
      localStorage.getItem('dak_theme') ||
      'dark';
    setTheme(currentTheme);
    document.documentElement.setAttribute('data-theme', currentTheme);

    const handleThemeChange = (e) => {
      if (e.detail && (e.detail === 'light' || e.detail === 'dark')) {
        setTheme(e.detail);
      }
    };

    window.addEventListener('dak_theme_changed', handleThemeChange);
    return () => window.removeEventListener('dak_theme_changed', handleThemeChange);
  }, []);

  const setThemeMode = (newTheme) => {
    setTheme(newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
    try {
      localStorage.setItem('dak_theme', newTheme);
      window.dispatchEvent(new CustomEvent('dak_theme_changed', { detail: newTheme }));
    } catch (err) {
      console.warn('Could not save theme preference:', err);
    }
  };

  if (!mounted) {
    return (
      <div className="theme-toggle-container skeleton" aria-hidden="true">
        <div className="theme-toggle-btn active">
          <i className="fa-solid fa-moon theme-icon moon"></i>
          <span className="theme-text">Dark</span>
        </div>
      </div>
    );
  }

  return (
    <div className="theme-toggle-container" role="radiogroup" aria-label="Color theme selection">
      <button
        type="button"
        className={`theme-toggle-btn ${theme === 'light' ? 'active' : ''}`}
        onClick={() => setThemeMode('light')}
        title="Switch to Light mode"
        aria-checked={theme === 'light'}
        role="radio"
      >
        <i className="fa-solid fa-sun theme-icon sun"></i>
        <span className="theme-text">Light</span>
      </button>

      <button
        type="button"
        className={`theme-toggle-btn ${theme === 'dark' ? 'active' : ''}`}
        onClick={() => setThemeMode('dark')}
        title="Switch to Dark mode"
        aria-checked={theme === 'dark'}
        role="radio"
      >
        <i className="fa-solid fa-moon theme-icon moon"></i>
        <span className="theme-text">Dark</span>
      </button>
    </div>
  );
}
