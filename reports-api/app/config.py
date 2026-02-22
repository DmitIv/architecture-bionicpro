import os


class Settings:
    def __init__(self):
        self.clickhouse_host = os.getenv("CLICKHOUSE_HOST", "clickhouse")
        self.clickhouse_port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
        self.clickhouse_user = os.getenv("CLICKHOUSE_USER", "default")
        self.clickhouse_password = os.getenv("CLICKHOUSE_PASSWORD", "")
        self.clickhouse_database = os.getenv("CLICKHOUSE_DATABASE", "default")

        self.keycloak_url = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
        self.keycloak_realm = os.getenv("KEYCLOAK_REALM", "bionicpro")

        # S3/MinIO Configuration
        self.s3_endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
        self.s3_access_key = os.getenv("S3_ACCESS_KEY", "minioadmin")
        self.s3_secret_key = os.getenv("S3_SECRET_KEY", "minioadmin")
        self.s3_region = os.getenv("S3_REGION", "us-east-1")
        self.s3_bucket_name = os.getenv("S3_BUCKET_NAME", "reports")

        # CDN Configuration
        self.cdn_base_url = os.getenv("CDN_BASE_URL", "http://localhost:8082")

        self.jwt_algorithms = ["RS256"]


settings = Settings()
