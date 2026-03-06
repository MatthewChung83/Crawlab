# -*- coding: utf-8 -*-
"""
Crawlab API Gateway
提供 RESTful API 介面供 n8n 或其他工具呼叫

啟動方式:
    uvicorn api_gateway:app --host 0.0.0.0 --port 8000

API 文件:
    http://localhost:8000/docs
"""
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import subprocess
import json
import uuid
import os
from datetime import datetime
from pathlib import Path

# 建立 FastAPI 應用
app = FastAPI(
    title="Crawlab API Gateway",
    description="爬蟲模組 API 介面",
    version="1.0.0"
)

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 任務狀態儲存 (生產環境建議使用 Redis)
tasks: Dict[str, dict] = {}

# 專案根目錄
BASE_PATH = Path(__file__).parent


# === 資料模型 ===

class TaskRequest(BaseModel):
    """任務請求"""
    module: str
    callback_url: Optional[str] = None


class TaskResponse(BaseModel):
    """任務回應"""
    task_id: str
    module: str
    status: str
    message: str


class TaskStatus(BaseModel):
    """任務狀態"""
    task_id: str
    module: str
    status: str  # pending, running, success, failed
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    result: Optional[Dict[str, Any]] = None


class ModuleInfo(BaseModel):
    """模組資訊"""
    name: str
    available: bool
    description: Optional[str] = None


# === API 端點 ===

@app.get("/")
async def root():
    """API 根目錄"""
    return {
        "name": "Crawlab API Gateway",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/api/v1/health")
async def health_check():
    """健康檢查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/v1/modules", response_model=Dict[str, Any])
async def list_modules():
    """列出所有可用模組"""
    result = subprocess.run(
        ["python", str(BASE_PATH / "run_crawler.py"), "--list"],
        capture_output=True,
        text=True,
        cwd=str(BASE_PATH)
    )

    if result.returncode == 0:
        return json.loads(result.stdout)
    else:
        raise HTTPException(status_code=500, detail="無法取得模組列表")


@app.post("/api/v1/tasks", response_model=TaskResponse)
async def create_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """
    建立新的爬蟲任務

    - **module**: 模組名稱 (例如: Data-TaxReturn)
    - **callback_url**: 完成後回呼的 URL (選用)
    """
    task_id = str(uuid.uuid4())

    # 初始化任務狀態
    tasks[task_id] = {
        "task_id": task_id,
        "module": request.module,
        "status": "pending",
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "duration_seconds": None,
        "result": None,
        "callback_url": request.callback_url
    }

    # 加入背景任務
    background_tasks.add_task(
        run_crawler_task,
        task_id,
        request.module,
        request.callback_url
    )

    return TaskResponse(
        task_id=task_id,
        module=request.module,
        status="pending",
        message="任務已建立"
    )


@app.get("/api/v1/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """查詢任務狀態"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任務不存在")

    task = tasks[task_id]
    return TaskStatus(
        task_id=task["task_id"],
        module=task["module"],
        status=task["status"],
        start_time=task["start_time"],
        end_time=task.get("end_time"),
        duration_seconds=task.get("duration_seconds"),
        result=task.get("result")
    )


@app.get("/api/v1/tasks", response_model=List[TaskStatus])
async def list_tasks(
    status: Optional[str] = None,
    module: Optional[str] = None,
    limit: int = 50
):
    """
    列出任務

    - **status**: 篩選狀態 (pending, running, success, failed)
    - **module**: 篩選模組
    - **limit**: 回傳數量上限
    """
    result = []

    for task in tasks.values():
        # 篩選條件
        if status and task["status"] != status:
            continue
        if module and task["module"] != module:
            continue

        result.append(TaskStatus(
            task_id=task["task_id"],
            module=task["module"],
            status=task["status"],
            start_time=task["start_time"],
            end_time=task.get("end_time"),
            duration_seconds=task.get("duration_seconds"),
            result=task.get("result")
        ))

    # 依時間排序，最新的在前
    result.sort(key=lambda x: x.start_time, reverse=True)

    return result[:limit]


@app.delete("/api/v1/tasks/{task_id}")
async def delete_task(task_id: str):
    """刪除任務記錄"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任務不存在")

    del tasks[task_id]
    return {"message": "任務已刪除"}


@app.post("/api/v1/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消任務 (僅限 pending 狀態)"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任務不存在")

    task = tasks[task_id]
    if task["status"] != "pending":
        raise HTTPException(status_code=400, detail="只能取消 pending 狀態的任務")

    task["status"] = "cancelled"
    task["end_time"] = datetime.now().isoformat()

    return {"message": "任務已取消"}


@app.get("/api/v1/logs/{module}")
async def get_module_logs(module: str, lines: int = 100):
    """
    取得模組的 Log

    - **module**: 模組名稱
    - **lines**: 回傳行數 (預設 100)
    """
    log_file = BASE_PATH / "logs" / f"{module}.log"

    if not log_file.exists():
        raise HTTPException(status_code=404, detail="Log 檔案不存在")

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            return {
                "module": module,
                "total_lines": len(all_lines),
                "lines": all_lines[-lines:]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"讀取 Log 失敗: {str(e)}")


# === 背景任務 ===

async def run_crawler_task(task_id: str, module: str, callback_url: str = None):
    """背景執行爬蟲任務"""
    task = tasks.get(task_id)
    if not task:
        return

    # 檢查是否被取消
    if task["status"] == "cancelled":
        return

    # 更新狀態為執行中
    task["status"] = "running"
    start_time = datetime.now()

    try:
        # 執行爬蟲
        result = subprocess.run(
            ["python", str(BASE_PATH / "run_crawler.py"), module],
            capture_output=True,
            text=True,
            timeout=3600,  # 1 小時超時
            cwd=str(BASE_PATH)
        )

        end_time = datetime.now()

        # 解析輸出
        if result.stdout:
            try:
                output = json.loads(result.stdout)
                task["status"] = "success" if output.get("success") else "failed"
                task["result"] = output
            except json.JSONDecodeError:
                task["status"] = "failed"
                task["result"] = {"stdout": result.stdout, "stderr": result.stderr}
        else:
            task["status"] = "failed"
            task["result"] = {"stderr": result.stderr}

    except subprocess.TimeoutExpired:
        end_time = datetime.now()
        task["status"] = "failed"
        task["result"] = {"error": "任務超時 (超過 1 小時)"}

    except Exception as e:
        end_time = datetime.now()
        task["status"] = "failed"
        task["result"] = {"error": str(e)}

    # 更新結束時間
    task["end_time"] = end_time.isoformat()
    task["duration_seconds"] = (end_time - start_time).total_seconds()

    # 回呼通知
    if callback_url:
        try:
            import requests
            requests.post(
                callback_url,
                json={
                    "task_id": task_id,
                    "module": module,
                    "status": task["status"],
                    "result": task["result"],
                    "duration_seconds": task["duration_seconds"]
                },
                timeout=30
            )
        except Exception as e:
            print(f"回呼通知失敗: {e}")


# === 啟動 ===

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
