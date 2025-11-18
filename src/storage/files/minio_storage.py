"""MinIO storage for documents."""

import hashlib
import io
from typing import Optional

from minio import Minio
from minio.error import S3Error

from src.core.config import get_settings
from src.core.exceptions import FileStorageException
from src.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class MinIOStorage:
    """MinIO storage client for document files."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
        secure: Optional[bool] = None,
    ) -> None:
        """Initialize MinIO client.

        Args:
            endpoint: MinIO endpoint
            access_key: Access key
            secret_key: Secret key
            bucket: Bucket name
            secure: Use HTTPS
        """
        self.endpoint = endpoint or settings.minio_endpoint
        self.access_key = access_key or settings.minio_access_key
        self.secret_key = secret_key or settings.minio_secret_key
        self.bucket = bucket or settings.minio_bucket
        self.secure = secure if secure is not None else settings.minio_secure

        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
            logger.info("minio_client_initialized", endpoint=self.endpoint, bucket=self.bucket)
        except Exception as e:
            raise FileStorageException(f"Failed to initialize MinIO client: {e}") from e

    def ensure_bucket(self) -> None:
        """Ensure bucket exists, create if not."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info("minio_bucket_created", bucket=self.bucket)
            else:
                logger.debug("minio_bucket_exists", bucket=self.bucket)
        except S3Error as e:
            raise FileStorageException(f"Failed to ensure bucket: {e}") from e

    def upload_file(
        self,
        file_content: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
    ) -> tuple[str, str]:
        """Upload file to MinIO.

        Args:
            file_content: File content as bytes
            object_name: Object name in bucket
            content_type: MIME content type

        Returns:
            Tuple of (object_path, file_hash)

        Raises:
            FileStorageException: If upload fails
        """
        try:
            self.ensure_bucket()

            # Calculate file hash
            file_hash = hashlib.sha256(file_content).hexdigest()

            # Upload file
            file_stream = io.BytesIO(file_content)
            file_size = len(file_content)

            self.client.put_object(
                self.bucket,
                object_name,
                file_stream,
                file_size,
                content_type=content_type,
            )

            object_path = f"{self.bucket}/{object_name}"
            logger.info(
                "file_uploaded",
                object_path=object_path,
                size=file_size,
                hash=file_hash,
            )

            return object_path, file_hash

        except S3Error as e:
            logger.error("file_upload_failed", object_name=object_name, error=str(e))
            raise FileStorageException(f"Failed to upload file: {e}") from e

    def download_file(self, object_name: str) -> bytes:
        """Download file from MinIO.

        Args:
            object_name: Object name in bucket

        Returns:
            File content as bytes

        Raises:
            FileStorageException: If download fails
        """
        try:
            response = self.client.get_object(self.bucket, object_name)
            content = response.read()
            response.close()
            response.release_conn()

            logger.info("file_downloaded", object_name=object_name, size=len(content))
            return content

        except S3Error as e:
            logger.error("file_download_failed", object_name=object_name, error=str(e))
            raise FileStorageException(f"Failed to download file: {e}") from e

    def delete_file(self, object_name: str) -> None:
        """Delete file from MinIO.

        Args:
            object_name: Object name in bucket

        Raises:
            FileStorageException: If deletion fails
        """
        try:
            self.client.remove_object(self.bucket, object_name)
            logger.info("file_deleted", object_name=object_name)

        except S3Error as e:
            logger.error("file_deletion_failed", object_name=object_name, error=str(e))
            raise FileStorageException(f"Failed to delete file: {e}") from e

    def file_exists(self, object_name: str) -> bool:
        """Check if file exists in MinIO.

        Args:
            object_name: Object name in bucket

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except S3Error:
            return False

    def get_file_url(self, object_name: str, expires: int = 3600) -> str:
        """Get presigned URL for file.

        Args:
            object_name: Object name in bucket
            expires: URL expiration in seconds

        Returns:
            Presigned URL

        Raises:
            FileStorageException: If URL generation fails
        """
        try:
            from datetime import timedelta

            url = self.client.presigned_get_object(
                self.bucket,
                object_name,
                expires=timedelta(seconds=expires),
            )

            logger.debug("presigned_url_generated", object_name=object_name)
            return url

        except S3Error as e:
            logger.error("url_generation_failed", object_name=object_name, error=str(e))
            raise FileStorageException(f"Failed to generate URL: {e}") from e


def get_storage() -> MinIOStorage:
    """Get MinIO storage instance."""
    return MinIOStorage()
