"use client";

import Image from "next/image";

import { cn } from "@/lib/utils";

type BrandLogoProps = {
  className?: string;
  size?: number;
};

export function BrandLogo({ className, size = 28 }: BrandLogoProps) {
  return (
    <span className={cn("inline-flex items-center justify-center overflow-hidden rounded-[var(--radius-8)]", className)}>
      <Image
        src="/360-encompass-logo.svg"
        alt="360 Encompass logo"
        width={size}
        height={size}
      />
    </span>
  );
}
