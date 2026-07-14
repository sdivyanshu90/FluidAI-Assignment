from __future__ import annotations
import re

class RequestGuard:
    """Deterministic input guardrails applied before any model call."""

    _secret_patterns = (
        re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"gh[pousr]_[A-Za-z0-9_]{30,}"),
    )
    _prompt_injection_patterns = (
        re.compile(r"\bignore\s+(?:all\s+|any\s+|the\s+|your\s+)?previous\s+instructions?\b", re.I),
        re.compile(r"\b(?:reveal|print|show|expose)\s+(?:the\s+)?(?:system|developer)\s+(?:prompt|message|instructions?)\b", re.I),
        re.compile(r"\b(?:bypass|disable|override)\s+(?:the\s+)?(?:guardrails?|safety|policy|restrictions?)\b", re.I),
    )
    _harmful_intent_patterns = (
        re.compile(r"\b(?:create|build|write|design|deploy)\b.{0,50}\b(?:malware|ransomware|phishing kit|credential stealer)\b", re.I),
        re.compile(r"\b(?:steal|harvest|exfiltrate)\b.{0,40}\b(?:passwords?|credentials?|api keys?|private data)\b", re.I),
        re.compile(r"\b(?:evade|bypass)\b.{0,35}\b(?:detection|authentication|access controls?)\b", re.I),
    )
    _document_scope_terms = re.compile(
        r"\b(?:plan|proposal|report|minutes|design|sop|procedure|specification|document|"
        r"strategy|roadmap|brief|analysis|policy|summary|requirements?|project|process|"
        r"launch|rollout|onboarding|meeting|business case|operating model)\b",
        re.I,
    )

    @classmethod
    def validate(cls, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip()
        if len(normalized.split()) < 3:
            raise ValueError("request must contain at least three meaningful words")
        if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
            raise ValueError("request contains unsupported control characters")
        if any(pattern.search(normalized) for pattern in cls._secret_patterns):
            raise ValueError("request appears to contain a secret; remove credentials and retry")
        if any(pattern.search(normalized) for pattern in cls._prompt_injection_patterns):
            raise ValueError("request contains prompt-injection instructions")
        if any(pattern.search(normalized) for pattern in cls._harmful_intent_patterns):
            raise ValueError("request asks for harmful or unauthorized operational content")
        if not cls._document_scope_terms.search(normalized):
            raise ValueError(
                "request must describe a business document, plan, report, design, or process"
            )
        return normalized

APPLIED_GUARDRAILS = [
    "Strict JSON schema and request-size validation",
    "Control-character and embedded-secret detection",
    "Prompt-injection and harmful-intent rejection",
    "Business-document scope enforcement",
    "Bounded tool allowlist and dependency validation",
    "Structured Gemini output validation",
    "Path-safe DOCX artifact download",
]

