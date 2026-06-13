"""
bootstrap.py — First-run onboarding wizard for NickOS.

Interviews Nick one question at a time via Telegram,
then writes USER.md and SOUL.md automatically.

Usage in Telegram bot:
    /bootstrap   — start or resume the interview
    Any reply    — answer current question

State is persisted to bootstrap_state.json so it survives bot restarts.
"""

import json
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional
import anthropic

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
USER_MD        = BASE_DIR / "USER.md"
SOUL_MD        = BASE_DIR / "SOUL.md"
BOOTSTRAP_MD   = BASE_DIR / "BOOTSTRAP.md"
STATE_FILE     = BASE_DIR / ".bootstrap_state.json"

# ─── Interview questions ───────────────────────────────────────────────────────
# Each question maps to a key that gets assembled into USER.md / SOUL.md

QUESTIONS = [
    {
        "key":     "full_name",
        "section": "user",
        "ask":     "Let's set up your NickOS profile. What's your full name?",
        "hint":    "e.g. Nick Johnson",
    },
    {
        "key":     "age_location",
        "section": "user",
        "ask":     "How old are you and where are you based?",
        "hint":    "e.g. 21, Boston MA",
    },
    {
        "key":     "current_situation",
        "section": "user",
        "ask":     "In 2–3 sentences, what's your current situation? (school, work, living situation)",
        "hint":    "e.g. Junior at Northeastern, double major CS/Finance, living off-campus",
    },
    {
        "key":     "top_goals",
        "section": "user",
        "ask":     "What are your top 3 goals right now? List them on separate lines.",
        "hint":    "e.g.\n1. Launch algo trading bot\n2. Study abroad next semester\n3. Hit 185 lb by August",
    },
    {
        "key":     "biggest_challenges",
        "section": "user",
        "ask":     "What are the 2–3 biggest challenges or obstacles you're currently facing?",
        "hint":    "Be honest — this helps NickOS give you better coaching",
    },
    {
        "key":     "fitness_stats",
        "section": "user",
        "ask":     "Quick fitness snapshot: height, weight, goal weight, current workout split?",
        "hint":    "e.g. 6'0, 172 lb, goal 185 lb, Push/Pull/Legs 5x/week",
    },
    {
        "key":     "diet_style",
        "section": "user",
        "ask":     "How do you eat? Any restrictions, budget, or preferences?",
        "hint":    "e.g. High protein, ~$50/week budget, no pork, meal prep Sundays",
    },
    {
        "key":     "sleep_habits",
        "section": "user",
        "ask":     "What's your typical sleep schedule? When do you usually go to bed and wake up?",
        "hint":    "e.g. Bed by midnight, up at 7:30am — but inconsistent",
    },
    {
        "key":     "values",
        "section": "soul",
        "ask":     "What are your 3–5 core values? What do you actually stand for?",
        "hint":    "e.g. Discipline, Ownership, Building, Family, Excellence",
    },
    {
        "key":     "identity",
        "section": "soul",
        "ask":     "How do you see yourself? Finish this: \"I am someone who...\"",
        "hint":    "e.g. builds things, doesn't wait for permission, takes calculated risks",
    },
    {
        "key":     "fears",
        "section": "soul",
        "ask":     "What's your biggest fear or thing you're most trying to avoid in life?",
        "hint":    "This stays private — it helps the bot coach you through hard moments",
    },
    {
        "key":     "vision",
        "section": "soul",
        "ask":     "What does your ideal life look like in 5 years? Be specific.",
        "hint":    "Job, finances, relationships, where you live, what you've built",
    },
    {
        "key":     "communication_style",
        "section": "soul",
        "ask":     "How do you want NickOS to talk to you? Pick a style:",
        "options": [
            "Direct and blunt — no fluff, just facts",
            "Coach/mentor — encouraging but honest",
            "Drill sergeant — push me hard, no excuses",
            "Chill friend — casual, real talk",
        ],
    },
]

# ─── State management ─────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"step": 0, "answers": {}, "started_at": datetime.now().isoformat()}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def clear_state():
    if STATE_FILE.exists():
        STATE_FILE.unlink()


# ─── Bootstrap conversation handler ───────────────────────────────────────────

