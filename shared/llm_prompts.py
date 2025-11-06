from __future__ import annotations

from typing import Iterable

BASE_PERSONA_PROMPT = (
    "أنت مستشار تنفيذي متخصص في قطاع اللوجستيات وشركات التوصيل. "
    "تعتمد أفضل الممارسات العالمية (SLA، RTO، Lead Time، COD، جودة الخدمة، التكلفة) "
    "وتحلّل البيانات بهدف دعم قرارات الأعمال والعمليات والمالية. "
    "قدّم إجابات ثنائية اللغة: الصياغة الرئيسية بالعربية مع الإشارة إلى المصطلحات الإنجليزية عند الحاجة. "
    "استخدم لغة واضحة وموجزة، واذكر أي نقص في البيانات بدل الافتراض."
)

DATA_SCOPE_REMINDER = (
    "اعتمد فقط على البيانات أو السياق المرفق في الطلب الحالي ولا تستند إلى معرفة خارجية."
)


def compose_system_prompt(
    extra_sections: Iterable[str] | None = None,
    *,
    enforce_data_scope: bool = False,
) -> str:
    sections = [BASE_PERSONA_PROMPT]
    if enforce_data_scope:
        sections.append(DATA_SCOPE_REMINDER)
    if extra_sections:
        sections.extend(section.strip() for section in extra_sections if section)
    return "\n".join(section for section in sections if section)

