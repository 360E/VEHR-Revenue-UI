"use client";

import { ReactNode, createContext, useContext, useEffect } from "react";

export type AppLayoutConfig = {
  moduleLabel?: string;
  pageTitle?: string;
  subtitle?: string;
  showSearch?: boolean;
  searchPlaceholder?: string;
  notificationCount?: number;
  actions?: ReactNode;
  showSidebar?: boolean;
};

type AppLayoutConfigContextValue = {
  setLayoutConfig: (config: Partial<AppLayoutConfig>) => void;
  resetLayoutConfig: () => void;
  searchQuery: string;
  setSearchQuery: (value: string) => void;
};

export const AppLayoutConfigContext = createContext<AppLayoutConfigContextValue | null>(null);

export function useAppLayoutConfig() {
  const value = useContext(AppLayoutConfigContext);
  if (!value) {
    throw new Error("useAppLayoutConfig must be used within AppLayoutConfigContext");
  }
  return value;
}

type AppLayoutPageConfigProps = AppLayoutConfig;

export function AppLayoutPageConfig({
  moduleLabel,
  pageTitle,
  subtitle,
  showSearch,
  searchPlaceholder,
  notificationCount,
  actions,
  showSidebar,
}: AppLayoutPageConfigProps) {
  const { setLayoutConfig, resetLayoutConfig } = useAppLayoutConfig();

  useEffect(() => {
    setLayoutConfig({
      moduleLabel,
      pageTitle,
      subtitle,
      showSearch,
      searchPlaceholder,
      notificationCount,
      actions,
      showSidebar,
    });
    return () => {
      resetLayoutConfig();
    };
  }, [
    moduleLabel,
    notificationCount,
    actions,
    pageTitle,
    resetLayoutConfig,
    searchPlaceholder,
    setLayoutConfig,
    showSearch,
    showSidebar,
    subtitle,
  ]);

  return null;
}
