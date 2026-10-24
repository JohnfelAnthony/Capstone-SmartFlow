"use client"

import * as React from "react"

import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { MoonIcon, SunIcon } from "lucide-react"

import { getInitialTheme, applyTheme, clearRandomPalette, type ThemeMode } from "@/lib/appearance"

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
  const isLight = theme === "light"
  const ThemeIcon = isLight ? SunIcon : MoonIcon

  React.useEffect(() => {
    applyTheme(theme)
    window.localStorage.setItem("smartflow-theme", theme)
  }, [theme])

  React.useEffect(() => {
    clearRandomPalette()
  }, [])

  React.useEffect(() => {
    const update = () => setTheme(getInitialTheme())
    window.addEventListener("smartflow-appearance", update)
    return () => window.removeEventListener("smartflow-appearance", update)
  }, [])

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
