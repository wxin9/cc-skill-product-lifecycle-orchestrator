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


# 每种类型的维度生成器配置（与 DimensionConfig TypedDict 对齐）
DIMENSION_GENERATORS = {
    "web": [
        {
            "dimension_tag": "[UI]",
            "name": "UI 交互",
            "description_template": "[UI] {variant_label}「{feature_name}」",
            "steps_template": [
                "用户在{feature_name}页面输入有效数据",
                "系统校验输入",
                "系统执行{feature_name}逻辑",
                "系统返回操作结果",
                "界面更新显示",
            ],
            "expected_template": "{feature_name}操作成功，界面正确反馈",
            "e2e": True,
            "layer_entry": "ui",
            "conditional_keywords": [],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[API]",
            "name": "API 接口",
            "description_template": "[API] {variant_label}「{feature_name}」",
            "steps_template": [
                "客户端发起{feature_name}请求",
                "服务端校验请求参数",
                "服务端执行{feature_name}业务逻辑",
                "服务端返回响应结果",
            ],
            "expected_template": "{feature_name}接口返回正确状态码和数据",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": [],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[DATA]",
            "name": "数据处理",
            "description_template": "[DATA] {variant_label}「{feature_name}」",
            "steps_template": [
                "系统接收{feature_name}数据输入",
                "系统校验数据格式与完整性",
                "系统执行{feature_name}数据处理",
                "系统持久化处理结果",
            ],
            "expected_template": "{feature_name}数据处理正确，存储结果一致",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": ["数据", "存储", "缓存"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[ASYNC]",
            "name": "异步流程",
            "description_template": "[ASYNC] {variant_label}「{feature_name}」",
            "steps_template": [
                "系统触发{feature_name}异步任务",
                "异步消费者接收并处理任务",
                "系统执行{feature_name}业务逻辑",
                "系统更新任务状态并通知",
            ],
            "expected_template": "{feature_name}异步任务执行成功，状态正确更新",
            "e2e": True,
            "layer_entry": "api",
            "conditional_keywords": ["异步", "队列", "消息", "并发"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[AUTH]",
            "name": "认证授权",
            "description_template": "[AUTH] {variant_label}「{feature_name}」",
            "steps_template": [
                "用户发起{feature_name}认证请求",
                "系统校验身份凭证",
                "系统执行{feature_name}授权判定",
                "系统返回认证结果",
            ],
            "expected_template": "{feature_name}认证授权结果符合预期",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": ["登录", "权限", "认证", "授权", "token"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[EXT]",
            "name": "外部集成",
            "description_template": "[EXT] {variant_label}「{feature_name}」",
            "steps_template": [
                "系统发起{feature_name}外部服务调用",
                "外部服务接收并处理请求",
                "系统接收外部服务响应",
                "系统处理响应并更新本地状态",
            ],
            "expected_template": "{feature_name}外部集成调用成功，结果正确处理",
            "e2e": True,
            "layer_entry": "api",
            "conditional_keywords": ["第三方", "外部", "支付", "通知"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
    ],
    "cli": [
        {
            "dimension_tag": "[CLI]",
            "name": "命令行交互",
            "description_template": "[CLI] {variant_label}「{feature_name}」",
            "steps_template": [
                "用户执行{feature_name}命令及参数",
                "CLI 解析命令与参数",
                "系统执行{feature_name}核心逻辑",
                "终端输出执行结果",
            ],
            "expected_template": "{feature_name}命令执行成功，输出结果正确",
            "e2e": False,
            "layer_entry": "cli",
            "conditional_keywords": [],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[DATA]",
            "name": "数据处理",
            "description_template": "[DATA] {variant_label}「{feature_name}」",
            "steps_template": [
                "CLI 接收{feature_name}数据输入",
                "系统校验数据格式",
                "系统执行{feature_name}数据处理",
                "系统输出处理结果",
            ],
            "expected_template": "{feature_name}数据处理正确，输出结果一致",
            "e2e": False,
            "layer_entry": "cli",
            "conditional_keywords": ["数据", "存储", "解析"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[ASYNC]",
            "name": "异步流程",
            "description_template": "[ASYNC] {variant_label}「{feature_name}」",
            "steps_template": [
                "用户触发{feature_name}异步操作",
                "系统启动后台任务",
                "系统执行{feature_name}异步逻辑",
                "系统输出任务执行结果",
            ],
            "expected_template": "{feature_name}异步操作执行成功，结果正确",
            "e2e": False,
            "layer_entry": "cli",
            "conditional_keywords": ["异步", "并发", "后台"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[FILE]",
            "name": "文件操作",
            "description_template": "[FILE] {variant_label}「{feature_name}」",
            "steps_template": [
                "用户指定{feature_name}文件路径",
                "系统校验文件路径与权限",
                "系统执行{feature_name}文件操作",
                "系统确认操作结果",
            ],
            "expected_template": "{feature_name}文件操作成功，内容正确",
            "e2e": False,
            "layer_entry": "cli",
            "conditional_keywords": ["文件", "目录", "导入", "导出", "读写"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[EXT]",
            "name": "外部集成",
            "description_template": "[EXT] {variant_label}「{feature_name}」",
            "steps_template": [
                "CLI 发起{feature_name}外部服务请求",
                "外部服务处理请求",
                "系统接收并解析响应",
                "终端输出集成结果",
            ],
            "expected_template": "{feature_name}外部集成调用成功，结果正确",
            "e2e": True,
            "layer_entry": "cli",
            "conditional_keywords": ["API", "第三方", "网络"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
    ],
    "mobile": [
        {
            "dimension_tag": "[UI]",
            "name": "界面交互",
            "description_template": "[UI] {variant_label}「{feature_name}」",
            "steps_template": [
                "用户在{feature_name}页面输入操作",
                "客户端校验输入",
                "客户端执行{feature_name}交互逻辑",
                "界面更新显示结果",
            ],
            "expected_template": "{feature_name}交互操作成功，界面正确响应",
            "e2e": True,
            "layer_entry": "ui",
            "conditional_keywords": [],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[API]",
            "name": "网络请求",
            "description_template": "[API] {variant_label}「{feature_name}」",
            "steps_template": [
                "客户端发起{feature_name}网络请求",
                "服务端校验请求并处理",
                "服务端返回响应数据",
                "客户端解析响应并更新状态",
            ],
            "expected_template": "{feature_name}网络请求成功，数据正确返回",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": [],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[DATA]",
            "name": "本地数据",
            "description_template": "[DATA] {variant_label}「{feature_name}」",
            "steps_template": [
                "客户端触发{feature_name}数据操作",
                "系统校验本地数据状态",
                "系统执行{feature_name}数据读写",
                "系统确认数据一致性",
            ],
            "expected_template": "{feature_name}本地数据操作成功，状态一致",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": ["数据", "缓存", "存储"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[ASYNC]",
            "name": "异步流程",
            "description_template": "[ASYNC] {variant_label}「{feature_name}」",
            "steps_template": [
                "客户端触发{feature_name}异步任务",
                "系统后台执行任务逻辑",
                "任务完成后回调通知",
                "客户端更新界面状态",
            ],
            "expected_template": "{feature_name}异步任务完成，状态正确更新",
            "e2e": True,
            "layer_entry": "api",
            "conditional_keywords": ["异步", "队列", "后台"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[OFFLINE]",
            "name": "离线模式",
            "description_template": "[OFFLINE] {variant_label}「{feature_name}」",
            "steps_template": [
                "用户在离线状态下操作{feature_name}",
                "客户端检测网络不可用",
                "系统执行{feature_name}离线逻辑",
                "网络恢复后系统同步数据",
            ],
            "expected_template": "{feature_name}离线模式正常工作，恢复后数据同步",
            "e2e": True,
            "layer_entry": "ui",
            "conditional_keywords": ["离线", "断网", "弱网"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[PUSH]",
            "name": "推送通知",
            "description_template": "[PUSH] {variant_label}「{feature_name}」",
            "steps_template": [
                "服务端触发{feature_name}推送事件",
                "推送服务下发通知",
                "客户端接收推送消息",
                "客户端处理{feature_name}通知逻辑",
            ],
            "expected_template": "{feature_name}推送通知送达，客户端正确处理",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": ["推送", "通知", "消息"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
    ],
    "data-pipeline": [
        {
            "dimension_tag": "[DATA]",
            "name": "数据流",
            "description_template": "[DATA] {variant_label}「{feature_name}」",
            "steps_template": [
                "系统接收{feature_name}数据源输入",
                "系统校验数据格式与完整性",
                "系统执行{feature_name}数据流转逻辑",
                "系统输出至目标存储",
            ],
            "expected_template": "{feature_name}数据流转正确，输出结果一致",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": [],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[ASYNC]",
            "name": "异步处理",
            "description_template": "[ASYNC] {variant_label}「{feature_name}」",
            "steps_template": [
                "系统接收{feature_name}异步消息",
                "消费者拉取并解析消息",
                "系统执行{feature_name}异步处理逻辑",
                "系统确认消息并更新状态",
            ],
            "expected_template": "{feature_name}异步处理完成，消息确认无误",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": ["异步", "流", "批", "队列"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[IDEMPOTENCY]",
            "name": "幂等性",
            "description_template": "[IDEMPOTENCY] {variant_label}「{feature_name}」",
            "steps_template": [
                "系统首次执行{feature_name}操作",
                "系统记录操作唯一标识",
                "系统重复接收{feature_name}请求",
                "系统识别重复并返回幂等结果",
            ],
            "expected_template": "{feature_name}重复执行结果一致，无副作用",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": ["幂等", "重复", "重试"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[VOLUME]",
            "name": "数据量",
            "description_template": "[VOLUME] {variant_label}「{feature_name}」",
            "steps_template": [
                "系统接收{feature_name}大批量数据输入",
                "系统分批处理数据",
                "系统执行{feature_name}容量逻辑",
                "系统输出处理结果并校验完整性",
            ],
            "expected_template": "{feature_name}大数据量处理成功，结果完整无丢失",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": ["大量", "批量", "海量", "容量"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[SCHEMA]",
            "name": "数据格式",
            "description_template": "[SCHEMA] {variant_label}「{feature_name}」",
            "steps_template": [
                "系统接收{feature_name}原始格式数据",
                "系统校验数据格式规范",
                "系统执行{feature_name}格式转换逻辑",
                "系统输出目标格式数据",
            ],
            "expected_template": "{feature_name}数据格式转换正确，符合目标规范",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": ["格式", "校验", "转换", "映射"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[BACKFILL]",
            "name": "数据回填",
            "description_template": "[BACKFILL] {variant_label}「{feature_name}」",
            "steps_template": [
                "系统识别{feature_name}历史数据缺失",
                "系统加载回填数据源",
                "系统执行{feature_name}回填逻辑",
                "系统校验回填结果完整性",
            ],
            "expected_template": "{feature_name}数据回填成功，历史记录完整",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": ["回填", "历史", "补录", "迁移"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
    ],
    "microservices": [
        {
            "dimension_tag": "[API]",
            "name": "API 网关",
            "description_template": "[API] {variant_label}「{feature_name}」",
            "steps_template": [
                "客户端发起{feature_name}网关请求",
                "网关校验请求并路由",
                "后端服务执行{feature_name}业务逻辑",
                "网关聚合响应并返回",
            ],
            "expected_template": "{feature_name}网关请求路由正确，响应符合预期",
            "e2e": True,
            "layer_entry": "api",
            "conditional_keywords": [],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[RPC]",
            "name": "服务间调用",
            "description_template": "[RPC] {variant_label}「{feature_name}」",
            "steps_template": [
                "调用方发起{feature_name}服务间请求",
                "服务注册中心解析目标实例",
                "被调方执行{feature_name}逻辑并返回",
                "调用方接收并处理响应",
            ],
            "expected_template": "{feature_name}服务间调用成功，返回结果正确",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": ["RPC", "gRPC", "内部调用", "服务间"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[DATA]",
            "name": "数据层",
            "description_template": "[DATA] {variant_label}「{feature_name}」",
            "steps_template": [
                "服务发起{feature_name}数据操作请求",
                "数据层校验请求与数据状态",
                "数据层执行{feature_name}读写逻辑",
                "数据层返回操作结果",
            ],
            "expected_template": "{feature_name}数据层操作成功，数据一致性正确",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": ["数据", "存储", "缓存", "数据库"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[ASYNC]",
            "name": "异步通信",
            "description_template": "[ASYNC] {variant_label}「{feature_name}」",
            "steps_template": [
                "发布方发送{feature_name}异步消息",
                "消息中间件路由消息至消费者",
                "消费方执行{feature_name}处理逻辑",
                "消费方确认消息并更新状态",
            ],
            "expected_template": "{feature_name}异步消息投递成功，消费结果正确",
            "e2e": True,
            "layer_entry": "api",
            "conditional_keywords": ["异步", "消息", "事件", "MQ"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[AUTH]",
            "name": "认证鉴权",
            "description_template": "[AUTH] {variant_label}「{feature_name}」",
            "steps_template": [
                "服务发起{feature_name}认证鉴权请求",
                "认证服务校验身份凭证",
                "认证服务执行{feature_name}权限判定",
                "认证服务返回鉴权结果",
            ],
            "expected_template": "{feature_name}认证鉴权结果符合预期",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": ["认证", "授权", "token", "JWT"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
        {
            "dimension_tag": "[RESILIENCE]",
            "name": "容错韧性",
            "description_template": "[RESILIENCE] {variant_label}「{feature_name}」",
            "steps_template": [
                "系统检测{feature_name}服务异常",
                "系统触发容错策略（熔断/降级/限流）",
                "系统执行{feature_name}容错逻辑",
                "系统恢复后自动复位",
            ],
            "expected_template": "{feature_name}容错策略生效，系统稳定运行",
            "e2e": False,
            "layer_entry": "api",
            "conditional_keywords": ["熔断", "降级", "限流", "超时", "重试"],
            "defensive_variants": ["happy", "boundary", "error", "data"],
        },
    ],
}


def get_dimension_generators(project_type: str) -> list:
    """Return dimension generator configs for the given project type."""
    return DIMENSION_GENERATORS.get(project_type, DIMENSION_GENERATORS["web"])


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
