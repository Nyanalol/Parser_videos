"""Estimación de coste de las llamadas a OpenAI.

Precios orientativos (USD) por si quieres saber cuánto cuesta cada resumen.
Son aproximados y pueden cambiar; sirven para hacerte una idea.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Precio de Whisper por minuto de audio (USD).
WHISPER_PER_MIN = 0.006

# Precio por 1M de tokens (entrada, salida) en USD. Aproximado.
CHAT_PRICES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
}


@dataclass
class CostTracker:
    """Acumula el coste estimado de una ejecución."""

    whisper_minutes: float = 0.0
    chat_in_tokens: int = 0
    chat_out_tokens: int = 0
    model: str = "gpt-4o-mini"
    notes: list[str] = field(default_factory=list)

    def add_whisper(self, seconds: float) -> None:
        self.whisper_minutes += max(0.0, seconds) / 60.0

    def add_chat(self, in_tokens: int, out_tokens: int) -> None:
        self.chat_in_tokens += int(in_tokens or 0)
        self.chat_out_tokens += int(out_tokens or 0)

    @property
    def total_usd(self) -> float:
        whisper = self.whisper_minutes * WHISPER_PER_MIN
        pin, pout = CHAT_PRICES.get(self.model, CHAT_PRICES["gpt-4o-mini"])
        chat = (self.chat_in_tokens / 1_000_000) * pin + (self.chat_out_tokens / 1_000_000) * pout
        return whisper + chat

    def summary(self) -> str:
        parts = []
        if self.whisper_minutes:
            parts.append(f"Whisper {self.whisper_minutes:.1f} min")
        if self.chat_in_tokens or self.chat_out_tokens:
            parts.append(f"chat {self.chat_in_tokens}+{self.chat_out_tokens} tok")
        detalle = ", ".join(parts) if parts else "sin coste (caché)"
        return f"Coste estimado: ${self.total_usd:.4f} ({detalle})"
