from rich.console import Console
from rich.theme import Theme

DRACULA = {
    "background":  "#282a36",
    "foreground":  "#f8f8f2",
    "comment":     "#6272a4",
    "cyan":        "#8be9fd",
    "green":       "#50fa7b",
    "orange":      "#ffb86c",
    "pink":        "#ff79c6",
    "purple":      "#bd93f9",
    "red":         "#ff5555",
    "yellow":      "#f1fa8c",
}

dracula_theme = Theme({
    "info":      "bold " + DRACULA["cyan"],
    "success":   "bold " + DRACULA["green"],
    "warning":   "bold " + DRACULA["orange"],
    "error":     "bold " + DRACULA["red"],
    "muted":     DRACULA["comment"],
    "accent":    DRACULA["purple"],
    "highlight": DRACULA["pink"],
})

console = Console(theme=dracula_theme)


def vampire_print(msg: str, style: str = "info") -> None:
    console.print(f"🧛🏻 {msg}", style=style)


def bat_warn(msg: str) -> None:
    console.print(f"🦇 {msg}", style="warning")


def coffin_error(msg: str) -> None:
    console.print(f"⚰️  {msg}", style="error")
    console.bell()
