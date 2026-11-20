export default function manifest() {
  return {
    name: 'Dak Sahayak AI — India Post Assistant',
    short_name: 'Dak Sahayak',
    description: 'AI-powered official assistant for India Post postal services, small savings schemes, speed post tariffs, and PIN lookup.',
    start_url: '/chat',
    display: 'standalone',
    background_color: '#121212',
    theme_color: '#d32f2f',
    orientation: 'portrait',
    icons: [
      {
        src: '/icon-192x192.png',
        sizes: '192x192',
        type: 'image/png',
        purpose: 'any maskable'
      },
      {
        src: '/icon-512x512.png',
        sizes: '512x512',
        type: 'image/png',
        purpose: 'any maskable'
      }
    ]
  };
}

