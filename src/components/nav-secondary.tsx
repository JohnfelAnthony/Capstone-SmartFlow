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
    window.localStorage.setItem("smartflow-theme", theme)
  }, [theme])

  React.useEffect(() => {
    const savedPalette = window.localStorage.getItem("smartflow-random-palette")

    if (savedPalette) {
      try {
        applyRandomPalette(JSON.parse(savedPalette) as RandomPalette)
      } catch {
        clearRandomPalette()
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
    window.localStorage.setItem("smartflow-random-count", String(nextCount))
    window.localStorage.setItem("smartflow-random-palette", JSON.stringify(palette))
  }

  function handleThemeToggle() {
    clearRandomPalette()
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
