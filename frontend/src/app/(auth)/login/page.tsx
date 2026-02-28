'use client';

import { Suspense, useEffect, useState } from 'react';
import { useAuthStore } from '@/lib/store';
import { useRouter, useSearchParams } from 'next/navigation';

async function verifyApiKey(key: string): Promise<{ ok: boolean; error?: string }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 6000);
  try {
    const res = await fetch('/api/v1/content?limit=1', {
      headers: { 'X-API-Key': key },
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (res.status === 401) return { ok: false, error: 'API Key 不正确，请重新检查。' };
    if (!res.ok) return { ok: false, error: `服务器返回错误 ${res.status}，请稍后重试。` };
    return { ok: true };
  } catch (e) {
    clearTimeout(timer);
    if (e instanceof Error && e.name === 'AbortError')
      return { ok: false, error: '连接超时，请确认后端服务已启动（端口 8000）。' };
    return { ok: false, error: '无法连接到服务器，请确认后端服务已启动。' };
  }
}

function LoginPageInner() {
  const [key, setKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [show, setShow] = useState(false);
  // 'checking' = silently verifying stored key; 'ready' = show form
  const [phase, setPhase] = useState<'checking' | 'ready'>('checking');
  const { setApiKey, logout } = useAuthStore();
  const router = useRouter();
  const searchParams = useSearchParams();

  // On mount: if a key is stored in localStorage, silently verify it.
  // If valid → re-set cookie and redirect (seamless re-login on refresh).
  // If invalid → clear stale session and show form.
  useEffect(() => {
    const stored = useAuthStore.getState().apiKey;
    if (!stored) {
      setPhase('ready');
      return;
    }
    verifyApiKey(stored).then((result) => {
      if (result.ok) {
        setApiKey(stored); // writes cookie
        router.replace(searchParams.get('from') ?? '/feed');
      } else {
        logout(); // clear stale key + cookie
        setPhase('ready');
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = key.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);

    const result = await verifyApiKey(trimmed);
    if (result.ok) {
      setApiKey(trimmed); // writes cookie only after verified
      router.replace(searchParams.get('from') ?? '/feed');
    } else {
      setError(result.error ?? 'API Key 无效，请检查后重试。');
      setLoading(false);
    }
  };

  // Show a minimal spinner while checking stored key
  if (phase === 'checking') {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <svg className="animate-spin" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
          <span className="text-sm">正在验证…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      <div className="w-full max-w-sm">
        {/* Logo / title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-primary/10 mb-4">
            <span className="text-2xl">✦</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Alice</h1>
          <p className="text-sm text-muted-foreground mt-1">AI 个人信息助手</p>
        </div>

        <div className="bg-card border border-border rounded-xl p-8 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="apikey" className="text-sm font-medium">
                API Key
              </label>
              <div className="relative mt-1">
                <input
                  id="apikey"
                  data-testid="api-key-input"
                  type={show ? 'text' : 'password'}
                  value={key}
                  onChange={(e) => { setKey(e.target.value); setError(null); }}
                  placeholder="alice-..."
                  autoComplete="current-password"
                  disabled={loading}
                  className="w-full px-3 py-2 pr-10 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
                />
                <button
                  type="button"
                  onClick={() => setShow((v) => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                  aria-label={show ? '隐藏' : '显示'}
                >
                  {show ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  )}
                </button>
              </div>
            </div>

            {error && (
              <p className="text-sm text-destructive bg-destructive/5 border border-destructive/20 rounded-md px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              data-testid="login-button"
              disabled={loading || !key.trim()}
              className="w-full px-4 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                  验证中…
                </>
              ) : '连接'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-muted-foreground/50 mt-6">
          API Key 可在 Alice 后端服务配置中找到
        </p>
      </div>
    </div>
  );
}

function LoginFallback() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        <svg className="animate-spin" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
        <span className="text-sm">正在加载…</span>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginPageInner />
    </Suspense>
  );
}
