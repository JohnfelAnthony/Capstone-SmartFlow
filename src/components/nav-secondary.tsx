"use client"

import * as React from "react"

import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { MoonIcon, ShuffleIcon, SunIcon } from "lucide-react"

import { getInitialTheme, applyTheme, clearRandomPalette, generateRandomPalette, applyRandomPalette, type ThemeMode, type RandomPalette } from "@/lib/appearance"
import { writePreference } from "@/lib/local-preference-store"

export function NavSecondary({
  activeItem,
  items,
  onSelectItem,
  ...props
}: {
  activeItem: string
  items: {
    title: string
    url: string
    icon: React.ReactNode
  }[]
  onSelectItem: (item: string) => void
} & React.ComponentPropsWithoutRef<typeof SidebarGroup>) {
  const [theme, setTheme] = React.useState<ThemeMode>(getInitialTheme)
  const [randomCount, setRandomCount] = React.useState(() => {
    if (typeof window === "undefined") {
      return 0
    }

    return Number(window.localStorage.getItem("smartflow-random-count") || "0")
  })
  const isLight = theme === "light"
  const ThemeIcon = isLight ? SunIcon : MoonIcon

  React.useEffect(() => {
    applyTheme(theme)
    void writePreference("smartflow-theme", theme).catch(console.error)
  }, [theme])

  React.useEffect(() => {
    const savedPalette = window.localStorage.getItem("smartflow-random-palette")

    if (savedPalette) {
      try {
        applyRandomPalette(JSON.parse(savedPalette) as RandomPalette)
      } catch {
        void clearRandomPalette().catch(console.error)
      }
    }
  }, [])

  React.useEffect(() => {
    const update = () => setTheme(getInitialTheme())
    window.addEventListener("smartflow-appearance", update)
    return () => window.removeEventListener("smartflow-appearance", update)
  }, [])

  function handleRandomize() {
    const palette = generateRandomPalette()
    const nextCount = randomCount + 1

    applyRandomPalette(palette)
    setRandomCount(nextCount)
    void writePreference("smartflow-random-count", String(nextCount)).catch(console.error)
    void writePreference("smartflow-random-palette", JSON.stringify(palette)).catch(console.error)
  }

  function handleThemeToggle() {
    void clearRandomPalette().catch(console.error)
    setTheme(isLight ? "dark" : "light")
  }

  return (
    <SidebarGroup {...props}>
      <SidebarGroupContent>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              className="smartflow-randomize-button"
              onClick={handleRandomize}
            >
              <ShuffleIcon />
              <span>Randomize</span>
              <span className="smartflow-random-count">{randomCount}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton
              className="smartflow-theme-toggle"
              onClick={handleThemeToggle}
            >
              <ThemeIcon />
              <span>{isLight ? "Light Mode" : "Dark Mode"}</span>
              <span className="smartflow-theme-switch" data-on={isLight}>
                <span />
              </span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          {items.map((item) => (
            <SidebarMenuItem key={item.title}>
              <SidebarMenuButton
                className={item.title === activeItem ? "smartflow-nav-active" : ""}
                onClick={() => onSelectItem(item.title)}
                render={<a href={item.url} />}
              >
                {item.icon}
                <span>{item.title}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}
