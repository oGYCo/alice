"""Prompt template management using Jinja2."""

from pathlib import Path

import jinja2

# Development layout:  <repo>/src/alice/prompts.py  →  <repo>/prompts/
# Docker (uv install): /app/.venv/lib/.../alice/prompts.py  →  /app/prompts/
_src_relative = Path(__file__).parent.parent.parent / "prompts"
PROMPTS_DIR = _src_relative if _src_relative.exists() else Path("/app/prompts")


class PromptManager:
    """Load and render Jinja2 prompt templates."""

    def __init__(self, prompts_dir: Path | None = None):
        self._dir = prompts_dir or PROMPTS_DIR
        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self._dir)),
            autoescape=False,  # LLM prompts don't need HTML escaping
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, **kwargs: object) -> str:
        """Render a template with the given variables."""
        if not template_name.endswith(".j2"):
            template_name = f"{template_name}.j2"
        template = self._env.get_template(template_name)
        return template.render(**kwargs)

    def render_gatekeeper(self, title: str, text: str, source: str = "") -> str:
        return self.render("gatekeeper", title=title, text=text, source=source)

    def render_understanding(
        self, title: str, text: str, language: str = "en", source: str = ""
    ) -> str:
        return self.render(
            "understanding", title=title, text=text, language=language, source=source
        )

    def render_quality_score(self, title: str, summary: str, key_points: list[str]) -> str:
        return self.render("quality_score", title=title, summary=summary, key_points=key_points)

    def render_push_reason(
        self,
        title: str,
        summary: str,
        key_points: list[str],
        domains: list[str],
        user_profile: str = "",
    ) -> str:
        return self.render(
            "push_reason",
            title=title,
            summary=summary,
            key_points=key_points,
            domains=domains,
            user_profile=user_profile,
        )


# Module-level singleton
prompt_manager = PromptManager()
