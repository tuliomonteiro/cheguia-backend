"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useMessages } from "@/lib/i18n";

function sourceLabel(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export default function ChatPage() {
  const { user, accessToken, loading, logout } = useAuth();
  const router = useRouter();
  const t = useMessages(user?.language_preference);

  const [sessions, setSessions] = useState<api.ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<api.Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (!accessToken) return;
    let ignore = false;
    api.listSessions(accessToken).then((list) => {
      if (ignore) return;
      setSessions(list);
      setActiveSessionId((prev) => prev ?? list[0]?.id ?? null);
    });
    return () => {
      ignore = true;
    };
  }, [accessToken]);

  useEffect(() => {
    if (!accessToken || !activeSessionId) return;
    let ignore = false;
    api
      .getSession(accessToken, activeSessionId)
      .then((detail) => {
        if (!ignore) setMessages(detail.messages);
      })
      .catch(() => {
        if (!ignore) setMessages([]);
      });
    return () => {
      ignore = true;
    };
  }, [accessToken, activeSessionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  async function handleNewSession() {
    if (!accessToken) return;
    const session = await api.createSession(accessToken);
    setSessions((prev) => [session, ...prev]);
    setActiveSessionId(session.id);
    setMessages([]);
  }

  async function handleSend(e: FormEvent) {
    e.preventDefault();
    if (!accessToken || !input.trim() || sending) return;

    setError(null);
    setSending(true);
    const content = input.trim();
    setInput("");

    try {
      let sessionId = activeSessionId;
      if (!sessionId) {
        const session = await api.createSession(accessToken);
        setSessions((prev) => [session, ...prev]);
        setActiveSessionId(session.id);
        sessionId = session.id;
      }

      setMessages((prev) => [
        ...prev,
        {
          id: `pending-${Date.now()}`,
          role: "user",
          content,
          sources: [],
          created_at: new Date().toISOString(),
        },
      ]);

      const result = await api.sendMessage(accessToken, sessionId, content);
      setMessages((prev) => [...prev.filter((m) => !m.id.startsWith("pending-")), result.user, result.assistant]);
      api.listSessions(accessToken).then(setSessions);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.sendFailed);
      setMessages((prev) => prev.filter((m) => !m.id.startsWith("pending-")));
    } finally {
      setSending(false);
    }
  }

  async function handleDeleteSession(id: string) {
    if (!accessToken || !window.confirm(t.deleteConfirm)) return;
    try {
      await api.deleteSession(accessToken, id);
    } catch {
      setError(t.deleteFailed);
      return;
    }
    const rest = sessions.filter((s) => s.id !== id);
    setSessions(rest);
    if (activeSessionId === id) {
      setMessages([]);
      setActiveSessionId(rest[0]?.id ?? null);
    }
  }

  if (loading || !user) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">
        {t.loading}
      </div>
    );
  }

  return (
    <div className="flex flex-1 overflow-hidden bg-zinc-50 dark:bg-black">
      <aside className="flex w-64 shrink-0 flex-col border-r border-black/10 bg-white dark:border-white/10 dark:bg-zinc-900">
        <div className="flex items-center justify-between border-b border-black/10 p-4 dark:border-white/10">
          <span className="min-w-0 truncate text-sm font-medium text-zinc-900 dark:text-zinc-50">
            {user.email}
          </span>
          <span className="flex shrink-0 gap-3">
            <Link
              href="/settings"
              className="text-xs font-medium text-zinc-500 underline hover:text-zinc-800 dark:hover:text-zinc-200"
            >
              {t.settings}
            </Link>
            <button
              onClick={logout}
              className="text-xs font-medium text-zinc-500 underline hover:text-zinc-800 dark:hover:text-zinc-200"
            >
              {t.signOut}
            </button>
          </span>
        </div>

        <button
          onClick={handleNewSession}
          className="m-3 rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {t.newChat}
        </button>

        <nav className="flex-1 space-y-1 overflow-y-auto px-2">
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`group flex items-center rounded-md ${
                s.id === activeSessionId
                  ? "bg-zinc-200 dark:bg-zinc-700"
                  : "hover:bg-zinc-100 dark:hover:bg-zinc-800"
              }`}
            >
              <button
                onClick={() => {
                  // Re-selecting the active session must not clear the thread:
                  // the load effect only re-runs when the id actually changes.
                  if (s.id === activeSessionId) return;
                  setMessages([]);
                  setActiveSessionId(s.id);
                }}
                className={`min-w-0 flex-1 truncate px-3 py-2 text-left text-sm ${
                  s.id === activeSessionId
                    ? "text-zinc-900 dark:text-zinc-50"
                    : "text-zinc-600 dark:text-zinc-400"
                }`}
              >
                {s.title || t.untitledChat}
              </button>
              <button
                onClick={() => handleDeleteSession(s.id)}
                title={t.deleteChat}
                aria-label={t.deleteChat}
                className="hidden shrink-0 px-2 py-2 text-xs text-zinc-400 hover:text-red-600 group-hover:block dark:hover:text-red-400"
              >
                ✕
              </button>
            </div>
          ))}
        </nav>
      </aside>

      <section className="flex flex-1 flex-col">
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6">
          {messages.length === 0 && (
            <p className="text-center text-sm text-zinc-500">{t.emptyPrompt}</p>
          )}
          <div className="mx-auto flex max-w-2xl flex-col gap-4">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                  m.role === "user"
                    ? "self-end whitespace-pre-wrap bg-zinc-900 text-white dark:bg-zinc-50 dark:text-zinc-900"
                    : "self-start bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-50"
                }`}
              >
                {m.role === "assistant" ? (
                  <div className="prose prose-sm max-w-none dark:prose-invert">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        a: (props) => (
                          <a {...props} target="_blank" rel="noopener noreferrer" />
                        ),
                      }}
                    >
                      {m.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  m.content
                )}
                {m.sources.length > 0 && (
                  <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs opacity-80">
                    <span>{t.sources}</span>
                    {[...new Set(m.sources)].map((url) => (
                      <a
                        key={url}
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="underline hover:opacity-70"
                      >
                        {sourceLabel(url)}
                      </a>
                    ))}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>

        {error && (
          <p className="px-6 pb-2 text-center text-sm text-red-600 dark:text-red-400">
            {error}
          </p>
        )}

        <form
          onSubmit={handleSend}
          className="flex gap-2 border-t border-black/10 p-4 dark:border-white/10"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t.inputPlaceholder}
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-50"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            {sending ? t.sending : t.send}
          </button>
        </form>
      </section>
    </div>
  );
}
