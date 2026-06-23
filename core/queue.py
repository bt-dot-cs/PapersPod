import logging
import os
import time

import procrastinate

logger = logging.getLogger(__name__)

# DATABASE_URL must be in env before this module is imported.
# worker.py and web/app.py both call load_dotenv() first.
# Procrastinate uses LISTEN/NOTIFY which requires a direct connection —
# the pooled DATABASE_URL (PgBouncer transaction mode) does not support it.
_connector_url = os.getenv("DATABASE_URL_DIRECT") or os.getenv("DATABASE_URL", "")
app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(
        conninfo=_connector_url,
    ),
    import_paths=["core.queue"],
)


async def _embed_episode(episode_id: str, manifest: dict, db_url: str) -> None:
    """Embed topic + disciplines and store as script_embedding. Non-fatal."""
    import os
    from openai import AsyncOpenAI
    from core.db import store_script_embedding

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set — skipping embedding for %s", episode_id)
        return

    params = manifest.get("parameters") or {}
    topic = params.get("topic", "")
    disciplines = params.get("disciplines") or []
    text = f"{topic} | {', '.join(disciplines)}".strip(" |")
    if not text:
        return

    client = AsyncOpenAI(api_key=api_key)
    resp = await client.embeddings.create(model="text-embedding-3-small", input=text)
    store_script_embedding(episode_id, resp.data[0].embedding, db_url)
    logger.info("Embedded episode %s", episode_id)


@app.task(name="generate_episode", retry=procrastinate.RetryStrategy(max_attempts=1))
async def generate_episode(query_dict: dict, episode_id: str) -> None:
    """Run the full pipeline for one episode. Executed by the worker process."""
    import json
    from agents.orchestrator import _WarningCapture, _build_manifest, _persist_backends, run_pipeline
    from core.config import DATA_DIR, VOICE_PROVIDER
    from core.db import update_episode_status
    from core.models import QueryParameters

    db_url = os.getenv("DATABASE_URL")

    if db_url:
        try:
            update_episode_status(episode_id, "running", db_url)
        except Exception as exc:
            logger.warning("Failed to set episode %s running: %s", episode_id, exc)

    warning_capture = _WarningCapture()
    logging.getLogger().addHandler(warning_capture)
    t_start = time.time()

    try:
        query = QueryParameters.model_validate(query_dict)
        episode, usage, tts_chars, tts_provider_used, stage_times, segments = await run_pipeline(
            query, episode_id, warning_capture=warning_capture
        )
    except Exception as exc:
        logger.error("Episode %s failed: %s", episode_id, exc, exc_info=True)
        if db_url:
            try:
                update_episode_status(episode_id, "failed", db_url, error=str(exc))
            except Exception as dbe:
                logger.warning("DB status update failed: %s", dbe)
        raise
    finally:
        logging.getLogger().removeHandler(warning_capture)

    total_runtime = time.time() - t_start
    manifest = _build_manifest(
        episode_id, query, episode, usage, tts_chars,
        tts_provider_used, VOICE_PROVIDER,
        stage_times, total_runtime, warning_capture,
        segments=segments,
    )

    manifest_path = DATA_DIR / "traces" / f"{episode_id}_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    _persist_backends(manifest, episode_id, {
        "audio":        episode.audio_path,
        "script":       episode.script_path,
        "bibliography": episode.bibliography_path,
        "manifest":     manifest_path,
    })

    if db_url:
        try:
            update_episode_status(episode_id, "done", db_url, manifest=manifest)
        except Exception as exc:
            logger.warning("DB status update failed: %s", exc)

        try:
            await _embed_episode(episode_id, manifest, db_url)
        except Exception as exc:
            logger.warning("Embedding failed for episode %s: %s", episode_id, exc)

        try:
            from core.db import store_episode_papers
            store_episode_papers(episode_id, episode.papers, db_url)
        except Exception as exc:
            logger.warning("Paper storage failed for episode %s: %s", episode_id, exc)

    logger.info("Episode %s complete", episode_id)
