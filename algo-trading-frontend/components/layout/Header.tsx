'use client';

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import type { TradingMode } from '@/types';

interface ModeBadgeProps {
  mode: TradingMode;
  onToggle: () => void;
}

function ModeBadge({ mode, onToggle }: ModeBadgeProps) {
  const isLive = mode === 'LIVE';
  return (
    <button
      type="button"
      onClick={onToggle}
      className={cn(
        'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold',
        'border transition-colors duration-200 cursor-pointer',
        isLive
          ? 'bg-red-500/10 text-red-400 border-red-500/25 hover:bg-red-500/20'
          : 'bg-blue-500/10 text-blue-400 border-blue-500/25 hover:bg-blue-500/20'
      )}
      aria-label={`Trading mode: ${mode}. Click to toggle.`}
    >
      {/* Animated dot */}
      <span
        className={cn(
          'inline-block w-1.5 h-1.5 rounded-full',
          isLive ? 'bg-red-400 animate-pulse' : 'bg-blue-400'
        )}
        aria-hidden="true"
      />
      {mode}
    </button>
  );
}

export default function Header() {
  const [mode, setMode] = useState<TradingMode>('PAPER');

  const handleToggle = () => {
    setMode((prev) => (prev === 'LIVE' ? 'PAPER' : 'LIVE'));
  };

  return (
    <header
      className="flex items-center justify-between px-6 h-[60px] bg-gray-900 border-b border-gray-800 shrink-0"
      role="banner"
    >
      {/* Left: breadcrumb slot (populated by page) */}
      <div className="flex items-center gap-2" id="header-breadcrumb">
        <span className="text-sm text-gray-500 font-medium">AlgoTrader Dashboard</span>
      </div>

      {/* Right: controls */}
      <div className="flex items-center gap-4">
        {/* Connection indicator */}
        <div className="flex items-center gap-1.5" aria-label="API connection status">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" aria-hidden="true" />
          <span className="text-xs text-gray-500">Connected</span>
        </div>

        {/* Mode badge */}
        <ModeBadge mode={mode} onToggle={handleToggle} />
      </div>
    </header>
  );
}
