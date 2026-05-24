"""
notebooklm_client.py — async wrapper around the unofficial `notebooklm`
library (PyPI: notebooklm-py, import: notebooklm), tuned for WorkHive's
video marketing pipeline.

API verified against notebooklm-py 0.4.1 (2026-05-24) — every method on
NotebooksAPI / SourcesAPI / ArtifactsAPI is an async coroutine, and
NotebookLMClient is itself an async context manager.

Why this layer exists:
  * `notebooklm-py` uses undocumented Google APIs that can drift; isolating
    that risk here means the Flask app + CLI never imports it directly.
  * Output paths follow the existing .tmp/ convention so the dashboard's
    asset browser can pick them up without further wiring.
  * One open-client-per-call keeps the auth lifecycle simple — the lib
    handles cookie refresh internally on each new context.

Reference: https://github.com/teng-lin/notebooklm-py
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

# ── Output convention ─────────────────────────────────────────────────────────

OUT_ROOT      = Path(".tmp/notebooklm")
INDEX_FILE    = OUT_ROOT / "_index.json"

DEFAULT_PROFILE   = os.getenv("NOTEBOOKLM_PROFILE", "default")
DEFAULT_SESSION   = Path.home() / ".notebooklm" / "profiles" / DEFAULT_PROFILE / "storage_state.json"
SESSION_OVERRIDE  = os.getenv("NOTEBOOKLM_STORAGE_STATE")


# ── Lazy import + capability flag ─────────────────────────────────────────────

_NLM = None
_NLM_IMPORT_ERROR = None


def _try_import():
    global _NLM, _NLM_IMPORT_ERROR
    if _NLM is not None:
        return True, None
    try:
        import notebooklm as nlm  # type: ignore
        _NLM = nlm
        return True, None
    except ImportError as exc:
        _NLM_IMPORT_ERROR = str(exc)
        return False, _NLM_IMPORT_ERROR
    except Exception as exc:                                # noqa: BLE001
        _NLM_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
        return False, _NLM_IMPORT_ERROR


def is_available() -> bool:
    ok, _ = _try_import()
    return ok


def storage_state_path() -> Path:
    if SESSION_OVERRIDE:
        return Path(SESSION_OVERRIDE)
    return DEFAULT_SESSION


def has_session() -> bool:
    p = storage_state_path()
    return p.exists() and p.stat().st_size > 0


def availability_report() -> dict:
    ok, err = _try_import()
    session = storage_state_path()
    ver = None
    if ok:
        v = getattr(_NLM, "version", None)
        try:
            ver = v() if callable(v) else v
        except Exception:                                       # noqa: BLE001
            ver = "?"
    return {
        "library_installed":  ok,
        "library_error":      err,
        "library_version":    ver,
        "session_file_path":  str(session),
        "session_file_ready": session.exists() and session.stat().st_size > 0,
        "output_root":        str(OUT_ROOT),
        "profile":            DEFAULT_PROFILE,
    }


# ── Enums — resolve real values, fall back to None if lib drifts ──────────────

def _enum(cls_name: str, member: str):
    """Look up `notebooklm.<cls_name>.<member>`. Returns None on miss so the
    lib falls back to its own default."""
    ok, _ = _try_import()
    if not ok:
        return None
    cls = getattr(_NLM, cls_name, None)
    if cls is None:
        return None
    return getattr(cls, member, None)


# ── Index helpers ─────────────────────────────────────────────────────────────

def _load_index() -> dict:
    if not INDEX_FILE.exists():
        return {}
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_index(idx: dict) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")


def get_notebook_id(idea_id: str) -> Optional[str]:
    return (_load_index().get(idea_id) or {}).get("notebook_id")


def remember_notebook(idea_id: str, notebook_id: str, title: str) -> None:
    idx   = _load_index()
    entry = idx.setdefault(idea_id, {})
    entry["notebook_id"] = notebook_id
    entry["title"]       = title
    entry["created_at"]  = entry.get("created_at") or time.time()
    entry["updated_at"]  = time.time()
    _save_index(idx)


def remember_artifact(idea_id: str, kind: str, file_path: Path, meta: dict | None = None) -> None:
    idx       = _load_index()
    entry     = idx.setdefault(idea_id, {})
    artifacts = entry.setdefault("artifacts", {})
    artifacts[kind] = {
        "file":       str(file_path),
        "size_bytes": file_path.stat().st_size if file_path.exists() else 0,
        "generated":  time.time(),
        "meta":       meta or {},
    }
    entry["updated_at"] = time.time()
    _save_index(idx)


def workspace_for(idea_id: str) -> Path:
    p = OUT_ROOT / idea_id
    p.mkdir(parents=True, exist_ok=True)
    (p / "sources").mkdir(exist_ok=True)
    (p / "artifacts").mkdir(exist_ok=True)
    return p


# ── Client open ───────────────────────────────────────────────────────────────

async def _open_client():
    """Open a NotebookLMClient via async context. Caller must `async with`
    the returned object."""
    ok, err = _try_import()
    if not ok:
        raise RuntimeError(
            f"notebooklm-py not installed: {err}. "
            "Run notebooklm_setup.bat or `pip install notebooklm-py`."
        )
    if not has_session():
        raise RuntimeError(
            f"NotebookLM session missing at {storage_state_path()}. "
            "Run `notebooklm login` first (opens a browser to sign in)."
        )
    cls = _NLM.NotebookLMClient
    if SESSION_OVERRIDE:
        return await cls.from_storage(path=SESSION_OVERRIDE)
    return await cls.from_storage(profile=DEFAULT_PROFILE)


# ── Public artifact API ───────────────────────────────────────────────────────

@dataclass
class ArtifactRequest:
    """Normalised request shape used by the orchestrator + Flask layer."""
    kind:          str
    language:      str = "en"
    instructions:  str = ""
    audio_format:  str = "DEEP_DIVE"
    audio_length:  str = "DEFAULT"
    # If voice_key is set on an `audio` kind, we bypass NotebookLM's native
    # 2-host audio (American accent, no customization) and instead:
    #   1) ask NotebookLM for a CUSTOM podcast-monologue script (text)
    #   2) re-voice via tools/tts_engine.py with the requested Edge TTS voice
    # Valid keys come from video_marketing_app/app.py VOICE_OPTIONS:
    #   james / rosa  (PH English)
    #   angelo / blessica  (Filipino)
    #   guy / jenny / ryan (US/UK English)
    voice_key:     str = ""
    video_format:  str = "EXPLAINER"
    video_style:   str = "AUTO_SELECT"
    report_format: str = "BLOG_POST"
    custom_prompt: str = ""
    extras:        dict = field(default_factory=dict)


# Voice ID lookup mirrors the dashboard's VOICE_OPTIONS so the
# notebooklm_campaign module doesn't need to import Flask code.
_VOICE_ID_MAP = {
    "james":    "en-PH-JamesNeural",
    "rosa":     "en-PH-RosaNeural",
    "guy":      "en-US-GuyNeural",
    "jenny":    "en-US-JennyNeural",
    "ryan":     "en-GB-RyanNeural",
    "angelo":   "fil-PH-AngeloNeural",
    "blessica": "fil-PH-BlessicaNeural",
}


def _clean_script_for_tts(markdown: str) -> str:
    """Strip Markdown formatting and any leading meta-lines so the result is
    pure spoken text safe to feed Edge TTS."""
    import re as _re
    text = markdown

    # Remove fenced code blocks entirely.
    text = _re.sub(r"```[\s\S]*?```", "", text)
    # Drop horizontal rules.
    text = _re.sub(r"^\s*[-*_]{3,}\s*$", "", text, flags=_re.MULTILINE)
    # Drop ATX headers (## ...).
    text = _re.sub(r"^\s*#{1,6}\s*", "", text, flags=_re.MULTILINE)
    # Drop bullet/number list markers, keep content.
    text = _re.sub(r"^\s*[-*+]\s+", "", text, flags=_re.MULTILINE)
    text = _re.sub(r"^\s*\d+\.\s+", "", text, flags=_re.MULTILINE)
    # Strip bold/italic markers but keep words.
    text = _re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = _re.sub(r"\*([^*]+)\*", r"\1", text)
    text = _re.sub(r"__([^_]+)__", r"\1", text)
    text = _re.sub(r"_([^_]+)_", r"\1", text)
    # Strip inline code backticks.
    text = _re.sub(r"`([^`]+)`", r"\1", text)
    # Collapse multiple blank lines.
    text = _re.sub(r"\n{3,}", "\n\n", text)
    # Strip leading bracket-tags like [SPEAKER 1] or [music swell].
    text = _re.sub(r"^\s*\[[^\]]+\]\s*", "", text, flags=_re.MULTILINE)
    return text.strip()


async def generate_audio_local_voice(
    idea_id: str, notebook_id: str, req: ArtifactRequest, timeout: int = 600,
) -> Path:
    """Two-phase audio: NotebookLM produces a podcast monologue script, then
    tools.tts_engine voices it locally with the requested Edge TTS voice."""
    if not req.voice_key:
        raise ValueError("voice_key is required for local-voice audio")
    voice_id = _VOICE_ID_MAP.get(req.voice_key)
    if not voice_id:
        raise ValueError(
            f"Unknown voice_key {req.voice_key!r}. Valid: {sorted(_VOICE_ID_MAP)}"
        )

    ws  = workspace_for(idea_id)
    suffix = f"_{req.audio_format.lower()}_{req.audio_length.lower()}_{req.voice_key}_{req.language}"
    script_out = ws / "artifacts" / f"{idea_id}_audio{suffix}_script.md"
    audio_out  = ws / "artifacts" / f"{idea_id}_audio{suffix}.mp3"

    # Phase 1 — ask NotebookLM for a podcast script (CUSTOM report).
    length_hint = {
        "SHORT":   "Aim for 250-400 words (60-90 seconds spoken).",
        "DEFAULT": "Aim for 700-1100 words (5-7 minutes spoken).",
        "LONG":    "Aim for 1600-2400 words (12-18 minutes spoken).",
    }.get(req.audio_length, "Aim for 700-1100 words.")

    fmt_hint = {
        "DEEP_DIVE": "deeply explore the topic, weave in concrete numbers and named features from the sources",
        "BRIEF":     "deliver a crisp, focused brief that lands one core message",
        "CRITIQUE":  "critically examine the topic, naming weaknesses and gaps from the sources",
        "DEBATE":    "lay out the two strongest competing positions before resolving with the WorkHive perspective",
    }.get(req.audio_format, "deliver the message")

    custom_prompt = (
        "Write a single-host podcast MONOLOGUE script in plain spoken English. "
        f"{fmt_hint}. {length_hint} "
        "Output ONLY the words the host would speak — continuous paragraphs, "
        "natural conversational rhythm. NO markdown, NO headings, NO bullets, "
        "NO stage directions, NO 'host:' tags, NO speaker labels, NO intro music notes. "
        "Anchor every claim in the uploaded sources. Open with a hook in the first sentence. "
        "Close with: 'Try WorkHive free at workhive ph dot com.' (spelled out, not as a URL)."
    )
    if req.instructions:
        custom_prompt += "\n\nAdditional guidance: " + req.instructions

    fmt_enum = _enum("ReportFormat", "CUSTOM")

    async with await _open_client() as client:
        status = await client.artifacts.generate_report(
            notebook_id,
            report_format = fmt_enum,
            language      = req.language,
            custom_prompt = custom_prompt,
        )
        await _wait_and_download(
            client, notebook_id, status,
            lambda nb, op: client.artifacts.download_report(nb, op),
            script_out, timeout,
        )

    script_md = script_out.read_text(encoding="utf-8")
    spoken    = _clean_script_for_tts(script_md)
    if not spoken:
        raise RuntimeError("NotebookLM returned an empty podcast script")

    # Phase 2 — synthesise with Edge TTS via the existing engine.
    from tools.tts_engine import generate_tts                  # local import keeps Flask boot lean
    audio_out.parent.mkdir(parents=True, exist_ok=True)
    generate_tts(spoken, voice_id, audio_out)

    remember_artifact(
        idea_id,
        f"audio:{req.audio_format}:{req.voice_key}:{req.language}",
        audio_out,
        meta={
            **req.__dict__,
            "voice_id":    voice_id,
            "script_file": str(script_out),
            "char_count":  len(spoken),
        },
    )
    return audio_out


async def ensure_notebook(idea_id: str, title: str) -> str:
    """Find or create the notebook for this idea. Returns notebook_id."""
    existing = get_notebook_id(idea_id)
    if existing:
        try:
            async with await _open_client() as client:
                nb = await client.notebooks.get(existing)
                if nb is not None:
                    return existing
        except Exception:
            pass

    async with await _open_client() as client:
        nb = await client.notebooks.create(title)
        notebook_id = getattr(nb, "id", None) or getattr(nb, "notebook_id", None) or str(nb)
        remember_notebook(idea_id, notebook_id, title)
        return notebook_id


async def upload_sources(notebook_id: str, source_paths: Iterable[Path], wait: bool = True) -> int:
    paths = [Path(p) for p in source_paths if Path(p).exists()]
    if not paths:
        return 0

    count = 0
    async with await _open_client() as client:
        for path in paths:
            try:
                await client.sources.add_file(notebook_id, str(path), wait=wait, wait_timeout=180.0)
                count += 1
            except Exception as exc:                               # noqa: BLE001
                print(f"  [upload] WARN failed on {path.name}: {type(exc).__name__}: {exc}")
    return count


async def _wait_and_download(
    client, notebook_id: str, status_obj, download_coro_factory, out_path: Path, timeout: int,
):
    """Block on wait_for_completion then download.

    `download_coro_factory` is a 2-arg callable returning an awaitable, e.g.
    `lambda nb,op: client.artifacts.download_audio(nb, op)`.

    For cinematic_video + infographic the lib's `wait_for_completion` can
    return prematurely (its internal task_id polling doesn't match what the
    download endpoint actually checks). Catch ArtifactNotReadyError on the
    download and back off — the artifact is being generated server-side
    even though our local state says "done".

    Also: the create call may return a `GenerationStatus` with status='failed'
    and an empty task_id when Google's side rejects the request (free-tier
    quota cap on Veo, region gates, transient backend errors). Detect that
    and surface the real error message instead of falling through to a
    confusing ArtifactNotReadyError.
    """
    import asyncio
    # Surface upfront-failed create calls — these have empty task_id and
    # is_failed=True. The lib's logger prints "CREATE_ARTIFACT failed" but
    # then returns a status object instead of raising.
    if getattr(status_obj, "is_failed", False) or getattr(status_obj, "status", "") == "failed":
        err = getattr(status_obj, "error", "") or "unknown failure"
        code = getattr(status_obj, "error_code", "") or ""
        raise RuntimeError(f"NotebookLM refused create: {err}" + (f" [{code}]" if code else ""))
    task_id = getattr(status_obj, "task_id", None) or getattr(status_obj, "id", None)
    if task_id:
        try:
            final = await client.artifacts.wait_for_completion(notebook_id, task_id, timeout=timeout)
            status = getattr(final, "status", "")
            done   = bool(getattr(final, "is_complete", False)) or status == "completed"
            if not done:
                err = getattr(final, "error", None) or status or "unknown"
                # Don't raise — fall through to download-retry, the lib's
                # poll may have given up before Google actually finished.
                print(f"  [wait] task {task_id} not flagged done ({err}); will retry download")
        except Exception as exc:                                 # noqa: BLE001
            # wait_for_completion can throw on its own internal timeouts.
            # Don't fail — fall through to download-retry.
            print(f"  [wait] task {task_id} wait_for_completion raised ({exc}); will retry download")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # The lib downloads to `<out>.tmp` and then `Path.rename` swaps it in.
    # On Windows, `rename` cannot overwrite an existing file, so a re-run
    # with the same output path fails with WinError 183. Pre-clean both
    # the final file and any stale temp from an aborted earlier attempt.
    def _clean():
        try:
            if out_path.exists():
                out_path.unlink()
            stale_tmp = out_path.with_suffix(out_path.suffix + ".tmp")
            if stale_tmp.exists():
                stale_tmp.unlink()
        except Exception:                                      # noqa: BLE001
            pass

    # Download with exponential backoff on ArtifactNotReadyError. Each
    # attempt re-cleans the target path because a previous failed attempt
    # may have left a .tmp file behind.
    delays = [10, 30, 60, 90, 120, 180, 240, 300, 300, 300]    # ~25min budget
    last_exc = None
    for attempt, delay in enumerate([0] + delays, start=1):
        if delay:
            print(f"  [download] artifact not ready yet, waiting {delay}s before retry {attempt}/{len(delays)+1}…")
            await asyncio.sleep(delay)
        _clean()
        try:
            result_path = await download_coro_factory(notebook_id, str(out_path))
            return Path(result_path) if result_path else out_path
        except Exception as exc:                                # noqa: BLE001
            # Only retry on "not ready" — other errors are real failures.
            cls_name = type(exc).__name__
            if cls_name == "ArtifactNotReadyError":
                last_exc = exc
                continue
            raise
    raise RuntimeError(f"Artifact still not ready after retries: {last_exc}")


# ── Per-kind generators ───────────────────────────────────────────────────────

async def generate_audio(idea_id: str, notebook_id: str, req: ArtifactRequest, timeout: int = 900) -> Path:
    ws  = workspace_for(idea_id)
    suffix = f"_{req.audio_format.lower()}_{req.audio_length.lower()}_{req.language}"
    # NotebookLM Studio delivers audio in MP4 container (ftyp/moov atoms)
    # even though older docs called it "mp3". Use .m4a so OS players honour
    # the actual format and don't refuse to play it.
    out = ws / "artifacts" / f"{idea_id}_audio{suffix}.m4a"

    async with await _open_client() as client:
        status = await client.artifacts.generate_audio(
            notebook_id,
            language     = req.language,
            instructions = req.instructions or None,
            audio_format = _enum("AudioFormat", req.audio_format),
            audio_length = _enum("AudioLength", req.audio_length),
        )
        out_path = await _wait_and_download(
            client, notebook_id, status,
            lambda nb, op: client.artifacts.download_audio(nb, op),
            out, timeout,
        )
    remember_artifact(idea_id, f"audio:{req.audio_format}:{req.language}", out_path, meta=req.__dict__)
    return out_path


async def generate_video(idea_id: str, notebook_id: str, req: ArtifactRequest, timeout: int = 1800) -> Path:
    ws  = workspace_for(idea_id)
    suffix = f"_{req.video_format.lower()}_{req.video_style.lower()}_{req.language}"
    out = ws / "artifacts" / f"{idea_id}_video{suffix}.mp4"

    async with await _open_client() as client:
        status = await client.artifacts.generate_video(
            notebook_id,
            language     = req.language,
            instructions = req.instructions or None,
            video_format = _enum("VideoFormat", req.video_format),
            video_style  = _enum("VideoStyle",  req.video_style),
        )
        out_path = await _wait_and_download(
            client, notebook_id, status,
            lambda nb, op: client.artifacts.download_video(nb, op),
            out, timeout,
        )
    remember_artifact(idea_id, f"video:{req.video_format}:{req.video_style}:{req.language}", out_path, meta=req.__dict__)
    return out_path


async def generate_cinematic_video(idea_id: str, notebook_id: str, req: ArtifactRequest, timeout: int = 1800) -> Path:
    ws  = workspace_for(idea_id)
    out = ws / "artifacts" / f"{idea_id}_cinematic_{req.language}.mp4"

    async with await _open_client() as client:
        status = await client.artifacts.generate_cinematic_video(
            notebook_id,
            language     = req.language,
            instructions = req.instructions or None,
        )
        # If a dedicated download_cinematic_video isn't exposed, the lib uses
        # the same download_video endpoint with cinematic artifacts.
        download = (
            getattr(client.artifacts, "download_cinematic_video", None)
            or client.artifacts.download_video
        )
        out_path = await _wait_and_download(
            client, notebook_id, status,
            lambda nb, op: download(nb, op),
            out, timeout,
        )
    remember_artifact(idea_id, f"cinematic:{req.language}", out_path, meta=req.__dict__)
    return out_path


async def generate_report(idea_id: str, notebook_id: str, req: ArtifactRequest, timeout: int = 600) -> Path:
    ws  = workspace_for(idea_id)
    out = ws / "artifacts" / f"{idea_id}_report_{req.report_format.lower()}_{req.language}.md"

    fmt_enum = _enum("ReportFormat", req.report_format)
    kwargs   = dict(
        language           = req.language,
        custom_prompt      = req.custom_prompt or None,
        extra_instructions = req.instructions or None,
    )
    if fmt_enum is not None:
        kwargs["report_format"] = fmt_enum

    async with await _open_client() as client:
        status = await client.artifacts.generate_report(notebook_id, **kwargs)
        out_path = await _wait_and_download(
            client, notebook_id, status,
            lambda nb, op: client.artifacts.download_report(nb, op),
            out, timeout,
        )
    remember_artifact(idea_id, f"report:{req.report_format}:{req.language}", out_path, meta=req.__dict__)
    return out_path


async def generate_study_guide(idea_id: str, notebook_id: str, req: ArtifactRequest, timeout: int = 600) -> Path:
    ws  = workspace_for(idea_id)
    out = ws / "artifacts" / f"{idea_id}_study_guide_{req.language}.md"

    async with await _open_client() as client:
        status = await client.artifacts.generate_study_guide(
            notebook_id,
            language           = req.language,
            extra_instructions = req.instructions or None,
        )
        out_path = await _wait_and_download(
            client, notebook_id, status,
            lambda nb, op: client.artifacts.download_report(nb, op),
            out, timeout,
        )
    remember_artifact(idea_id, f"study_guide:{req.language}", out_path, meta=req.__dict__)
    return out_path


async def generate_slides(idea_id: str, notebook_id: str, req: ArtifactRequest, timeout: int = 900) -> Path:
    ws  = workspace_for(idea_id)
    out = ws / "artifacts" / f"{idea_id}_slides_{req.language}.pptx"

    async with await _open_client() as client:
        status = await client.artifacts.generate_slide_deck(
            notebook_id,
            language     = req.language,
            instructions = req.instructions or None,
        )
        out_path = await _wait_and_download(
            client, notebook_id, status,
            lambda nb, op: client.artifacts.download_slide_deck(nb, op, output_format="pptx"),
            out, timeout,
        )
    remember_artifact(idea_id, f"slides:{req.language}", out_path, meta=req.__dict__)
    return out_path


async def generate_infographic(idea_id: str, notebook_id: str, req: ArtifactRequest, timeout: int = 600) -> Path:
    ws  = workspace_for(idea_id)
    out = ws / "artifacts" / f"{idea_id}_infographic_{req.language}.png"

    async with await _open_client() as client:
        status = await client.artifacts.generate_infographic(
            notebook_id,
            language     = req.language,
            instructions = req.instructions or None,
        )
        out_path = await _wait_and_download(
            client, notebook_id, status,
            lambda nb, op: client.artifacts.download_infographic(nb, op),
            out, timeout,
        )
    remember_artifact(idea_id, f"infographic:{req.language}", out_path, meta=req.__dict__)
    return out_path


async def generate_mind_map(idea_id: str, notebook_id: str, req: ArtifactRequest) -> Path:
    """Returns JSON inline (no task to poll) per the lib's API."""
    ws  = workspace_for(idea_id)
    out = ws / "artifacts" / f"{idea_id}_mindmap.json"

    async with await _open_client() as client:
        result = await client.artifacts.generate_mind_map(
            notebook_id,
            language     = req.language,
            instructions = req.instructions or None,
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    remember_artifact(idea_id, "mindmap", out, meta=req.__dict__)
    return out


# ── Dispatch by kind ──────────────────────────────────────────────────────────

_DISPATCH = {
    "audio":       generate_audio,
    "video":       generate_video,
    "cinematic":   generate_cinematic_video,
    "slides":      generate_slides,
    "infographic": generate_infographic,
    "mindmap":     generate_mind_map,
    "blog":        generate_report,
    "briefing":    generate_report,
    "study":       generate_study_guide,
}


async def generate(kind: str, idea_id: str, notebook_id: str, req: ArtifactRequest) -> Path:
    """Dispatch to the right generator. For `audio` with `voice_key` set,
    route to the local-voice path (NotebookLM script → Edge TTS) instead of
    NotebookLM's fixed 2-host American audio."""
    if kind == "audio" and req.voice_key:
        return await generate_audio_local_voice(idea_id, notebook_id, req)

    fn = _DISPATCH.get(kind)
    if fn is None:
        raise ValueError(f"Unknown artifact kind: {kind!r}. Valid: {sorted(_DISPATCH.keys())}")
    if kind == "blog":
        req.report_format = "BLOG_POST"
    elif kind == "briefing":
        req.report_format = "BRIEFING_DOC"
    return await fn(idea_id, notebook_id, req)
