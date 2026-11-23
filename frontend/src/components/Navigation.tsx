'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { getAuthToken, getAuthUser } from '@/lib/api';

export default function Navigation({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [role, setRole] = useState<string | null>(null);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    setAuthenticated(Boolean(getAuthToken()));
    setRole(getAuthUser()?.role || null);
    setOpen(false);
  }, [pathname]);

  if (!authenticated || pathname === '/login' || pathname === '/register') return <>{children}</>;
  const links = [
    { href: '/', label: 'Calendrier' },
    { href: '/profile', label: 'Profil' },
    { href: '/plans', label: 'Plan' },
    { href: '/community', label: 'Communauté' },
    ...(role === 'coach' ? [{ href: '/coach', label: 'Coach' }] : []),
  ];
  return (
    <div className="md:flex min-h-screen">
      <div className="md:hidden bg-brand-dark p-4">
        <button type="button" className="text-white font-bold" aria-expanded={open} aria-controls="main-navigation" onClick={() => setOpen(!open)}>
          {open ? 'Fermer le menu' : 'Ouvrir le menu'}
        </button>
      </div>
      <nav id="main-navigation" aria-label="Navigation principale" className={`${open ? 'block' : 'hidden'} md:block bg-brand-dark text-white p-5 md:w-56 shrink-0`}>
        <div className="font-black text-xl mb-6">Coach Tommy</div>
        <ul className="space-y-2">
          {links.map(link => <li key={link.href}><Link href={link.href} aria-current={pathname === link.href ? 'page' : undefined} className="block rounded-xl px-4 py-3 hover:bg-white/10 focus:bg-white/10">{link.label}</Link></li>)}
        </ul>
      </nav>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}