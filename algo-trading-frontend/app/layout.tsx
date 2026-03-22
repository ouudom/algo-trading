'use client';

import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Sidebar from '@/components/layout/Sidebar';
import Header from '@/components/layout/Header';
import './globals.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,        // 30 s
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>AlgoTrader</title>
        <meta name="description" content="Algorithmic trading dashboard" />
        <link rel="icon" href="/favicon.ico" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-gray-950 text-gray-100 antialiased">
        <QueryClientProvider client={queryClient}>
          <div className="flex h-screen overflow-hidden">
            {/* Sidebar */}
            <Sidebar />

            {/* Main content area */}
            <div className="flex flex-col flex-1 overflow-hidden">
              <Header />
              <main
                className="flex-1 overflow-y-auto p-6 bg-gray-950"
                id="main-content"
              >
                {children}
              </main>
            </div>
          </div>
        </QueryClientProvider>
      </body>
    </html>
  );
}
