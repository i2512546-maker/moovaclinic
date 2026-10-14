from __future__ import annotations

from abc import ABC, abstractmethod

import requests

from shared.config import SMS_MODE, TEXTBEE_API_KEY, TEXTBEE_DEVICE_ID, TEXTBEE_URL


class SmsProvider(ABC):
    @abstractmethod
    def send(self, phone: str, message: str) -> bool:
        raise NotImplementedError


class ConsoleSmsProvider(SmsProvider):
    def send(self, phone: str, message: str) -> bool:
        print(f"[SMS] {phone}: {message}")
        return True


class TextBeeSmsProvider(SmsProvider):
    def send(self, phone: str, message: str) -> bool:
        if not TEXTBEE_URL or not TEXTBEE_DEVICE_ID or not TEXTBEE_API_KEY:
            return False

        cleaned = (phone or "").strip().replace(" ", "")
        if not cleaned:
            return False
        if not cleaned.startswith("+"):
            cleaned = "+51" + cleaned.lstrip("0")

        try:
            requests.post(
                TEXTBEE_URL.format(device_id=TEXTBEE_DEVICE_ID),
                json={"recipients": [cleaned], "message": message},
                headers={"x-api-key": TEXTBEE_API_KEY},
                timeout=10,
            )
            return True
        except requests.RequestException:
            return False


def get_sms_provider() -> SmsProvider:
    mode = (SMS_MODE or "console").lower()
    if mode == "textbee":
        return TextBeeSmsProvider()
    return ConsoleSmsProvider()
