import logging
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

_CONTENT_TYPES: dict[str, str] = {
    ".mp3":  "audio/mpeg",
    ".json": "application/json",
    ".md":   "text/markdown",
}


def upload_episode_files(
    episode_id: str,
    files: dict[str, Path],
    account_id: str,
    access_key_id: str,
    secret_access_key: str,
    bucket_name: str,
) -> dict[str, str]:
    """Upload episode files to R2. Returns {label: object_key} for each successful upload."""
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name="auto",
    )
    uploaded: dict[str, str] = {}
    for label, path in files.items():
        path = Path(path)
        if not path.exists():
            logger.warning("R2 upload skipped — file not found: %s", path)
            continue
        key = f"episodes/{episode_id}/{label}{path.suffix}"
        content_type = _CONTENT_TYPES.get(path.suffix, "application/octet-stream")
        try:
            client.upload_file(
                str(path),
                bucket_name,
                key,
                ExtraArgs={"ContentType": content_type},
            )
            uploaded[label] = key
            logger.info("R2 uploaded: %s → %s", label, key)
        except (BotoCoreError, ClientError) as exc:
            logger.warning("R2 upload failed for %s: %s", label, exc)
    return uploaded


def get_presigned_audio_url(
    episode_id: str,
    account_id: str,
    access_key_id: str,
    secret_access_key: str,
    bucket_name: str,
    expires_in: int = 3600,
) -> str:
    """Return a presigned GET URL for the episode's audio file (valid for expires_in seconds)."""
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name="auto",
    )
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_name, "Key": f"episodes/{episode_id}/audio.mp3"},
        ExpiresIn=expires_in,
    )
