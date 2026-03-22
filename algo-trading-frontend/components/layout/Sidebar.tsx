'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

// Inline SVG icons — no external icon library dependency
const IconDashboard = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.75}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <rect x="3" y="3" width="7" height="7" rx="1" />
    <rect x="14" y="3" width="7" height="7" rx="1" />
    <rect x="3" y="14" width="7" height="7" rx="1" />
    <rect x="14" y="14" width="7" height="7" rx="1" />
  </svg>
);

const IconBacktest = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.75}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </svg>
);

const IconTrades = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.75}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
    <polyline points="10 9 9 9 8 9" />
  </svg>
);

const IconAnalytics = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.75}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);

const IconLive = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    className="h-5 w-5"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.75}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <circle cx="12" cy="12" r="3" />
    <path d="M5.64 5.64a9 9 0 0 0 0 12.73" />
    <path d="M18.36 5.64a9 9 0 0 1 0 12.73" />
    <path d="M8.46 8.46a5 5 0 0 0 0 7.07" />
    <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
  </svg>
);

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', href: '/', icon: <IconDashboard /> },
  { label: 'Backtests', href: '/backtests', icon: <IconBacktest /> },
  { label: 'Trades', href: '/trades', icon: <IconTrades /> },
  { label: 'Analytics', href: '/analytics', icon: <IconAnalytics /> },
  { label: 'Live Trading', href: '/live', icon: <IconLive /> },
];

export default function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string): boolean => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <aside
      className="flex flex-col w-60 shrink-0 bg-gray-900 border-r border-gray-800 h-full"
      aria-label="Main navigation"
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 h-[60px] border-b border-gray-800 shrink-0">
        <div className="flex items-center justify-center w-8 h-8 rounded-md bg-blue-600 text-white font-bold text-sm select-none">
          AT
        </div>
        <span className="text-gray-100 font-semibold text-base tracking-tight">
          AlgoTrader
        </span>
      </div>

      {/* Nav links */}
      <nav className="flex-1 px-3 py-4 space-y-0.5" aria-label="Sidebar navigation">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors duration-150 group',
                active
                  ? 'bg-blue-600/15 text-blue-400 border border-blue-500/20'
                  : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800 border border-transparent'
              )}
            >
              <span
                className={cn(
                  'transition-colors duration-150',
                  active ? 'text-blue-400' : 'text-gray-500 group-hover:text-gray-300'
                )}
              >
                {item.icon}
              </span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-gray-800">
        <p className="text-xs text-gray-600 leading-relaxed">
          AlgoTrader v0.1.0
        </p>
      </div>
    </aside>
  );
}
