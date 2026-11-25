"""VLM requests, constrained output, and unchanged AsgardBench parser adapter."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys

import httpx

from .artifacts import save
from .navigation import NAVIGATION

sys.dont_write_bytecode = True
ASGARDBENCH_DIR = Path(os.environ.get(
    "ASGARDBENCH_DIR", str(Path(__file__).resolve().parents[4] / "AsgardBench")
)).expanduser().resolve()
sys.path.insert(0, str(ASGARDBENCH_DIR))
from AsgardBench.Model.prompt_templates import PromptParams, render_prompt, extract_action_object
from AsgardBench.Utils.config_utils import EvaluationConfig


class OutputValidationError(ValueError):
    def __init__(self, message, response="", usage=None):
        super().__init__(message)
        self.response = response
        self.usage = usage or {}


def output_schema(choices):
    return {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": list(choices)},
            "object": {"type": "string", "enum": sorted({name for names in choices.values() for name in names})},
        },
        "required": ["action", "object"], "additionalProperties": False,
    }


def decode_response_object(raw, required):
    if not raw.get("done") or raw.get("done_reason") != "stop":
        raise ValueError("Model response did not finish normally")
    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"Duplicate JSON field: {key}")
            value[key] = item
        return value
    try:
        choice = json.loads(raw.get("message", {}).get("content", ""), object_pairs_hook=unique_pairs)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    if not isinstance(choice, dict) or set(choice) != set(required):
        raise ValueError("JSON must contain exactly " + " and ".join(required))
    return choice


def validate_response(raw, choices):
    choice = decode_response_object(raw, ("action", "object"))
    action, name = choice["action"], choice["object"]
    if not isinstance(action, str) or action not in choices:
        raise ValueError(f"Unsupported action: {action!r}; choose from {list(choices)}")
    if not isinstance(name, str) or name not in choices[action]:
        raise ValueError(f"Invalid object for {action}: {name!r}; choose from {choices[action]}")
    parser_text = f"Action: {action} {name}"
    # The external benchmark parser has no navigation actions. Navigation uses
    # the same strict JSON validation and an explicit local control adapter.
    if action in NAVIGATION:
        if name != "None":
            raise ValueError("Navigation requires object identifier None")
        return action, name, parser_text
    parsed_action, parsed_name, error = extract_action_object(parser_text, sorted({n for v in choices.values() for n in v}))
    if error or (parsed_action, parsed_name) != (action, name):
        raise ValueError(error or "Parser changed the supplied action/object")
    return action, name, parser_text


def make_prompt(task, choices, feedback):
    config = EvaluationConfig()
    names = sorted({name for values in choices.values() for name in values})
    prompt = render_prompt(PromptParams(
        mode="image", feedback_type=config.feedback_type.value,
        include_common_sense=config.include_common_sense, include_simulation=True,
        hand_transparency=config.hand_transparency,
        previous_image=config.previous_image.value, first_action=True,
        task_description=task, objects_in_scene=", ".join(names),
        action_history="", memories="", use_memory=config.use_memory,
        full_steps=config.full_steps, suggested_plan_sequence="",
    ))
    prompt += (
        "\n\nFINAL OUTPUT CONTRACT: Override the earlier response format. "
        "Return only a JSON object with required string fields action and object. "
        f"Legal objects BY ACTION: {json.dumps(choices)}. "
        "Use exact spelling, include both fields, and no extra fields or explanation. "
        "Choose the next action for the current task using the attached CURRENT image. "
        "Example tasks earlier in the prompt are not the current task. "
        "Follow the supplied JSON schema."
    )
    if feedback:
        prompt += "\n\nPREVIOUS ATTEMPT FEEDBACK (correct the error using the current image):\n"
        prompt += json.dumps(feedback)
    return prompt


class OllamaModel:
    def __init__(self, model="llava:7b", base_url="http://localhost:11434", request=None, prompt_builder=None):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.request = request or self._request
        self.prompt_builder = prompt_builder

    def _request(self, body, folder):
        with httpx.Client(timeout=600, transport=httpx.HTTPTransport(retries=0)) as client:
            response = client.post(f"{self.base_url}/api/chat", json=body)
            (folder / "raw_response.json").write_text(response.text)
            response.raise_for_status()
            try:
                raw = response.json()
            except ValueError as exc:
                raise RuntimeError("Ollama returned invalid response JSON") from exc
            if raw.get("error"):
                raise RuntimeError(raw["error"])
            return raw

    def image_response(self, prompt, schema, folder):
        """Send one image with a caller-owned schema and preserve request evidence."""
        (folder / "prompt.txt").write_text(prompt + "\n")
        image_bytes = (folder / "before.png").read_bytes()
        body = {"model": self.model,
                "messages": [{"role": "user", "content": prompt,
                              "images": [base64.b64encode(image_bytes).decode()]}],
                "format": schema,
                "options": {"num_ctx": 16384, "num_predict": 1024, "temperature": 0, "top_p": 1},
                "stream": False, "keep_alive": "2m"}
        save(folder / "request.json", {**body, "messages": [{"role": "user", "content": prompt,
             "image_file": "before.png", "image_sha256": hashlib.sha256(image_bytes).hexdigest()}]})
        raw = self.request(body, folder)
        save(folder / "raw_response.json", raw)
        text = raw.get("message", {}).get("content", "")
        (folder / "response.txt").write_text(text)
        return raw

    def choose(self, task, choices, feedback, folder):
        prompt = (self.prompt_builder or make_prompt)(task, choices, feedback)
        raw = self.image_response(prompt, output_schema(choices), folder)
        text = raw.get("message", {}).get("content", "")
        usage = {key: raw.get(key) for key in ("prompt_eval_count", "eval_count", "done", "done_reason")}
        try:
            action, name, parser_text = validate_response(raw, choices)
        except ValueError as exc:
            raise OutputValidationError(str(exc), text, usage) from exc
        parsed = {"action": action, "object": name, "error": None, "parser_input": parser_text,
                  "parser": "local_navigation" if action in NAVIGATION else "asgardbench"}
        save(folder / "parsed_action.json", parsed)
        return {"model_response": text, "usage": usage, "parsed": parsed}
