from __future__ import annotations

import html
from typing import Optional

import regex as re  # type: ignore
import ftfy  # type: ignore

_AR_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0657-\u065F\u0670]")
_AR_ALEF = re.compile(r"[\u0622\u0623\u0625\u0671\u0672\u0673\u0675\u0627]")
_AR_YA = re.compile(r"[\u0649\u064A\u06D2\u06CC]")
_AR_TA_MARBUTA = re.compile(r"[\u0629\u06C3]")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_URL_RE = re.compile(r"https?://\S+|www\.[^\s]+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:(?:\+?[\d]{1,3})?[\s\-]*\d[\d\-\s]{5,}\d)")
_ID_RE = re.compile(r"\b\d{10,}\b")


def _compact_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_ar_en(
    text: Optional[str],
    *,
    unescape_html: bool = True,
    unify_alef_ya_ta: bool = True,
    strip_diacritics: bool = True,
    unify_digits: bool = True,
) -> str:
    if not text:
        return ""
    value = ftfy.fix_text(text, normalization="NFC")
    if unescape_html:
        value = html.unescape(value)
    value = _compact_spaces(value)
    if unify_alef_ya_ta:
        value = _AR_ALEF.sub("ا", value)
        value = _AR_YA.sub("ي", value)
        value = _AR_TA_MARBUTA.sub("ه", value)
    if strip_diacritics:
        value = _AR_DIACRITICS.sub("", value)
    if unify_digits:
        value = value.translate(_AR_DIGITS)
    return value


def mask_pii(text: Optional[str]) -> str:
    if not text:
        return ""
    value = _URL_RE.sub("<URL>", text)
    value = _EMAIL_RE.sub("<EMAIL>", value)
    value = _PHONE_RE.sub("<PHONE>", value)
    value = _ID_RE.sub("<ID>", value)
    return value


__all__ = ["normalize_ar_en", "mask_pii"]
