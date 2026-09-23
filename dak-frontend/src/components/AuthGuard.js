'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { supabase } from '../lib/supabase';

export default function AuthGuard({ children }) {
  const router = useRouter();
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    // Safety timeout: Never stay stuck on Verifying Session for more than 2.5 seconds
    const timeoutId = setTimeout(() => {
      if (isMounted && loading && !authenticated) {
        setLoading(false);
        router.replace('/login');
      }
    }, 2500);

    const checkSession = async () => {
      try {
        const { data: { session }, error } = await supabase.auth.getSession();
        if (!isMounted) return;

        if (error || !session) {
          setAuthenticated(false);
          router.replace('/login');
        } else {
          setAuthenticated(true);
        }
      } catch (err) {
        console.warn('Session verification error:', err);
        if (isMounted) {
          setAuthenticated(false);
          router.replace('/login');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
          clearTimeout(timeoutId);
        }
      }
    };

    checkSession();

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!isMounted) return;
      if (!session) {
        setAuthenticated(false);
        router.replace('/login');
      } else {
        setAuthenticated(true);
        setLoading(false);
      }
    });

    return () => {
      isMounted = false;
      clearTimeout(timeoutId);
      subscription?.unsubscribe();
    };
  }, [router]);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--bg-primary)', color: 'var(--text-main)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
          <i className="fa-solid fa-spinner fa-spin" style={{ color: '#c4122f', fontSize: '1.5rem' }}></i>
          <span>Verifying Session...</span>
        </div>
        <button
          onClick={() => router.replace('/login')}
          style={{
            background: 'none',
            border: '1px solid rgba(255,255,255,0.15)',
            color: 'var(--text-muted, #aaa)',
            padding: '6px 14px',
            borderRadius: '6px',
            fontSize: '0.8rem',
            cursor: 'pointer'
          }}
        >
          Go to Sign In →
        </button>
      </div>
    );
  }

  if (!authenticated) {
    return null;
  }

  return children;
}

