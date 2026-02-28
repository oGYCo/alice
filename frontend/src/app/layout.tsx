import type { Metadata } from 'next';
import { Inter, Source_Serif_4 } from 'next/font/google';
import './globals.css';
import { ConditionalSidebar } from '@/components/layout/ConditionalSidebar';
import { AuthGuard } from '@/components/layout/AuthGuard';
import { Toaster } from '@/components/ui/sonner';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
});

const sourceSerif = Source_Serif_4({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-source-serif',
});

export const metadata: Metadata = {
  title: 'Alice — AI Secretary',
  description: 'Intelligent personal information manager',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${sourceSerif.variable} font-sans h-screen flex bg-background text-foreground antialiased`}>
        <ConditionalSidebar />
        <main className="flex-1 overflow-auto pl-4 pr-4">
          <AuthGuard>
            {children}
          </AuthGuard>
        </main>
        <Toaster />
      </body>
    </html>
  );
}