class BootstrapWizard:
    def __init__(self):
        self.state = load_state()

    @property
    def is_complete(self) -> bool:
        return self.state["step"] >= len(QUESTIONS)

    @property
    def current_question(self) -> Optional[dict]:
        if self.is_complete:
            return None
        return QUESTIONS[self.state["step"]]

    def get_prompt(self) -> str:
        """Return the message to send to Nick for the current question."""
        if self.is_complete:
            return "✅ Profile complete!"

        q    = self.current_question
        step = self.state["step"] + 1
        total = len(QUESTIONS)
        prog  = "▓" * step + "░" * (total - step)

        msg = f"[{step}/{total}] {prog}\n\n**{q['ask']}**"
        if "hint" in q:
            msg += f"\n\n_e.g. {q['hint']}_"
        if "options" in q:
            for i, opt in enumerate(q["options"], 1):
                msg += f"\n{i}. {opt}"
            msg += "\n\n_Reply with the number or your own answer_"
        return msg

    def handle_answer(self, answer: str) -> str:
        """
        Process an answer for the current question.
        Returns the next message to send.
        """
        if self.is_complete:
            return "Profile is already complete. Use /profile to view it."

        q = self.current_question

        # Resolve numbered option
        if "options" in q and answer.strip().isdigit():
            idx = int(answer.strip()) - 1
            if 0 <= idx < len(q["options"]):
                answer = q["options"][idx]

        # Save answer
        self.state["answers"][q["key"]] = answer.strip()
        self.state["step"] += 1
        save_state(self.state)

        # If done, generate and write profile files
        if self.is_complete:
            return self._finalize()

        # Otherwise return next question
        return self.get_prompt()

    def _finalize(self) -> str:
        """Generate USER.md and SOUL.md from collected answers."""
        answers = self.state["answers"]

        # Build USER.md
        user_md = textwrap.dedent(f"""
            # USER.md — Nick's Profile
            _Generated by NickOS Bootstrap on {datetime.now().strftime('%Y-%m-%d')}_

            ## Identity
            **Name:** {answers.get('full_name', 'Nick')}
            **Age/Location:** {answers.get('age_location', 'Unknown')}

            ## Current Situation
            {answers.get('current_situation', '')}

            ## Top Goals Right Now
            {answers.get('top_goals', '')}

            ## Biggest Challenges
            {answers.get('biggest_challenges', '')}

            ## Fitness
            {answers.get('fitness_stats', '')}

            ## Diet
            {answers.get('diet_style', '')}

            ## Sleep
            {answers.get('sleep_habits', '')}
        """).strip()

        USER_MD.write_text(user_md)

        # Build SOUL.md via Claude
        soul_md = self._generate_soul_md(answers)
        SOUL_MD.write_text(soul_md)

        # Write readable BOOTSTRAP.md summary
        self._write_bootstrap_summary(answers)

        clear_state()

        return textwrap.dedent("""
            ✅ **NickOS profile complete!**

            I've written:
            • `USER.md` — your current situation, goals, fitness, diet
            • `SOUL.md` — your values, identity, vision (AI-refined)
            • `BOOTSTRAP.md` — raw interview notes

            From now on, every session I load these automatically so I always know who you are.

            Type /today to see your dashboard, or /help for all commands.
        """).strip()

    def _generate_soul_md(self, answers: dict) -> str:
        """Use Claude Haiku to refine raw answers into a tight SOUL.md."""
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": f"""You are writing SOUL.md for a personal AI operating system.
Take these raw answers and write a tight, first-person identity document.
Be direct, specific, honest. No fluff. Write AS Nick, not about Nick.

Raw answers:
Values: {answers.get('values', '')}
Identity: {answers.get('identity', '')}
Biggest fear: {answers.get('fears', '')}
5-year vision: {answers.get('vision', '')}
Preferred communication: {answers.get('communication_style', '')}

Format:
# SOUL.md — Who I Am

## Core Values
[bullet list]

## My Identity
I am someone who [2-3 sentences]

## What I'm Building Toward
[2-3 sentences on 5-year vision]

## What I'm Afraid Of
[honest, 1-2 sentences]

## How I Want to Be Coached
[1 sentence on communication style]

## My Operating Principles
[3-5 rules you live by, in first person]"""
            }]
        )
        return f"# SOUL.md — Nick's Identity\n_Generated {datetime.now().strftime('%Y-%m-%d')}_\n\n{msg.content[0].text}"

    def _write_bootstrap_summary(self, answers: dict):
        lines = [f"# BOOTSTRAP.md — Interview Notes\n_Completed {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n"]
        for q in QUESTIONS:
            key = q["key"]
            if key in answers:
                lines.append(f"## {q['ask']}\n{answers[key]}\n")
        BOOTSTRAP_MD.write_text("\n".join(lines))


# ─── Singleton (one wizard per bot session) ───────────────────────────────────
_wizard: Optional[BootstrapWizard] = None


def get_wizard() -> BootstrapWizard:
    global _wizard
    if _wizard is None or _wizard.is_complete:
        _wizard = BootstrapWizard()
    return _wizard


def handle_bootstrap_message(text: str, is_start_command: bool = False) -> str:
    """
    Main entry point for Telegram /bootstrap command and replies.

    In your Telegram bot:
        if message.text == '/bootstrap':
            reply(handle_bootstrap_message('', is_start_command=True))
        elif user_in_bootstrap_flow:
            reply(handle_bootstrap_message(message.text))
    """
    wizard = get_wizard()

    if is_start_command:
        if wizard.state["step"] > 0:
            pct = int(wizard.state["step"] / len(QUESTIONS) * 100)
            return f"Resuming bootstrap ({pct}% complete)...\n\n{wizard.get_prompt()}"
        return f"👋 Let's set up your NickOS profile. This takes ~3 minutes.\n\n{wizard.get_prompt()}"

    return wizard.handle_answer(text)


def is_bootstrap_active() -> bool:
    """Check if bootstrap is currently in progress."""
    return STATE_FILE.exists() and not get_wizard().is_complete
