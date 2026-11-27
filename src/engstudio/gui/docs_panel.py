"""Documentation panel (G6.2): local Markdown pages with Back/Forward/Home."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QHBoxLayout, QTextBrowser, QToolButton, QVBoxLayout, QWidget

from engstudio.app.docs import INDEX, DocService

__all__ = ["DocsPanel"]

_LINK_COLORS = {"light": "#0b5cad", "dark": "#6cb6ff"}


class DocsPanel(QWidget):
    def __init__(
        self, service: DocService | None = None, theme: str = "light",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if theme not in _LINK_COLORS:
            raise ValueError(f"unknown theme {theme!r}; expected one of {sorted(_LINK_COLORS)}")
        self.service = service if service is not None else DocService()
        self.theme = theme
        self.current_page: str | None = None
        self._back: list[str] = []
        self._forward: list[str] = []

        self.back_button = QToolButton()
        self.back_button.setText("Back")
        self.forward_button = QToolButton()
        self.forward_button.setText("Forward")
        self.home_button = QToolButton()
        self.home_button.setText("Home")
        self.back_button.clicked.connect(lambda _c=False: self.back())
        self.forward_button.clicked.connect(lambda _c=False: self.forward())
        self.home_button.clicked.connect(lambda _c=False: self.home())

        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(lambda url: self.open_link(url.toString()))

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        for b in (self.back_button, self.forward_button, self.home_button):
            top.addWidget(b)
        top.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(top)
        layout.addWidget(self.browser, 1)
        self.setMinimumSize(140, 80)
        self._apply_link_color()
        self.home()

    # -- navigation ---------------------------------------------------------
    def can_back(self) -> bool:
        return bool(self._back)

    def can_forward(self) -> bool:
        return bool(self._forward)

    def show_page(self, name: str, record: bool = True) -> bool:
        """Display page ``name``; False (and an error page) if it does not exist."""
        if not self.service.exists(name):
            self.browser.setMarkdown(f"# Page not found\n\nNo documentation page `{name}`.")
            return False
        if record and self.current_page is not None and self.current_page != name:
            self._back.append(self.current_page)
            self._forward.clear()
        self.current_page = name
        self.browser.setMarkdown(self.service.read(name))
        self._update_buttons()
        return True

    def home(self) -> None:
        self.show_page(INDEX)

    def back(self) -> bool:
        if not self._back or self.current_page is None:
            return False
        self._forward.append(self.current_page)
        self.show_page(self._back.pop(), record=False)
        return True

    def forward(self) -> bool:
        if not self._forward or self.current_page is None:
            return False
        self._back.append(self.current_page)
        self.show_page(self._forward.pop(), record=False)
        return True

    def open_link(self, href: str) -> bool:
        """Follow an internal link; external links are ignored (the app is offline)."""
        name = self.service.resolve(QUrl(href).toString())
        if name is None:
            return False
        return self.show_page(name)

    # -- theme --------------------------------------------------------------
    def set_theme(self, name: str) -> None:
        if name not in _LINK_COLORS:
            raise ValueError(f"unknown theme {name!r}; expected one of {sorted(_LINK_COLORS)}")
        self.theme = name
        self._apply_link_color()
        if self.current_page is not None:
            self.show_page(self.current_page, record=False)

    # -- internals ----------------------------------------------------------
    def _apply_link_color(self) -> None:
        from PySide6.QtGui import QColor
        pal = self.browser.palette()
        pal.setColor(QPalette.ColorRole.Link, QColor(_LINK_COLORS[self.theme]))
        self.browser.setPalette(pal)

    def _update_buttons(self) -> None:
        self.back_button.setEnabled(self.can_back())
        self.forward_button.setEnabled(self.can_forward())
