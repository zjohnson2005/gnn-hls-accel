"""Live OpenAI generation for CAP-01 offline candidate pools."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping

from .contracts import CandidateRecord, TaskRecord, canonical_json_bytes, sha256_json
from .pool import PoolWriter

DEFAULT_PROMPT_TEMPLATE = """Solve the task below. Return only the proposed answer.

Domain: {domain}
Task:
{prompt}
"""

GenerationRequest = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class GenerationError(RuntimeError):
    """Raised when candidate generation cannot produce a valid record."""


@dataclass(frozen=True)
class GenerationConfig:
    model: str
    temperature: float = 1.0
    max_completion_tokens: int = 4096
    target_candidates: int = 2048
    prompt_template: str = DEFAULT_PROMPT_TEMPLATE
    prompt_templates: Mapping[str, str] = field(default_factory=dict)
    endpoint: str = "https://api.openai.com/v1/chat/completions"
    timeout_seconds: float = 120.0

    def validate(self) -> None:
        if not self.model:
            raise ValueError("generation model is required")
        if self.target_candidates < 1:
            raise ValueError("target_candidates must be positive")
        if self.max_completion_tokens < 1:
            raise ValueError("max_completion_tokens must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        templates = self.resolved_prompt_templates()
        for domain, template in templates.items():
            if "{prompt}" not in template or "{domain}" not in template:
                raise ValueError(
                    f"prompt template for {domain} must include "
                    "{{domain}} and {{prompt}}"
                )
            lowered = template.lower()
            forbidden = ("harness", "wall_budget", "latency_scale", "langgraph")
            if any(term in lowered for term in forbidden):
                raise ValueError(
                    f"generation prompt template for {domain} is not blind to "
                    "the harness"
                )

    def resolved_prompt_templates(self) -> dict[str, str]:
        if self.prompt_templates:
            return {str(domain): str(template) for domain, template in self.prompt_templates.items()}
        return {"default": self.prompt_template}

    def template_for(self, domain: str) -> str:
        templates = self.resolved_prompt_templates()
        return templates.get(domain, templates.get("default", self.prompt_template))

    @property
    def prompt_template_sha256(self) -> str:
        return sha256_json({"templates": self.resolved_prompt_templates()})

    def public_dict(self) -> dict[str, Any]:
        """Return serializable generation provenance with no credentials."""
        payload = asdict(self)
        payload["prompt_templates"] = self.resolved_prompt_templates()
        payload["prompt_template_sha256"] = self.prompt_template_sha256
        return payload

    def digest(self) -> str:
        return sha256_json(self.public_dict())


def build_generation_prompt(
    task: TaskRecord,
    config: GenerationConfig,
) -> str:
    """Render only public task content, never verifier or harness details."""
    config.validate()
    return config.template_for(task.domain).format(domain=task.domain, prompt=task.prompt)


def _live_openai_request(
    payload: Mapping[str, Any],
    *,
    endpoint: str,
    timeout_seconds: float,
) -> Mapping[str, Any]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise GenerationError("OPENAI_API_KEY is not set in the environment")
    body = canonical_json_bytes(payload)
    request = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            result = json.loads(response.read())
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        raise GenerationError(f"OpenAI generation request failed: {exc}") from exc
    if not isinstance(result, dict):
        raise GenerationError("OpenAI response is not a JSON object")
    return result


def _parse_response(response: Mapping[str, Any]) -> tuple[str, int, int, str | None]:
    try:
        choices = response["choices"]
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError("exactly one completion is required per request")
        choice = choices[0]
        content = choice["message"]["content"]
        usage = response["usage"]
        prompt_tokens = int(usage["prompt_tokens"])
        completion_tokens = int(usage["completion_tokens"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GenerationError("OpenAI response lacks candidate token provenance") from exc
    if not isinstance(content, str) or not content.strip():
        raise GenerationError("OpenAI returned an empty candidate")
    if prompt_tokens < 0 or completion_tokens < 0:
        raise GenerationError("OpenAI returned negative token usage")
    request_id = response.get("id")
    return (
        content,
        prompt_tokens,
        completion_tokens,
        str(request_id) if request_id is not None else None,
    )


def generate_task_pool(
    task: TaskRecord,
    writer: PoolWriter,
    config: GenerationConfig,
    *,
    request_fn: GenerationRequest | None = None,
) -> tuple[CandidateRecord, ...]:
    """Resume and complete one offline pool using one traceable request per candidate."""
    task.validate()
    config.validate()
    if writer.task_id != task.task_id:
        raise ValueError("writer task_id does not match task")
    prompt = build_generation_prompt(task, config)
    requester = request_fn
    while writer.count < config.target_candidates:
        payload: dict[str, Any] = {
            "model": config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config.temperature,
            "max_completion_tokens": config.max_completion_tokens,
            "n": 1,
        }
        response = (
            requester(payload)
            if requester is not None
            else _live_openai_request(
                payload,
                endpoint=config.endpoint,
                timeout_seconds=config.timeout_seconds,
            )
        )
        content, prompt_tokens, completion_tokens, request_id = _parse_response(response)
        ordinal = writer.count
        candidate_id = "cand-" + sha256_json(
            {
                "task_id": task.task_id,
                "ordinal": ordinal,
                "model": config.model,
                "content": content,
            }
        )[:24]
        writer.append(
            CandidateRecord(
                candidate_id=candidate_id,
                task_id=task.task_id,
                ordinal=ordinal,
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                generation_request_id=request_id,
            )
        )
    return writer.candidates
