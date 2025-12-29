from minio import Minio
import os
import io

class MinioHandler:
    def __init__(self, host="127.0.0.1", port="9000"):
        # Configuration matches your docker-compose.kafka.yml
        self.endpoint = f"{host}:{port}"
        self.access_key = "minio_access_key"
        self.secret_key = "minio_secret_key"
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=False
        )
        self.bucket_data = "product-data-lake"
        self.bucket_images = "product-images"
        self._ensure_bucket(self.bucket_data)
        self._ensure_bucket(self.bucket_images)

    def _ensure_bucket(self, bucket_name):
        if not self.client.bucket_exists(bucket_name):
            self.client.make_bucket(bucket_name)
            # Set policy to public read if needed, or rely on presigned/direct access
            print(f"Bucket '{bucket_name}' created.")

    def upload_parquet(self, data_frame, file_name):
        """
        Convert DataFrame to Parquet in-memory and upload to MinIO
        """
        try:
            # Convert DataFrame to Parquet buffer
            parquet_buffer = io.BytesIO()
            data_frame.to_parquet(parquet_buffer, index=False)
            parquet_buffer.seek(0) # Reset the cursor back to the start so MinIO can read from the beginning
            
            # Upload
            self.client.put_object(
                self.bucket_data,
                file_name,
                parquet_buffer,
                length=parquet_buffer.getbuffer().nbytes,
                content_type="application/octet-stream"
            )
            print(f"Uploaded {file_name} to MinIO.")
        except Exception as e:
            print(f"Failed to upload to MinIO: {e}")
    
    def upload_file(self, file_path, object_name):
        """
        Upload a local file to the MinIO Image Bucket and return the URL
        """
        try:
            self.client.fput_object(
                self.bucket_images,
                object_name,
                file_path,
                content_type="image/jpeg" # Assuming JPEGs based on script
            )
            # Construct URL (assuming localhost access)
            url = f"http://{self.endpoint}/{self.bucket_images}/{object_name}"
            return url
        except Exception as e:
            print(f"Failed to upload file {file_path}: {e}")
            return None