"""
Object store MinIO (S3-compatible) para artefactos de lote.
"""
from __future__ import annotations

import io

from minio import Minio


class MinioObjectStore:
    def __init__(self, endpoint: str, access_key: str, secret_key: str,
                 bucket: str, secure: bool = False) -> None:
        self._client = Minio(endpoint, access_key=access_key,
                             secret_key=secret_key, secure=secure)
        self._bucket = bucket
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)

    def put(self, key: str, data: bytes, content_type: str = "application/json") -> str:
        self._client.put_object(self._bucket, key, io.BytesIO(data),
                                length=len(data), content_type=content_type)
        return f"s3://{self._bucket}/{key}"

    def get(self, key: str) -> bytes:
        response = self._client.get_object(self._bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
