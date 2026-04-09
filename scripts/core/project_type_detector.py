"""
project_type_detector.py — 自动识别项目类型，驱动自适应测试维度选择。

支持五种类型：web / cli / mobile / data-pipeline / microservices
识别来源：ARCH.md 中的技术选型章节 + 用户在访谈中的描述。
"""
import re
from pathlib import Path


# 每种类型的测试维度集
TEST_DIMENSIONS = {
    "web": ["[UI]", "[API]", "[DATA]", "[AUTH]", "[PERF]", "[XSS]", "[MOBILE-WEB]"],
    "cli": ["[UNIT]", "[INT]", "[E2E]", "[EDGE]", "[INSTALL]", "[CROSS-PLATFORM]"],
    "mobile": ["[UI]", "[OFFLINE]", "[PUSH]", "[PERF]", "[DEVICE]", "[PERMISSION]"],
    "data-pipeline": ["[DATA]", "[ASYNC]", "[IDEMPOTENCY]", "[VOLUME]", "[SCHEMA]", "[BACKFILL]"],
    "microservices": ["[API]", "[CONTRACT]", "[CHAOS]", "[LATENCY]", "[SCALE]", "[CIRCUIT]"],
}

# 关键词 → 类型映射（权重最高的 3 个词触发判定）
KEYWORD_MAP = {
    "web": ["React", "Vue", "Angular", "Django", "Flask", "FastAPI", "Express",
            "HTML", "CSS", "浏览器", "前端", "Web", "HTTP", "REST", "nginx", "Caddy"],
    "cli": ["CLI", "命令行", "terminal", "argparse", "click", "cobra", "shell",
            "bash", "脚本", "工具", "terminal"],
    "mobile": ["iOS", "Android", "React Native", "Flutter", "Swift", "Kotlin",
               "移动端", "APP", "小程序", "uni-app"],
    "data-pipeline": ["Kafka", "Flink", "Spark", "ETL", "Pipeline", "数据管道",
                      "Airflow", "Luigi", "Celery", "消息队列", "数据处理", "batch"],
    "microservices": ["微服务", "gRPC", "Service Mesh", "Kubernetes", "k8s",
                      "Docker Compose", "API Gateway", "服务发现", "负载均衡"],
}


def detect_from_arch(arch_path: str) -> str:
    """从 ARCH.md 文本中自动识别项目类型。"""
    p = Path(arch_path)
    if not p.exists():
        return "web"  # 默认降级

    text = p.read_text(encoding="utf-8", errors="ignore")
    scores = {t: 0 for t in KEYWORD_MAP}
    for proj_type, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if re.search(re.escape(kw), text, re.IGNORECASE):
                scores[proj_type] += 1

    best = max(scores, key=lambda t: scores[t])
    if scores[best] == 0:
        return "web"
    return best


def detect_from_description(description: str) -> str:
    """从用户描述文本中识别项目类型（访谈阶段使用）。"""
    scores = {t: 0 for t in KEYWORD_MAP}
    for proj_type, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if re.search(re.escape(kw), description, re.IGNORECASE):
                scores[proj_type] += 1

    best = max(scores, key=lambda t: scores[t])
    if scores[best] == 0:
        return "web"
    return best


def get_dimensions(project_type: str) -> list:
    """获取项目类型对应的测试维度列表。"""
    return TEST_DIMENSIONS.get(project_type, TEST_DIMENSIONS["web"])


def describe_project_type(project_type: str) -> str:
    dims = get_dimensions(project_type)
    type_names = {
        "web": "Web 应用",
        "cli": "CLI 命令行工具",
        "mobile": "移动应用",
        "data-pipeline": "数据管道/批处理",
        "microservices": "微服务架构",
    }
    return f"{type_names.get(project_type, project_type)}（维度：{', '.join(dims)}）"
