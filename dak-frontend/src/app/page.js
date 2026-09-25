'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { supabase } from '../lib/supabase';

export default function RootPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [sessionFound, setSessionFound] = useState(false);

  useEffect(() => {
    let isMounted = true;

    // Safety fallback: if no response within 1.5s, direct to login
    const timer = setTimeout(() => {
      if (isMounted && loading) {
        setLoading(false);
        router.replace('/login');
      }
    }, 1500);

    const checkAuth = async () => {
      try {
        const { data: { session }, error } = await supabase.auth.getSession();
        if (!isMounted) return;

        if (error || !session) {
          setSessionFound(false);
          router.replace('/login');
        } else {
          setSessionFound(true);
          router.replace('/chat');
        }
      } catch (err) {
        console.warn('Auth check error in root page:', err);
        if (isMounted) {
          setSessionFound(false);
          router.replace('/login');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
          clearTimeout(timer);
        }
      }
    };

    checkAuth();

    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [router]);

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: 'var(--bg-primary)',
      color: 'var(--text-main)',
      fontFamily: 'system-ui, sans-serif'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
        <i className="fa-solid fa-spinner fa-spin" style={{ color: '#c4122f', fontSize: '1.6rem' }}></i>
        <span style={{ fontSize: '1.05rem', fontWeight: 500 }}>Loading Dak Sahayak...</span>
      </div>

      <div style={{ display: 'flex', gap: '12px', marginTop: '10px' }}>
        <Link
          href="/login"
          style={{
            backgroundColor: '#c4122f',
            color: '#fff',
            padding: '8px 18px',
            borderRadius: '6px',
            textDecoration: 'none',
            fontSize: '0.85rem',
            fontWeight: 600
          }}
        >
          Sign In
        </Link>
        <Link
          href="/chat"
          style={{
            border: '1px solid rgba(255,255,255,0.2)',
            color: '#e3e3e3',
            padding: '8px 18px',
            borderRadius: '6px',
            textDecoration: 'none',
            fontSize: '0.85rem'
          }}
        >
          Open Chat
        </Link>
      </div>
    </div>
  );
}

