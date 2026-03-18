"""
intelligence/llm.py
────────────────────
Supports Groq (default), OpenAI, Anthropic, and Google Gemini.
Switch provider by setting LLM_PROVIDER in .env
"""

import os
import json
import time
from dataclasses import dataclass, field, asdict
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()


@dataclass
class ActionItem:
    task:     str
    owner:    str = "Unassigned"
    deadline: str = None
    priority: str = "medium"

@dataclass
class MeetingIntelligence:
    action_items:   list[ActionItem] = field(default_factory=list)
    decisions:      list[str]        = field(default_factory=list)
    open_questions: list[str]        = field(default_factory=list)
    key_topics:     list[str]        = field(default_factory=list)
    summary:        str              = ""
    timestamp:      float            = field(default_factory=time.time)

    def to_dict(self):
        return asdict(self)

    def __str__(self):
        lines = []
        if self.summary:
            lines.append(f"📋 Summary: {self.summary}")
        if self.action_items:
            lines.append("\n✅ Action Items:")
            for ai in self.action_items:
                dl = f" (by {ai.deadline})" if ai.deadline else ""
                lines.append(f"   • [{ai.owner}] {ai.task}{dl}")
        if self.decisions:
            lines.append("\n🔨 Decisions:")
            for d in self.decisions:
                lines.append(f"   • {d}")
        if self.open_questions:
            lines.append("\n❓ Open Questions:")
            for q in self.open_questions:
                lines.append(f"   • {q}")
        return "\n".join(lines) if lines else "(nothing extracted yet)"


SYSTEM_PROMPT = """You are an expert meeting analyst and executive assistant.
Your job is to extract highly detailed, structured information from meeting transcripts.
Always respond with ONLY valid JSON — no markdown, no explanation, no preamble.
"""

def build_user_prompt(transcript: str) -> str:
    return f"""Analyze this meeting transcript carefully and return a JSON object with exactly these keys:

{{
  "action_items": [
    {{
      "task": "clear, specific description of what needs to be done",
      "owner": "person responsible by name, or Unassigned if unclear",
      "deadline": "specific deadline if mentioned, else null",
      "priority": "high / medium / low based on urgency and context"
    }}
  ],
  "decisions": [
    "Each decision as a complete, clear statement of what was agreed upon"
  ],
  "open_questions": [
    "Each unresolved question or blocker raised but not resolved"
  ],
  "key_topics": [
    "Main topics or themes discussed in the meeting"
  ],
  "summary": "Write a detailed 5-8 sentence summary covering: the overall purpose of the meeting, the main topics discussed, key decisions made, action items assigned, any blockers or risks mentioned, and the overall outcome or next steps agreed upon."
}}

Rules:
- summary MUST be 5-8 detailed sentences — be thorough, not brief
- action_items should be specific and actionable, not vague
- decisions should be complete statements, not fragments
- key_topics should list 3-6 main themes
- Only include items clearly stated in the transcript
- Empty array if nothing found for a category

TRANSCRIPT:
{transcript}
"""


class GroqProvider:
    def __init__(self):
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in .env")
        self.client = Groq(api_key=api_key)
        self.model  = "llama-3.3-70b-versatile"
        print(f"[LLM] Using Groq ({self.model})")

    def extract(self, transcript: str) -> MeetingIntelligence:
        response = self.client.chat.completions.create(
            model       = self.model,
            messages    = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": build_user_prompt(transcript)},
            ],
            temperature = 0.1,
            max_tokens  = 1000,
        )
        return _parse_response(response.choices[0].message.content)


class GeminiProvider:
    def __init__(self):
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in .env")
        self.client = genai.Client(api_key=api_key)
        self.model  = "gemini-2.0-flash"
        print(f"[LLM] Using Google Gemini ({self.model})")

    def extract(self, transcript: str) -> MeetingIntelligence:
        from google import genai
        prompt   = SYSTEM_PROMPT + "\n\n" + build_user_prompt(transcript)
        response = self.client.models.generate_content(
            model    = self.model,
            contents = prompt,
        )
        return _parse_response(response.text)


class OpenAIProvider:
    def __init__(self):
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in .env")
        self.client = OpenAI(api_key=api_key)
        self.model  = "gpt-4o"
        print(f"[LLM] Using OpenAI ({self.model})")

    def extract(self, transcript: str) -> MeetingIntelligence:
        response = self.client.chat.completions.create(
            model           = self.model,
            messages        = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": build_user_prompt(transcript)},
            ],
            response_format = {"type": "json_object"},
            temperature     = 0.1,
            max_tokens      = 1000,
        )
        return _parse_response(response.choices[0].message.content)


class AnthropicProvider:
    def __init__(self):
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in .env")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model  = "claude-sonnet-4-6"
        print(f"[LLM] Using Anthropic ({self.model})")

    def extract(self, transcript: str) -> MeetingIntelligence:
        message = self.client.messages.create(
            model      = self.model,
            max_tokens = 1000,
            system     = SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": build_user_prompt(transcript)}],
        )
        return _parse_response(message.content[0].text)


def _parse_response(raw: str) -> MeetingIntelligence:
    try:
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data  = json.loads(clean)
        action_items = [
            ActionItem(
                task     = item.get("task", ""),
                owner    = item.get("owner", "Unassigned"),
                deadline = item.get("deadline"),
                priority = item.get("priority", "medium"),
            )
            for item in data.get("action_items", [])
            if item.get("task")
        ]
        return MeetingIntelligence(
            action_items   = action_items,
            decisions      = data.get("decisions", []),
            open_questions = data.get("open_questions", []),
            key_topics     = data.get("key_topics", []),
            summary        = data.get("summary", ""),
        )
    except json.JSONDecodeError as e:
        print(f"[LLM] JSON parse error: {e}\nRaw:\n{raw[:300]}")
        return MeetingIntelligence(summary="[Parse error — check logs]")


def create_llm_provider():
    if LLM_PROVIDER == "groq":
        return GroqProvider()
    elif LLM_PROVIDER == "openai":
        return OpenAIProvider()
    elif LLM_PROVIDER in ("anthropic", "claude"):
        return AnthropicProvider()
    elif LLM_PROVIDER == "gemini":
        return GeminiProvider()
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. "
            "Set to 'groq', 'openai', 'anthropic', or 'gemini'"
        )


class IntelligenceEngine:
    def __init__(self):
        self.provider      = create_llm_provider()
        self.interval      = int(os.getenv("LLM_INTERVAL_SECONDS", "120"))
        self._last_call    = 0.0
        self.latest_result = None
        self.all_results   = []

    def maybe_extract(self, transcript: str, force: bool = False):
        now = time.time()
        if not force and (now - self._last_call) < self.interval:
            return None
        if not transcript.strip():
            return None
        print("[LLM] Extracting intelligence from transcript …")
        try:
            result = self.provider.extract(transcript)
            self._last_call    = now
            self.latest_result = result
            self.all_results.append(result)
            print(result)
            return result
        except Exception as e:
            print(f"[LLM] Error during extraction: {e}")
            return None

    def get_final_summary(self, full_transcript: str):
        return self.maybe_extract(full_transcript, force=True)