"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { Brain, X } from "lucide-react";

import { ApiError, apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { AgentOption, AgentSelector } from "@/components/enterprise/AgentSelector";
import { ChatPanel } from "@/components/enterprise/ChatPanel";

type MemoryItem = {
  id: string;
  key: string;
  value: string;
  tags: string[];
  source?: string | null;
  updated_at: string;
};

const STORAGE_OPEN_KEY = "vehr_enterprise_assistant_open";
const STORAGE_TAB_KEY = "vehr_enterprise_assistant_tab";

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

export default function EnterpriseAssistantDock() {
  const pathname = usePathname();
  const contextTitle = useMemo(() => {
    const safePath = pathname && pathname.startsWith("/") ? pathname : "/";
    const parts = safePath.split("/").filter(Boolean);
    const moduleKey = parts[0] ?? "workspace";
    return moduleKey.replace(/[-_]/g, " ").replace(/\b\w/g, (ch) => ch.toUpperCase());
  }, [pathname]);

  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "memory">("chat");

  const [agents, setAgents] = useState<AgentOption[]>([
    { agent_id: "enterprise_copilot", display_name: "Enterprise Copilot" },
  ]);
  const [agentId, setAgentId] = useState("enterprise_copilot");
  const [agentError, setAgentError] = useState<string | null>(null);

  const [memoryItems, setMemoryItems] = useState<MemoryItem[]>([]);
  const [memoryKey, setMemoryKey] = useState("");
  const [memoryValue, setMemoryValue] = useState("");
  const [memoryError, setMemoryError] = useState<string | null>(null);
  const [isMemoryLoading, setIsMemoryLoading] = useState(false);
  const [isMemorySaving, setIsMemorySaving] = useState(false);

  useEffect(() => {
    try {
      const rawOpen = window.localStorage.getItem(STORAGE_OPEN_KEY);
      if (rawOpen === "1") setIsOpen(true);
      const rawTab = window.localStorage.getItem(STORAGE_TAB_KEY);
      if (rawTab === "chat" || rawTab === "memory") {
        setActiveTab(rawTab);
      }
    } catch {
      // ignore storage failures
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_OPEN_KEY, isOpen ? "1" : "0");
    } catch {
      // ignore storage failures
    }
  }, [isOpen]);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_TAB_KEY, activeTab);
    } catch {
      // ignore storage failures
    }
  }, [activeTab]);

  useEffect(() => {
    if (!isOpen) return;
    let mounted = true;
    setAgentError(null);

    async function loadAgents() {
      try {
        const response = await apiFetch<AgentOption[]>("/api/v1/ai/agents", { cache: "no-store" });
        if (!mounted) return;
        if (Array.isArray(response) && response.length) {
          setAgents(response);
          if (!response.some((item) => item.agent_id === agentId)) {
            setAgentId(response[0]?.agent_id ?? "enterprise_copilot");
          }
        }
      } catch (error) {
        if (!mounted) return;
        setAgentError(toErrorMessage(error, "Unable to load agents."));
      }
    }

    void loadAgents();
    return () => {
      mounted = false;
    };
  }, [agentId, isOpen]);

  async function refreshMemory() {
    setMemoryError(null);
    setIsMemoryLoading(true);
    try {
      const response = await apiFetch<MemoryItem[]>("/api/v1/ai/memory?limit=200", { cache: "no-store" });
      setMemoryItems(Array.isArray(response) ? response : []);
    } catch (error) {
      setMemoryError(toErrorMessage(error, "Unable to load memory."));
    } finally {
      setIsMemoryLoading(false);
    }
  }

  useEffect(() => {
    if (!isOpen) return;
    if (activeTab !== "memory") return;
    void refreshMemory();
  }, [activeTab, isOpen]);

  async function handleSaveMemory() {
    const key = memoryKey.trim();
    const value = memoryValue.trim();
    if (!key || !value || isMemorySaving) return;

    setIsMemorySaving(true);
    setMemoryError(null);
    try {
      await apiFetch<MemoryItem>("/api/v1/ai/memory", {
        method: "POST",
        body: JSON.stringify({
          key,
          value,
          tags: ["preference"],
          source: "user",
        }),
      });
      setMemoryKey("");
      setMemoryValue("");
      await refreshMemory();
    } catch (error) {
      setMemoryError(toErrorMessage(error, "Unable to save memory."));
    } finally {
      setIsMemorySaving(false);
    }
  }

  async function handleDeleteMemory(id: string) {
    if (!id) return;
    setMemoryError(null);
    try {
      await apiFetch<{ ok: boolean }>(`/api/v1/ai/memory?id=${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
      setMemoryItems((current) => current.filter((item) => item.id !== id));
    } catch (error) {
      setMemoryError(toErrorMessage(error, "Unable to delete memory item."));
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label={isOpen ? "Close Enterprise Assistant" : "Open Enterprise Assistant"}
        data-testid="copilot-trigger"
        className={cn(
          "fixed bottom-6 right-6 z-[2147483000] inline-flex h-14 min-w-[56px] items-center justify-center gap-2 rounded-full px-4 shadow-[var(--shadow-lg)] transition-all",
          "bg-[var(--brand-primary)] text-[var(--brand-primary-foreground)] hover:scale-[1.03]",
          isOpen ? "pointer-events-none opacity-0" : "opacity-100",
        )}
      >
        <Brain className="h-5 w-5" />
        <span className="text-xs font-semibold">Assistant</span>
      </button>

      <aside
        data-testid="enterprise-assistant"
        className={cn(
          "fixed right-4 top-4 z-[2147482999] flex h-[calc(100vh-2rem)] w-[min(96vw,860px)] flex-col overflow-hidden rounded-[var(--radius-16)] border border-[var(--neutral-border)] bg-[var(--surface)] shadow-[var(--shadow-lg)] transition-transform duration-300",
          isOpen ? "translate-x-0" : "translate-x-[110%]",
        )}
        aria-hidden={!isOpen}
      >
        <header className="border-b border-[color-mix(in_srgb,var(--neutral-border)_70%,white)] px-[var(--space-16)] py-[var(--space-14)]">
          <div className="flex items-start justify-between gap-[var(--space-16)]">
            <div className="min-w-0">
              <div className="ui-type-caption text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--neutral-muted)]">
                Enterprise Assistant
              </div>
              <div className="mt-1 text-sm text-[var(--neutral-text)]">
                Context: {contextTitle}
              </div>
              {agentError ? (
                <div className="mt-[var(--space-8)] text-xs text-[var(--danger)]">{agentError}</div>
              ) : null}
            </div>
            <Button type="button" variant="outline" size="sm" onClick={() => setIsOpen(false)}>
              <X className="h-4 w-4" />
              <span className="sr-only">Close</span>
            </Button>
          </div>

          <div className="mt-[var(--space-12)] flex flex-col gap-[var(--space-12)] md:flex-row md:items-end md:justify-between">
            <AgentSelector
              agents={agents}
              value={agentId}
              onChange={setAgentId}
              disabled={!isOpen}
              className="md:max-w-[320px]"
            />
          </div>
        </header>

        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as "chat" | "memory")} className="flex min-h-0 flex-1 flex-col">
          <div className="border-b border-[color-mix(in_srgb,var(--neutral-border)_70%,white)] px-[var(--space-16)] py-[var(--space-10)]">
            <TabsList className="w-full justify-start bg-transparent p-0">
              <TabsTrigger value="chat" className="data-[state=active]:bg-[color-mix(in_srgb,var(--brand-primary)_12%,transparent)]">
                Chat
              </TabsTrigger>
              <TabsTrigger value="memory" className="data-[state=active]:bg-[color-mix(in_srgb,var(--brand-primary)_12%,transparent)]">
                Memory
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="chat" className="min-h-0 flex-1 p-0">
            <ChatPanel isOpen={isOpen} agentId={agentId} />
          </TabsContent>

          <TabsContent value="memory" className="min-h-0 flex-1 overflow-auto px-[var(--space-16)] py-[var(--space-16)]">
            {memoryError ? (
              <div className="mb-[var(--space-12)] rounded-[var(--radius-10)] border border-[color-mix(in_srgb,var(--danger)_35%,white)] bg-[color-mix(in_srgb,var(--danger)_10%,white)] px-[var(--space-12)] py-[var(--space-10)] text-xs text-[var(--danger)]">
                {memoryError}
              </div>
            ) : null}

            <div className="ui-panel border border-[var(--neutral-border)] bg-[var(--neutral-panel)] p-[var(--space-16)]">
              <div className="flex flex-wrap items-center justify-between gap-[var(--space-12)]">
                <div>
                  <p className="ui-type-section-title text-[var(--neutral-text)]">Personal Memory</p>
                  <p className="ui-type-body text-[var(--neutral-muted)]">
                    Stored preferences and open loops (PHI is blocked by default).
                  </p>
                </div>
                <Button type="button" variant="outline" size="sm" onClick={() => void refreshMemory()} disabled={isMemoryLoading}>
                  {isMemoryLoading ? "Refreshing..." : "Refresh"}
                </Button>
              </div>

              <div className="mt-[var(--space-16)] grid gap-[var(--space-12)] md:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <label className="ui-type-caption text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--neutral-muted)]">
                    Key
                  </label>
                  <input
                    value={memoryKey}
                    onChange={(event) => setMemoryKey(event.target.value)}
                    placeholder="pref.timezone"
                    className="h-10 rounded-[var(--radius-10)] border border-[var(--neutral-border)] bg-[var(--surface)] px-[var(--space-12)] text-sm text-[var(--neutral-text)] shadow-sm outline-none transition focus:border-[color-mix(in_srgb,var(--brand-primary)_45%,var(--neutral-border))] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--brand-primary)_25%,transparent)]"
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <label className="ui-type-caption text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--neutral-muted)]">
                    Value
                  </label>
                  <input
                    value={memoryValue}
                    onChange={(event) => setMemoryValue(event.target.value)}
                    placeholder="America/Denver"
                    className="h-10 rounded-[var(--radius-10)] border border-[var(--neutral-border)] bg-[var(--surface)] px-[var(--space-12)] text-sm text-[var(--neutral-text)] shadow-sm outline-none transition focus:border-[color-mix(in_srgb,var(--brand-primary)_45%,var(--neutral-border))] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--brand-primary)_25%,transparent)]"
                  />
                </div>
              </div>

              <div className="mt-[var(--space-12)] flex flex-wrap items-center gap-[var(--space-12)]">
                <Button type="button" onClick={() => void handleSaveMemory()} disabled={isMemorySaving || !memoryKey.trim() || !memoryValue.trim()}>
                  {isMemorySaving ? "Saving..." : "Save"}
                </Button>
                <p className="text-xs text-[var(--neutral-muted)]">
                  Tips: Use keys like `pref.*`, `loop.*`, `reminder.*`.
                </p>
              </div>
            </div>

            <div className="mt-[var(--space-16)] space-y-[var(--space-12)]">
              {!memoryItems.length ? (
                <div className="text-sm text-[var(--neutral-muted)]">
                  No memory items yet.
                </div>
              ) : null}

              {memoryItems.map((item) => (
                <div
                  key={item.id}
                  className="rounded-[var(--radius-12)] border border-[var(--neutral-border)] bg-[var(--neutral-panel)] p-[var(--space-14)] shadow-sm"
                >
                  <div className="flex items-start justify-between gap-[var(--space-12)]">
                    <div className="min-w-0">
                      <div className="font-mono text-xs text-[var(--neutral-text)]">{item.key}</div>
                      <div className="mt-2 whitespace-pre-wrap break-words text-sm text-[var(--neutral-text)]">{item.value}</div>
                      <div className="mt-2 text-[10px] text-[var(--neutral-muted)]">
                        Updated {new Date(item.updated_at).toLocaleString()}
                      </div>
                    </div>
                    <Button type="button" variant="outline" size="sm" onClick={() => void handleDeleteMemory(item.id)}>
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      </aside>
    </>
  );
}
