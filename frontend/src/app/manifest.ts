import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Coach Tommy',
    short_name: 'Coach Tommy',
    start_url: '/',
    display: 'standalone',
    background_color: '#ffffff',
    theme_color: '#ffffff',
    icons: [{ src: '/logo-coachtommy.jpg', sizes: 'any', type: 'image/jpeg' }],
  };
}