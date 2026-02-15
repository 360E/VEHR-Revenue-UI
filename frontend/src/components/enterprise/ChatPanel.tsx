"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";

import { ApiError, apiFetch, buildUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ThreadSummary = {
  id: string;
  title?: string | null;
  created_at: string;
  updated_at: string;
  last_message_at?: string | null;
  last_message_preview?: string | null;
};

type ChatMessage = {
  id: string;
  thread_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

type ToolCall = {
  tool_id: string;
  status: string;
  result?: Record<string, unknown> | null;
  error?: string | null;
};

type ChatContext = {
  path: string;
  module: string;
  patient_id?: string | null;
  entity_type?: string | null;
  entity_id?: string | null;
  quick_action?: string | null;
};

type ChatResponse = {
  thread: ThreadSummary;
  assistant_message: ChatMessage;
  reply: string;
  tool_calls?: ToolCall[];
  warnings?: string[];
  fallback?: boolean;
};

const STORAGE_THREAD_KEY = "vehr_enterprise_assistant_thread";

function deriveContext(pathname: string | null): ChatContext {
  const safePath = pathname && pathname.startsWith("/") ? pathname : "/";
  const parts = safePath.split("/").filter(Boolean);
  return {
    path: safePath,
    module: parts[0] ?? "dashboard",
  };
}

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

function formatClock(value: string): string {
  const stamp = new Date(value);
  if (Number.isNaN(stamp.getTime())) return "";
  return stamp.toLocaleTimeString();
}

type ChatPanelProps = {
  isOpen: boolean;
  agentId: string;
  className?: string;
};

export function ChatPanel({ isOpen, agentId, className }: ChatPanelProps) {
  const pathname = usePathname();
  const context = useMemo(() => deriveContext(pathname), [pathname]);

  const [threadId, setThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [isLoadingThread, setIsLoadingThread] = useState(false);

  const seenNotificationIdsRef = useRef<Set<string>>(new Set());
  const historyRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!historyRef.current) return;
    historyRef.current.scrollTop = historyRef.current.scrollHeight;
  }, [messages]);

  useEffect(() => {
    if (!isOpen) return;
    let mounted = true;

    async function loadThread() {
      setIsLoadingThread(true);
      setError(null);
      try {
        const threads = await apiFetch<ThreadSummary[]>("/api/v1/ai/threads?limit=20", {
          cache: "no-store",
        });

        const stored = (() => {
          try {
            return window.localStorage.getItem(STORAGE_THREAD_KEY);
          } catch {
            return null;
          }
        })();

        const nextThreadId = stored && threads.some((item) => item.id === stored)
          ? stored
          : threads[0]?.id ?? null;

        if (!mounted) return;
        setThreadId(nextThreadId);
      } catch (loadError) {
        if (!mounted) return;
        setError(toErrorMessage(loadError, "Unable to load assistant threads."));
        setThreadId(null);
      } finally {
        if (mounted) setIsLoadingThread(false);
      }
    }

    void loadThread();
    return () => {
      mounted = false;
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    if (!threadId) {
      setMessages([]);
      return;
    }
    const activeThreadId = threadId;

    let mounted = true;
    async function loadMessages() {
      setError(null);
      try {
        const rows = await apiFetch<ChatMessage[]>(`/api/v1/ai/threads/${encodeURIComponent(activeThreadId)}/messages?limit=200`, {
          cache: "no-store",
        });
        if (!mounted) return;
        setMessages(rows);
        try {
          window.localStorage.setItem(STORAGE_THREAD_KEY, activeThreadId);
        } catch {
          // ignore storage failures
        }
      } catch (loadError) {
        if (!mounted) return;
        setError(toErrorMessage(loadError, "Unable to load assistant messages."));
      }
    }

    void loadMessages();
    return () => {
      mounted = false;
    };
  }, [isOpen, threadId]);

  useEffect(() => {
    if (!isOpen) return;
    const streamUrl = buildUrl("/api/v1/ai/notifications/stream");
    const source = new EventSource(streamUrl, { withCredentials: true });

    source.addEventListener("notification", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as {
        id: string;
        type?: string | null;
        title?: string | null;
        body?: string | null;
        created_at?: string | null;
      };

      if (!payload?.id) return;
      if (seenNotificationIdsRef.current.has(payload.id)) return;
      seenNotificationIdsRef.current.add(payload.id);

      // If the backend persisted an in-thread assistant message for this notification,
      // refresh the thread to avoid duplicates and keep history consistent.
      const activeThreadId = threadId;
      if (activeThreadId) {
        void apiFetch<ChatMessage[]>(`/api/v1/ai/threads/${encodeURIComponent(activeThreadId)}/messages?limit=200`, {
          cache: "no-store",
        })
          .then((rows) => setMessages(rows))
          .catch(() => {
            // Fall back to rendering a local message if refresh fails.
            const kind = payload.type === "reminder" ? "Reminder" : "Notification";
            const title = payload.title?.trim() || kind;
            const body = payload.body?.trim() || "";
            const content = body ? `${kind}: ${title}\n${body}` : `${kind}: ${title}`;
            setMessages((current) => [
              ...current,
              {
                id: `notification-${payload.id}`,
                thread_id: activeThreadId,
                role: "assistant",
                content,
                created_at: payload.created_at || new Date().toISOString(),
              },
            ]);
          });
        return;
      }

      const kind = payload.type === "reminder" ? "Reminder" : "Notification";
      const title = payload.title?.trim() || kind;
      const body = payload.body?.trim() || "";
      const content = body ? `${kind}: ${title}\n${body}` : `${kind}: ${title}`;

      setMessages((current) => [
        ...current,
        {
          id: `notification-${payload.id}`,
          thread_id: "unthreaded",
          role: "assistant",
          content,
          created_at: payload.created_at || new Date().toISOString(),
        },
      ]);
    });

    source.onerror = () => {
      // EventSource will auto-retry; keep UI quiet to avoid noisy loops.
    };

    return () => {
      source.close();
    };
  }, [isOpen, threadId]);

  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isSending) return;

    setError(null);
    setWarnings([]);
    setIsSending(true);
    setDraft("");

    const optimisticId = `user-${Date.now()}`;
    const optimisticThreadId = threadId ?? "pending";

    setMessages((current) => [
      ...current,
      {
        id: optimisticId,
        thread_id: optimisticThreadId,
        role: "user",
        content: message,
        created_at: new Date().toISOString(),
      },
    ]);

    try {
      const response = await apiFetch<ChatResponse>("/api/v1/ai/chat", {
        method: "POST",
        body: JSON.stringify({
          agent_id: agentId,
          thread_id: threadId,
          message,
          context,
        }),
      });

      const resolvedThreadId = response.thread?.id ?? threadId;
      if (resolvedThreadId && resolvedThreadId !== threadId) {
        setThreadId(resolvedThreadId);
        try {
          window.localStorage.setItem(STORAGE_THREAD_KEY, resolvedThreadId);
        } catch {
          // ignore storage failures
        }
      }

      setWarnings(Array.isArray(response.warnings) ? response.warnings : []);

      setMessages((current) => [
        ...current,
        {
          id: response.assistant_message.id,
          thread_id: response.assistant_message.thread_id,
          role: "assistant",
          content: response.reply ?? response.assistant_message.content,
          created_at: response.assistant_message.created_at,
        },
      ]);
    } catch (sendError) {
      setError(toErrorMessage(sendError, "Assistant request failed."));
    } finally {
      setIsSending(false);
    }
  }

  return (
    <section className={cn("flex min-h-0 flex-1 flex-col", className)}>
      <div className="border-b border-[color-mix(in_srgb,var(--neutral-border)_70%,white)] px-[var(--space-16)] py-[var(--space-12)]">
        <div className="flex flex-wrap items-center justify-between gap-[var(--space-12)]">
          <p className="ui-type-section-title text-[var(--neutral-text)]">
            Conversation
          </p>
          <div className="text-xs text-[var(--neutral-muted)]">
            {isLoadingThread ? "Loading..." : threadId ? "Ready" : "New thread"}
          </div>
        </div>
        {warnings.length ? (
          <div className="mt-[var(--space-8)] rounded-[var(--radius-10)] border border-[color-mix(in_srgb,var(--status-warning)_35%,white)] bg-[color-mix(in_srgb,var(--status-warning)_10%,white)] px-[var(--space-12)] py-[var(--space-8)] text-xs text-[color-mix(in_srgb,var(--status-warning)_90%,black)]">
            {warnings.join("; ")}
          </div>
        ) : null}
      </div>

      <div ref={historyRef} className="min-h-0 flex-1 space-y-[var(--space-12)] overflow-y-auto px-[var(--space-16)] py-[var(--space-16)]">
        {!messages.length ? (
          <div className="text-sm text-[var(--neutral-muted)]">
            Ask for drafts, checklists, compliance-safe guidance, or reminders.
          </div>
        ) : null}
        {messages.map((item) => (
          <div
            key={item.id}
            className={cn(
              "max-w-[92%] rounded-[var(--radius-12)] px-[var(--space-12)] py-[var(--space-10)] text-sm shadow-sm",
              item.role === "assistant"
                ? "mr-auto border border-[var(--neutral-border)] bg-[var(--neutral-panel)] text-[var(--neutral-text)]"
                : "ml-auto bg-[var(--brand-primary)] text-[var(--brand-primary-foreground)]",
            )}
          >
            <div className="whitespace-pre-wrap break-words leading-relaxed">
              {item.content}
            </div>
            <div className={cn("mt-1 text-[10px] opacity-75", item.role === "assistant" ? "text-[var(--neutral-muted)]" : "")}>
              {formatClock(item.created_at)}
            </div>
          </div>
        ))}
      </div>

      <footer className="border-t border-[color-mix(in_srgb,var(--neutral-border)_70%,white)] px-[var(--space-16)] py-[var(--space-12)]">
        {error ? (
          <div className="mb-[var(--space-8)] rounded-[var(--radius-10)] border border-[color-mix(in_srgb,var(--danger)_35%,white)] bg-[color-mix(in_srgb,var(--danger)_10%,white)] px-[var(--space-12)] py-[var(--space-8)] text-xs text-[var(--danger)]">
            {error}
          </div>
        ) : null}
        <form onSubmit={handleSend} className="flex items-end gap-[var(--space-12)]">
          <textarea
            data-testid="assistant-input"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Message the assistant..."
            rows={2}
            className="min-h-[72px] flex-1 resize-y rounded-[var(--radius-10)] border border-[var(--neutral-border)] bg-[var(--surface)] px-[var(--space-12)] py-[var(--space-10)] text-sm text-[var(--neutral-text)] shadow-sm outline-none transition focus:border-[color-mix(in_srgb,var(--brand-primary)_45%,var(--neutral-border))] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--brand-primary)_25%,transparent)]"
          />
          <Button
            data-testid="assistant-send"
            type="submit"
            disabled={isSending || !draft.trim()}
            className="h-10"
          >
            {isSending ? "Sending..." : "Send"}
          </Button>
        </form>
      </footer>
    </section>
  );
}
