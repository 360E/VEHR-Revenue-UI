"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ModuleTileCard } from "@/components/enterprise/module-tile-card";
import { PageShell } from "@/components/enterprise/page-shell";
import { SectionCard } from "@/components/enterprise/section-card";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { AppLayoutPageConfig, useAppLayoutConfig } from "@/lib/app-layout-config";
import { ModuleId, defaultRouteForModule, getModuleById, isModuleId } from "@/lib/modules";
import { fetchMePreferences, patchMePreferences } from "@/lib/preferences";

export default function DirectoryPage() {
  const { searchQuery } = useAppLayoutConfig();
  const router = useRouter();
  const [allowedModules, setAllowedModules] = useState<ModuleId[]>([]);
  const [lastActiveModule, setLastActiveModule] = useState<ModuleId | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [launchingModule, setLaunchingModule] = useState<ModuleId | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const preferences = await fetchMePreferences();
        if (!isMounted) return;
        const normalized = preferences.allowed_modules.filter((id): id is ModuleId => isModuleId(id));
        setAllowedModules(normalized);
        setLastActiveModule(isModuleId(preferences.last_active_module) ? preferences.last_active_module : null);
      } catch (loadError) {
        if (!isMounted) return;
        if (loadError instanceof ApiError || loadError instanceof Error) {
          setError(loadError.message);
        } else {
          setError("Failed to load organizational directory");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      isMounted = false;
    };
  }, []);

  const visibleTiles = useMemo(() => {
    return allowedModules.map((moduleId) => getModuleById(moduleId));
  }, [allowedModules]);

  const filteredTiles = useMemo(() => {
    const normalized = searchQuery.trim().toLowerCase();
    if (!normalized) return visibleTiles;
    return visibleTiles.filter((tile) =>
      `${tile.name} ${tile.description}`.toLowerCase().includes(normalized),
    );
  }, [searchQuery, visibleTiles]);

  const recentModuleIds = useMemo(() => {
    const modules: ModuleId[] = [];
    if (lastActiveModule && allowedModules.includes(lastActiveModule)) {
      modules.push(lastActiveModule);
    }
    for (const moduleId of allowedModules) {
      if (!modules.includes(moduleId)) {
        modules.push(moduleId);
      }
      if (modules.length >= 3) {
        break;
      }
    }
    return modules;
  }, [allowedModules, lastActiveModule]);

  async function enterModule(moduleId: ModuleId) {
    try {
      setLaunchingModule(moduleId);
      await patchMePreferences({ last_active_module: moduleId });
      router.push(defaultRouteForModule(moduleId));
    } catch (launchError) {
      if (launchError instanceof ApiError || launchError instanceof Error) {
        setError(launchError.message);
      } else {
        setError("Failed to enter module");
      }
    } finally {
      setLaunchingModule(null);
    }
  }

  return (
    <div className="flex flex-col gap-[var(--space-24)]" data-testid="directory-launcher">
      <AppLayoutPageConfig
        moduleLabel="Home"
        pageTitle="Organizational Directory"
        subtitle="Choose a module workspace and continue team operations."
        showSearch={true}
        searchPlaceholder="Search modules"
        showSidebar={false}
      />

      <PageShell
        eyebrow="Launcher"
        title="Module Workspace Launcher"
        description="Select a module to open your operational workspace."
        testId="directory-page-shell"
      >
        {error ? (
          <div className="rounded-[var(--radius-6)] border border-[color-mix(in_srgb,var(--status-critical)_25%,white)] bg-[color-mix(in_srgb,var(--status-critical)_8%,white)] px-[var(--space-12)] py-[var(--space-8)] text-[length:var(--font-size-14)] text-[var(--status-critical)]">
            {error}
          </div>
        ) : null}

        <SectionCard
          title="Recently used"
          description="Quickly jump back into recent module workspaces."
          testId="directory-recently-used"
        >
          {recentModuleIds.length === 0 ? (
            <p className="ui-type-body text-[var(--neutral-muted)]">
              No recent modules yet. Open any module to populate this row.
            </p>
          ) : (
            <div className="flex flex-wrap gap-[var(--space-8)]">
              {recentModuleIds.map((moduleId) => {
                const moduleDef = getModuleById(moduleId);
                return (
                  <Button
                    key={`recent-${moduleDef.id}`}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => enterModule(moduleDef.id)}
                    disabled={launchingModule === moduleDef.id}
                  >
                    {launchingModule === moduleDef.id ? `Opening ${moduleDef.name}...` : moduleDef.name}
                  </Button>
                );
              })}
            </div>
          )}
        </SectionCard>

        {loading ? (
          <div className="ui-panel px-[var(--space-16)] py-[var(--space-12)] ui-type-body text-[var(--neutral-muted)]">
            Loading modules...
          </div>
        ) : null}

        {!loading && filteredTiles.length === 0 ? (
          <div className="ui-panel px-[var(--space-16)] py-[var(--space-12)] ui-type-body text-[var(--neutral-muted)]">
            {visibleTiles.length === 0
              ? "No modules are currently available for your role in this organization."
              : "No modules match the current search."}
          </div>
        ) : null}

        {!loading && filteredTiles.length > 0 ? (
          <div className="grid grid-cols-1 gap-[var(--space-16)] md:grid-cols-2 xl:grid-cols-3" data-testid="directory-module-grid">
            {filteredTiles.map((tile) => (
              <ModuleTileCard
                key={tile.id}
                moduleId={tile.id}
                title={tile.name}
                description={tile.description}
                onOpen={() => enterModule(tile.id)}
                isOpening={launchingModule === tile.id}
                testId={`directory-module-${tile.id}`}
              />
            ))}
          </div>
        ) : null}
      </PageShell>
    </div>
  );
}
