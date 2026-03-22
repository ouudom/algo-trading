import React from 'react';
import { cn } from '@/lib/utils';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /** Optional right-side slot for buttons / filters */
  actions?: React.ReactNode;
  className?: string;
}

export default function PageHeader({
  title,
  subtitle,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        'flex items-start justify-between gap-4 mb-6',
        className
      )}
    >
      <div>
        <h1 className="text-xl font-bold text-gray-100 leading-tight">{title}</h1>
        {subtitle && (
          <p className="mt-1 text-sm text-gray-500 leading-snug">{subtitle}</p>
        )}
      </div>

      {actions && (
        <div className="flex items-center gap-2 shrink-0">{actions}</div>
      )}
    </div>
  );
}
