"""First-run welcome: one click downloads the recommended speech and cleanup models."""

import customtkinter as ctk

from ui import theme
from ui.model_cards import ModelCard, size_text

# Recommended pair, downloaded in this order: dictation works once speech lands.
FIRST_RUN = (("speech", "parakeet"), ("cleanup", "4b"))


class WelcomeWindow:
    def __init__(self, root, models, on_start):
        """
        Args:
            root: Parent CTk window.
            models: Provides model_state(kind, key) and cancel_download(kind, key).
            on_start: Callback() that begins the first-run downloads.
        """
        self._root = root
        self._models = models
        self._on_start = on_start
        self._started = False
        self._win = None
        self._cards = {}

    @property
    def is_open(self):
        return self._win is not None and self._win.winfo_exists()

    def show(self):
        if self.is_open:
            self._win.focus_force()
            return
        from dictation_engine import CLEANUP_REGISTRY, MODEL_REGISTRY
        speech, cleanup = MODEL_REGISTRY["parakeet"], CLEANUP_REGISTRY["4b"]
        total = speech["size_gb"] + cleanup["size_gb"]

        self._win = ctk.CTkToplevel(self._root)
        self._win.title("CopyThat · Welcome")
        self._win.geometry("560x480")
        self._win.resizable(False, False)
        self._win.configure(fg_color=theme.BG)
        self._win.update_idletasks()
        theme.title_bar(self._win)
        from ui.icons import render_app_icon
        from PIL import ImageTk
        self._icon_photo = ImageTk.PhotoImage(render_app_icon(32))
        self._win._iconbitmap_method_called = True
        self._win.iconphoto(False, self._icon_photo)

        ctk.CTkLabel(self._win, text="Welcome to CopyThat", text_color=theme.TEXT,
                     font=ctk.CTkFont(size=25, weight="bold")).pack(anchor="w", padx=28, pady=(26, 4))
        ctk.CTkLabel(self._win, text="Hold Ctrl + Win in any app to dictate. Your speech stays on this PC.",
                     text_color=theme.MUTED).pack(anchor="w", padx=28)
        ctk.CTkLabel(self._win, text=f"CopyThat needs two models ({size_text(total)}). They download once "
                     "from Hugging Face. After that, CopyThat works offline.",
                     text_color=theme.TEXT, wraplength=500, justify="left", anchor="w",
                     ).pack(anchor="w", fill="x", padx=28, pady=(18, 10))
        cards = ctk.CTkFrame(self._win, fg_color="transparent")
        cards.pack(fill="x", padx=28)
        self._cards[FIRST_RUN[0]] = ModelCard(
            cards, "Speech recognition: Parakeet", speech["summary"], speech["size_gb"]).pack(fill="x", pady=4)
        self._cards[FIRST_RUN[1]] = ModelCard(
            cards, "Polish: Standard",
            "Fixes punctuation, stutters and spoken corrections. Uses Qwen3 4B. You can turn it off in Settings.",
            cleanup["size_gb"]).pack(fill="x", pady=4)

        self._message = ctk.CTkLabel(self._win, text="", text_color=theme.MUTED, anchor="w",
                                     justify="left", wraplength=500)
        self._message.pack(anchor="w", fill="x", padx=28, pady=(10, 0))
        buttons = ctk.CTkFrame(self._win, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", padx=28, pady=22)
        self._primary = ctk.CTkButton(buttons, text=f"Download {size_text(total)}", width=150,
                                      command=self._primary_click, fg_color=theme.ACCENT,
                                      hover_color=theme.ACCENT_HOVER, text_color=theme.ON_ACCENT)
        self._primary.pack(side="right", padx=(8, 0))
        self._secondary = ctk.CTkButton(buttons, text="Later", width=110, command=self._secondary_click,
                                        fg_color=theme.SURFACE, hover_color=theme.SELECTED,
                                        text_color=theme.TEXT, border_color=theme.BORDER, border_width=1)
        self._secondary.pack(side="right")
        self._poll()

    def refresh_theme(self):
        if self.is_open:
            theme.title_bar(self._win)

    def _states(self):
        return {item: self._models.model_state(*item)[0] for item in FIRST_RUN}

    def _primary_click(self):
        states = self._states()
        if self._started and states[FIRST_RUN[0]] in ("installed", "removable"):
            self._win.destroy()  # Remaining downloads continue in the background.
            return
        self._started = True
        self._message.configure(text="")
        self._on_start()

    def _secondary_click(self):
        if any(state == "downloading" for state in self._states().values()):
            for item in FIRST_RUN:
                self._models.cancel_download(*item)
            self._started = False
        else:
            self._win.destroy()

    def set_error(self, text):
        if self.is_open:
            self._started = False
            self._message.configure(text=text, text_color=theme.ERROR)

    def _poll(self):
        if not self.is_open:
            return
        states = self._states()
        for item, card in self._cards.items():
            state, fraction = self._models.model_state(*item)
            if state == "removable":
                state = "installed"
            elif state == "available":
                state = "queued"
            card.set_state(state, fraction)
        speech_done = states[FIRST_RUN[0]] in ("installed", "removable")
        downloading = any(state == "downloading" for state in states.values())
        if speech_done and not downloading and states[FIRST_RUN[1]] != "available":
            self._message.configure(text="All set. Hold Ctrl + Win to dictate.", text_color=theme.SUCCESS)
            self._primary.configure(text="Start dictating", state="normal")
            self._secondary.pack_forget()
        elif speech_done:
            self._message.configure(text="Ready to dictate. Polish turns on when its download finishes; "
                                    "you can close this window.", text_color=theme.SUCCESS)
            self._primary.configure(text="Close", state="normal")
            self._secondary.configure(text="Cancel" if downloading else "Later")
        elif downloading:
            self._primary.configure(text="Downloading…", state="disabled")
            self._secondary.configure(text="Cancel")
        else:
            self._primary.configure(state="normal")
            self._secondary.configure(text="Later")
        self._win.after(400, self._poll)
