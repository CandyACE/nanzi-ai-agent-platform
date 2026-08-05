import { ref } from "vue"

export type AppTheme = "light" | "dark"

const STORAGE_KEY = "nanzi_app_theme"
const theme = ref<AppTheme>("dark")
let initialized = false

function applyTheme(nextTheme: AppTheme) {
  theme.value = nextTheme
  if (typeof document === "undefined") return

  document.documentElement.dataset.theme = nextTheme
}

export function initializeTheme() {
  if (initialized) return
  initialized = true

  let storedTheme: string | null = null
  try {
    storedTheme = localStorage.getItem(STORAGE_KEY)
  } catch {
    storedTheme = null
  }

  applyTheme(storedTheme === "light" ? "light" : "dark")
}

function setTheme(nextTheme: AppTheme) {
  initializeTheme()
  applyTheme(nextTheme)
  try {
    localStorage.setItem(STORAGE_KEY, nextTheme)
  } catch {
    // Theme remains active for the current page when storage is unavailable.
  }
}

function toggleTheme() {
  setTheme(theme.value === "light" ? "dark" : "light")
}

export function useAppTheme() {
  initializeTheme()
  return { theme, setTheme, toggleTheme, initializeTheme }
}
