"""
bot/registry.py — NickOS Skill Registry

Scans skills/*/skill.json at startup, imports each handler module, and
registers Telegram CommandHandlers + (optionally) an NLU MessageHandler.

Usage in bot/main.py:
    registry = SkillRegistry()
    registry.load_all()
    registry.register(app)

skill.json schema (all fields unless noted are required):
    {
      "name":        "reflect",          # must match folder name
      "version":     "1.0.0",
      "description": "...",
      "author":      "nickos",           # optional
      "commands": [
        {
          "command":     "reflect",      # telegram command (no slash)
          "description": "...",          # shown in command menu
          "handler":     "reflect_handler",  # function in handler.py
          "guarded":     true            # optional, default true
        }
      ],
      "nlu_handler": "memory_search_handler"  # optional; handler.py must
                                               # also expose _extract_nlu_query
    }

Hot-reload:
    registry.reload("reflect")   # re-imports handler module, updates refs
    Note: Telegram handler objects already registered with the Application
    are NOT replaced — bot restart is required for routing changes to take
    effect. reload() is useful for updating logic in long-running processes
    where the registered closures delegate to module-level functions.
"""

from __future__ import annotations

import json
import logging
import importlib
import importlib.util
from pathlib import Path

from telegram import BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.auth import guarded

logger = logging.getLogger(__name__)

ROOT       = Path(__file__).parent.parent
SKILLS_DIR = ROOT / "skills"


