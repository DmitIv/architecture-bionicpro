

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user_id
from ..clickhouse import get_user_reports
from ..s3 import s3_client

router = APIRouter()


@router.get("/reports")
async def get_reports(
    user_id: int = Query(..., description="User ID"),
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    current_user_id: str = Depends(get_current_user_id)
):
    if str(user_id) != current_user_id:
        raise HTTPException(status_code=403, detail="Access denied: can only access your own reports")

    try:
        # Если запрашивается отчет за конкретный день, пробуем получить из кеша
        if start_date and start_date == end_date:
            cached_report = s3_client.get_cached_report(user_id, start_date)
            if cached_report:
                return {
                    "reports": cached_report["reports"],
                    "total": cached_report["total"],
                    "cached": True,
                    "cdn_url": cached_report.get("cdn_url")
                }

        # Если нет в кеше или запрашивается диапазон дат, получаем из ClickHouse
        reports = get_user_reports(user_id, start_date, end_date)

        result = []
        for row in reports:
            result.append({
                "user_id": row[0],
                "report_date": str(row[1]),
                "device_id": row[2],
                "total_signals": row[3],
                "avg_response_time": float(row[4]),
                "customer_name": row[5],
                "customer_email": row[6]
            })

        response_data = {"reports": result, "total": len(result), "cached": False}

        # Если это отчет за один день, кешируем его
        if start_date and start_date == end_date and result:
            try:
                cdn_url = s3_client.cache_report(user_id, start_date, response_data)
                response_data["cdn_url"] = cdn_url
            except Exception as cache_error:
                # Логируем ошибку кеширования, но не прерываем ответ
                print(f"Failed to cache report: {cache_error}")

        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching reports: {str(e)}")
