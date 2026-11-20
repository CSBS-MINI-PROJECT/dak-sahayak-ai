import Script from 'next/script';
import '../styles/globals.css';

export const viewport = {
  themeColor: '#d32f2f',
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover'
};

export const metadata = {
  title: 'Dak Sahayak (डाक सहायक) - Official India Post AI Assistant',
  description: 'AI-powered official assistant for India Post postal services, small savings schemes, speed post tariffs, and PIN lookup.',
  manifest: '/manifest.webmanifest',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'Dak Sahayak'
  },
  icons: {
    icon: [
      { url: '/icon-192x192.png', sizes: '192x192', type: 'image/png' },
      { url: '/icon-512x512.png', sizes: '512x512', type: 'image/png' }
    ],
    apple: [
      { url: '/icon-192x192.png', sizes: '192x192', type: 'image/png' }
    ]
  }
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Noto+Sans+Devanagari:wght@400;600;700&display=swap" rel="stylesheet" />
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var saved = localStorage.getItem('dak_theme');
                  var theme = saved || 'dark';
                  document.documentElement.setAttribute('data-theme', theme);
                } catch (e) {}
              })();
            `
          }}
        />
      </head>
      <body>
        {children}
        <Script
          id="pwa-service-worker-register"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              if ('serviceWorker' in navigator) {
                window.addEventListener('load', function() {
                  navigator.serviceWorker.register('/sw.js').then(
                    function(registration) {
                      console.log('[PWA] ServiceWorker registration successful with scope:', registration.scope);
                    },
                    function(err) {
                      console.warn('[PWA] ServiceWorker registration failed:', err);
                    }
                  );
                });
              }
            `
          }}
        />
      </body>
    </html>
  );
}
