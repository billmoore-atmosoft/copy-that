"""One card design for every model choice: speech, cleanup, and the welcome window."""
import customtkinter as ctk

from ui import theme


def size_text(size_gb):
    return f"{size_gb:.1f} GB" if size_gb >= 1 else f"{round(size_gb * 1000)} MB"


class ModelCard:
    """Name, one-line trade-off, and a status: Installed, Download, or progress.

    States: "none" (nothing to download), "available", "queued" (size only),
    "downloading", "installed", "removable" (installed and not in use).
    """

    def __init__(self, parent, title, summary, size_gb=None, variable=None, value=None,
                 on_download=None, on_cancel=None, on_remove=None, on_select=None):
        self._size_gb = size_gb
        self._on_download, self._on_cancel, self._on_remove = on_download, on_cancel, on_remove
        self._state = None
        self.frame = ctk.CTkFrame(parent, fg_color=theme.SURFACE, border_color=theme.BORDER,
                                  border_width=1, corner_radius=8)
        top = ctk.CTkFrame(self.frame, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 0))
        font = ctk.CTkFont(size=14, weight="bold")
        if variable is not None:
            self._radio = ctk.CTkRadioButton(
                top, text=title, variable=variable, value=value, font=font,
                fg_color=theme.ACCENT, border_color=theme.BORDER, hover_color=theme.ACCENT_HOVER,
                text_color=theme.TEXT, text_color_disabled=theme.TEXT, command=on_select)
            self._radio.pack(side="left")
        else:
            self._radio = None
            ctk.CTkLabel(top, text=title, font=font, text_color=theme.TEXT).pack(side="left")
        self._status = ctk.CTkFrame(top, fg_color="transparent", height=28)
        self._status.pack(side="right")
        self._summary = ctk.CTkLabel(self.frame, text=summary, text_color=theme.MUTED,
                                     anchor="w", justify="left", wraplength=420)
        self._summary.pack(fill="x", padx=(40 if variable is not None else 12, 12), pady=(2, 10))
        # Wrap to the card's real width so long lines never clip.
        self.frame.bind("<Configure>", lambda e: self._summary.configure(
            wraplength=max(200, e.width - 70)))
        self._bar = self._percent = None

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)
        return self

    @property
    def state(self):
        return self._state

    def set_state(self, state, fraction=0.0):
        if state == self._state:
            if state == "downloading" and self._bar is not None:
                self._bar.set(fraction)
                self._percent.configure(text=f"{int(fraction * 100)}%")
            return
        self._state = state
        for child in self._status.winfo_children():
            child.destroy()
        self._bar = self._percent = None
        link = dict(fg_color="transparent", hover_color=theme.SELECTED, height=26, width=60,
                    font=ctk.CTkFont(size=12))
        if state in ("installed", "removable"):
            if state == "removable" and self._on_remove:
                ctk.CTkButton(self._status, text="Remove", text_color=theme.MUTED,
                              command=self._on_remove, **link).pack(side="right", padx=(6, 0))
            ctk.CTkLabel(self._status, text="Installed", text_color=theme.SUCCESS,
                         font=ctk.CTkFont(size=12)).pack(side="right")
        elif state == "queued":
            ctk.CTkLabel(self._status, text=size_text(self._size_gb), text_color=theme.MUTED,
                         font=ctk.CTkFont(size=12)).pack(side="right")
        elif state == "available":
            ctk.CTkButton(self._status, text=f"Download · {size_text(self._size_gb)}",
                          command=self._on_download, height=28, width=130,
                          fg_color=theme.BG, hover_color=theme.SELECTED, text_color=theme.TEXT,
                          border_color=theme.BORDER, border_width=1,
                          font=ctk.CTkFont(size=12)).pack(side="right")
        elif state == "downloading":
            if self._on_cancel:
                ctk.CTkButton(self._status, text="Cancel", text_color=theme.MUTED,
                              command=self._on_cancel, **link).pack(side="right", padx=(6, 0))
            self._percent = ctk.CTkLabel(self._status, text=f"{int(fraction * 100)}%",
                                         text_color=theme.MUTED, width=36, font=ctk.CTkFont(size=12))
            self._percent.pack(side="right")
            self._bar = ctk.CTkProgressBar(self._status, width=120, height=6,
                                           progress_color=theme.ACCENT, fg_color=theme.BORDER)
            self._bar.pack(side="right", padx=(0, 6))
            self._bar.set(fraction)
        if self._radio is not None:
            # A model can be chosen only once it is on disk.
            self._radio.configure(state="disabled" if state in ("available", "queued", "downloading") else "normal")