class SkillRegistry:
    """
    Discovers, loads, and registers all skills from the skills/ directory.
    """

    def __init__(self, skills_dir: Path | None = None):
        self.skills_dir = (skills_dir or SKILLS_DIR).resolve()
        self._loaded: dict[str, dict] = {}   # name → {meta, module, handlers}
        self._failed: dict[str, str]  = {}   # name → error message
        self._bot_commands: list[BotCommand] = []
        self._nlu_handler_fn  = None
        self._nlu_extract_fn  = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def load_all(self) -> None:
        """
        Scan skills/*/skill.json and load every skill found.
        Failures are logged and recorded in self._failed but do not abort.
        """
        skill_jsons = sorted(self.skills_dir.glob("*/skill.json"))
        if not skill_jsons:
            logger.warning(f"[registry] No skills found in {self.skills_dir}")
            return

        for json_path in skill_jsons:
            name = json_path.parent.name
            try:
                self._load_skill(json_path.parent)
            except Exception as exc:
                self._failed[name] = str(exc)
                logger.error(f"[registry] ✗ '{name}' failed: {exc}")

        # Summary
        ok_list   = ", ".join(self._loaded)
        fail_list = (f" | failed: {', '.join(self._failed)}" if self._failed else "")
        logger.info(
            f"[registry] {len(self._loaded)} skill(s) loaded: {ok_list}{fail_list}"
        )

    def register(self, app: Application) -> None:
        """
        Register all loaded skills' CommandHandlers with the Telegram Application.
        Also registers the NLU MessageHandler if any skill provides one.
        Must be called after load_all().
        """
        for name, skill in self._loaded.items():
            for command, hdef in skill["handlers"].items():
                fn = guarded(hdef["fn"]) if hdef.get("guarded", True) else hdef["fn"]
                app.add_handler(CommandHandler(command, fn))

        # NLU MessageHandler (group=1 so CommandHandlers take priority)
        if self._nlu_handler_fn and self._nlu_extract_fn:
            _extract = self._nlu_extract_fn

            class _NLUFilter(filters.MessageFilter):
                def filter(self, message):  # type: ignore[override]
                    return bool(message.text and _extract(message.text))

            app.add_handler(
                MessageHandler(
                    filters.TEXT & filters.ChatType.PRIVATE & _NLUFilter(),
                    guarded(self._nlu_handler_fn),
                ),
                group=1,
            )
            logger.info("[registry] NLU MessageHandler registered")

    def reload(self, skill_name: str) -> bool:
        """
        Hot-reload a single skill. Re-imports handler.py and updates all
        function references in self._loaded.

        Returns True on success, False on failure.

        Caveats:
          - Telegram CommandHandler objects already bound to the Application
            are not replaced. The registered closures call through to the
            module-level functions, so logic changes take effect immediately.
          - New or removed commands require a bot restart to take effect in
            Telegram routing.
        """
        skill_dir = self.skills_dir / skill_name
        if not skill_dir.exists():
            logger.warning(f"[registry] reload: '{skill_name}' directory not found")
            return False

        try:
            # Evict old state so _load_skill rebuilds cleanly
            old_cmds = set()
            if skill_name in self._loaded:
                old_cmds = {c for c in self._loaded[skill_name]["handlers"]}
                del self._loaded[skill_name]
            if skill_name in self._failed:
                del self._failed[skill_name]

            # Trim bot_commands list
            self._bot_commands = [
                bc for bc in self._bot_commands if bc.command not in old_cmds
            ]

            self._load_skill(skill_dir)
            logger.info(f"[registry] ✓ Reloaded '{skill_name}'")
            return True
        except Exception as exc:
            self._failed[skill_name] = str(exc)
            logger.error(f"[registry] ✗ Reload failed for '{skill_name}': {exc}")
            return False

    # ── Introspection ──────────────────────────────────────────────────────────

    @property
    def bot_commands(self) -> list[BotCommand]:
        """Flat list of BotCommand objects for all loaded skills."""
        return list(self._bot_commands)

    def list_skills(self) -> list[dict]:
        """Return summary dicts for all loaded skills."""
        return [
            {
                "name":        name,
                "version":     skill["meta"].get("version", "?"),
                "commands":    list(skill["handlers"]),
                "description": skill["meta"].get("description", ""),
            }
            for name, skill in self._loaded.items()
        ]

    def __repr__(self) -> str:
        ok   = list(self._loaded)
        fail = list(self._failed)
        return f"<SkillRegistry loaded={ok} failed={fail}>"

    # ── Internal ───────────────────────────────────────────────────────────────

    def _load_skill(self, skill_dir: Path) -> None:
        name = skill_dir.name
        handler_path = skill_dir / "handler.py"
        json_path    = skill_dir / "skill.json"

        if not json_path.exists():
            raise FileNotFoundError(f"skill.json not found in {skill_dir}")
        if not handler_path.exists():
            raise FileNotFoundError(f"handler.py not found in {skill_dir}")

        # Parse metadata
        meta: dict = json.loads(json_path.read_text())
        if meta.get("name") != name:
            logger.warning(
                f"[registry] '{name}': skill.json name '{meta.get('name')}' "
                f"does not match folder name — using folder name"
            )

        # Import handler module via spec so it works regardless of sys.path
        spec   = importlib.util.spec_from_file_location(
            f"skills.{name}.handler", handler_path
        )
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        # Resolve command → handler function mappings
        handlers: dict[str, dict] = {}
        for cmd_def in meta.get("commands", []):
            command  = cmd_def.get("command", "")
            fn_name  = cmd_def.get("handler", f"{command}_handler")  # convention fallback
            fn       = getattr(module, fn_name, None)
            if fn is None:
                raise AttributeError(
                    f"handler.py for skill '{name}' has no function '{fn_name}' "
                    f"(required for command /{command})"
                )
            handlers[command] = {
                "fn":          fn,
                "description": cmd_def.get("description", ""),
                "guarded":     cmd_def.get("guarded", True),
            }
            self._bot_commands.append(BotCommand(command, cmd_def.get("description", "")))

        # NLU support — optional
        nlu_handler_name = meta.get("nlu_handler")
        if nlu_handler_name:
            nlu_fn = getattr(module, nlu_handler_name, None)
            if nlu_fn is None:
                raise AttributeError(
                    f"skill '{name}' declares nlu_handler='{nlu_handler_name}' "
                    f"but handler.py has no such function"
                )
            extract_fn = getattr(module, "_extract_nlu_query", None)
            if extract_fn is None:
                raise AttributeError(
                    f"skill '{name}' has nlu_handler but handler.py does not "
                    f"expose '_extract_nlu_query(text) → str | None'"
                )
            # Only one NLU handler is supported (last one wins if multiple skills declare it)
            self._nlu_handler_fn = nlu_fn
            self._nlu_extract_fn = extract_fn

        self._loaded[name] = {"meta": meta, "module": module, "handlers": handlers}

        cmd_names = list(handlers)
        nlu_note  = " + NLU" if nlu_handler_name else ""
        logger.info(f"[registry] ✓ '{name}' v{meta.get('version','?')} — {cmd_names}{nlu_note}")
