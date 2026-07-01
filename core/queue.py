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
    """Generate dual embeddings: paper_content (papers table) and episode_content (R2 script). Non-fatal."""
    import json as _json
    import os
    from openai import AsyncOpenAI
    from core.db import get_episode_papers, upsert_episode_embedding

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set — skipping embeddings for %s", episode_id)
        return

    EMBEDDING_MODEL = "text-embedding-3-small"
    MAX_CHARS = 30_000  # safe ceiling below the 8,192-token context limit

    params = manifest.get("parameters") or {}
    topic = params.get("topic", "")
    openai_client = AsyncOpenAI(api_key=api_key)

    # --- paper_content embedding ---
    try:
        papers = get_episode_papers(episode_id, db_url)
        if papers:
            sections = [
                f"{p['title']}: {p.get('abstract_snippet') or ''}"
                for p in papers
            ]
            paper_text = (f"{topic}\n\n" + "\n\n".join(sections))[:MAX_CHARS]
            resp = await openai_client.embeddings.create(model=EMBEDDING_MODEL, input=paper_text)
            upsert_episode_embedding(episode_id, "paper_content", resp.data[0].embedding, EMBEDDING_MODEL, db_url)
            logger.info("paper_content embedding stored for episode %s", episode_id)
    except Exception as exc:
        logger.warning("paper_content embedding failed for %s: %s", episode_id, exc)

    # --- episode_content embedding ---
    r2_account_id = os.getenv("R2_ACCOUNT_ID")
    r2_access_key = os.getenv("R2_ACCESS_KEY_ID")
    r2_secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    r2_bucket     = os.getenv("R2_BUCKET_NAME")

    if not all([r2_account_id, r2_access_key, r2_secret_key, r2_bucket]):
        logger.warning("R2 env vars not set — skipping episode_content embedding for %s", episode_id)
        return

    try:
        import boto3
        s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=r2_access_key,
            aws_secret_access_key=r2_secret_key,
            region_name="auto",
        )
        obj = s3.get_object(Bucket=r2_bucket, Key=f"episodes/{episode_id}/script.json")
        script = _json.loads(obj["Body"].read())
        turns = script.get("turns") or []
        dialogue = " ".join(t["text"] for t in turns if t.get("text"))
        dialogue = dialogue[:MAX_CHARS]
        if dialogue:
            resp = await openai_client.embeddings.create(model=EMBEDDING_MODEL, input=dialogue)
            upsert_episode_embedding(episode_id, "episode_content", resp.data[0].embedding, EMBEDDING_MODEL, db_url)
            logger.info("episode_content embedding stored for episode %s", episode_id)
    except Exception as exc:
        logger.warning("episode_content embedding failed for %s: %s", episode_id, exc)


@app.task(name="generate_episode", retry=procrastinate.RetryStrategy(max_attempts=1))
async def generate_episode(query_dict: dict, episode_id: str) -> None:
    """Run the full pipeline for one episode. Executed by the worker process."""
    import json
    from agents.orchestrator import _WarningCapture, _build_manifest, _persist_backends, run_pipeline
    from core.config import DATA_DIR, VOICE_PROVIDER
    from core.db import update_episode_status
    from core.models import QueryParameters

    db_url = os.getenv("DATABASE_URL")

    def _on_stage(stage: str) -> None:
        if db_url:
            try:
                update_episode_status(episode_id, stage, db_url)
            except Exception as exc:
                logger.warning("Failed to set episode %s status to %s: %s", episode_id, stage, exc)

    _on_stage("planning")

    warning_capture = _WarningCapture()
    logging.getLogger().addHandler(warning_capture)
    t_start = time.time()

    try:
        query = QueryParameters.model_validate(query_dict)
        episode, usage, tts_chars, tts_provider_used, stage_times, segments = await run_pipeline(
            query, episode_id, warning_capture=warning_capture, on_stage_start=_on_stage
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
