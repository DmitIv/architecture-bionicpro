import json

from datetime import datetime
from typing import Any

import boto3

from botocore.exceptions import ClientError, NoCredentialsError

from .config import settings


class S3Client:
    def __init__(self):
        self.client = boto3.client(
            's3',
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region
        )
        self.bucket_name = settings.s3_bucket_name

    def generate_report_key(self, user_id: int, report_date: str) -> str:
        """Генерирует ключ для отчета в S3"""
        date_obj = datetime.strptime(report_date, "%Y-%m-%d")
        year = date_obj.year
        month = date_obj.month
        return f"reports/{user_id}/{year}/{month}/report_{report_date}.json"

    def get_cached_report(self, user_id: int, report_date: str) -> dict[str, Any] | None:
        """Получает кешированный отчет из S3"""
        try:
            key = self.generate_report_key(user_id, report_date)
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            data = response['Body'].read().decode('utf-8')
            return json.loads(data)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            raise
        except (NoCredentialsError, json.JSONDecodeError):
            return None

    def cache_report(self, user_id: int, report_date: str, report_data: dict[str, Any]) -> str:
        """Сохраняет отчет в S3 и возвращает CDN URL"""
        try:
            key = self.generate_report_key(user_id, report_date)
            json_data = json.dumps(report_data, ensure_ascii=False, indent=2)

            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json_data,
                ContentType='application/json',
                CacheControl='max-age=86400'  # 1 день
            )

            # Возвращаем CDN URL
            cdn_url = f"{settings.cdn_base_url}/{key}"
            return cdn_url

        except Exception as e:
            raise Exception(f"Failed to cache report: {str(e)}")


s3_client = S3Client()
