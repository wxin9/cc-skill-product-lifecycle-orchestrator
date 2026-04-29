"""
solution_analyzer.py — 实现方案分析器

分析用户需求、项目代码和业界方案，为 product-lifecycle-orchestrator 工作流提供实现建议。

核心类：
  SolutionAnalyzer — 分析需求并生成实现方案建议

设计原则：
  - 分析项目代码结构和依赖关系
  - 搜索业界最佳实践和解决方案
  - 生成多个候选实现方案
  - 推荐最优方案并给出理由
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any


class SolutionAnalyzer:
    """实现方案分析器

    分析需求、项目代码和业界方案，提出实现建议。
    """

    def __init__(self, project_root: str | Path):
        """初始化分析器

        Args:
            project_root: 项目根目录路径
        """
        self.root = Path(project_root).resolve()
        self.intent = None
        self.user_input = None

    def analyze(self, intent: str, user_input: str) -> Dict[str, Any]:
        """主分析方法

        分析用户意图和输入，生成实现方案建议。

        Args:
            intent: 用户意图（如 "bug-fix", "new-feature", "refactor"）
            user_input: 用户原始输入

        Returns:
            {
                "project_context": {...},          # 项目代码分析结果
                "industry_solutions": [...],       # 业界方案列表
                "proposed_solutions": [...],       # 提议的实现方案
                "recommendation": str,             # 推荐的最优方案
                "confidence": float,               # 推荐置信度 (0-1)
            }
        """
        self.intent = intent
        self.user_input = user_input

        # 1. 分析项目代码
        project_context = self._analyze_project_code()

        # 2. 搜索业界方案
        industry_solutions = self._search_industry_solutions()

        # 3. 生成实现方案
        proposed_solutions = self._generate_solutions(
            project_context, industry_solutions
        )

        # 4. 推荐最优方案
        recommendation, confidence = self._recommend(proposed_solutions)

        return {
            "project_context": project_context,
            "industry_solutions": industry_solutions,
            "proposed_solutions": proposed_solutions,
            "recommendation": recommendation,
            "confidence": confidence,
        }

    def _analyze_project_code(self) -> Dict[str, Any]:
        """分析项目代码

        分析项目结构、依赖关系、代码模式等。

        Returns:
            {
                "type": str,                       # 项目类型 (web/cli/mobile/data/microservices)
                "language": str,                   # 主要编程语言
                "framework": str,                  # 使用的框架
                "related_modules": [...],          # 相关模块列表
                "key_functions": [...],            # 关键函数列表
                "dependencies": [...],             # 依赖列表
                "structure": {...},                # 项目结构分析
                "patterns": [...],                 # 已使用的代码模式
                "test_coverage": float,            # 测试覆盖率
            }
        """
        result = {
            "type": "unknown",
            "language": "unknown",
            "framework": "unknown",
            "related_modules": [],
            "key_functions": [],
            "dependencies": [],
            "structure": {},
            "patterns": [],
            "test_coverage": 0.0,
        }

        try:
            # 1. 检测项目类型
            result["type"] = self._detect_project_type()

            # 2. 识别主要编程语言
            result["language"] = self._detect_language()

            # 3. 识别框架
            result["framework"] = self._detect_framework()

            # 4. 分析依赖关系
            result["dependencies"] = self._analyze_dependencies()

            # 5. 扫描代码目录，提取模块和函数
            modules, functions = self._scan_code_structure()
            result["related_modules"] = modules
            result["key_functions"] = functions

            # 6. 分析项目结构
            result["structure"] = self._analyze_structure()

            # 7. 识别代码模式
            result["patterns"] = self._detect_patterns()

            # 8. 估算测试覆盖率
            result["test_coverage"] = self._estimate_test_coverage()

        except Exception as e:
            # 异常情况下返回默认值，但记录错误
            result["error"] = str(e)

        return result

    def _search_industry_solutions(self) -> List[Dict[str, Any]]:
        """搜索业界方案

        根据意图和项目类型搜索业界最佳实践。

        Returns:
            [
                {
                    "name": str,                   # 方案名称
                    "description": str,            # 方案描述
                    "pros": List[str],             # 优点
                    "cons": List[str],             # 缺点
                    "complexity": str,             # 复杂度 (low/medium/high)
                    "source": str,                 # 来源
                },
                ...
            ]
        """
        solutions = []

        # 构建搜索查询
        intent_keywords = {
            "bug-fix": "bug fixing debugging",
            "new-feature": "feature implementation design",
            "refactor": "code refactoring patterns",
            "performance": "performance optimization",
            "security": "security hardening best practices",
            "testing": "testing strategies",
            "new-product": "new product development from scratch MVP",
            "from-scratch": "building software from scratch architecture design",
        }

        # 获取项目类型
        project_type = self._detect_project_type()
        intent_key = intent_keywords.get(self.intent, self.intent)

        # 尝试使用 WebSearch 搜索业界方案
        try:
            # 搜索查询 1: 最佳实践
            query1 = f"{intent_key} best practices {project_type}"
            results1 = self._web_search(query1)

            # 搜索查询 2: 开源实现
            query2 = f"{intent_key} open source implementation"
            results2 = self._web_search(query2)

            # 合并结果
            solutions = self._parse_search_results(results1 + results2)

        except Exception:
            # WebSearch 不可用，返回通用建议
            solutions = self._get_generic_solutions()

        return solutions[:10]  # 限制返回数量

    def _web_search(self, query: str) -> List[Dict]:
        """执行 Web 搜索（内部方法）

        Args:
            query: 搜索查询

        Returns:
            搜索结果列表
        """
        # 这里返回空列表，实际使用时会被 WebSearch 工具的结果替换
        # 这个方法主要作为占位符，真正的 WebSearch 需要在运行时调用
        return []

    def _parse_search_results(self, results: List[Dict]) -> List[Dict[str, Any]]:
        """解析搜索结果

        Args:
            results: 原始搜索结果

        Returns:
            格式化的方案列表
        """
        solutions = []

        for result in results[:5]:  # 限制处理数量
            solution = {
                "name": result.get("title", "Unknown"),
                "description": result.get("snippet", ""),
                "pros": [],
                "cons": [],
                "complexity": "medium",
                "source": result.get("link", ""),
            }
            solutions.append(solution)

        return solutions

    def _get_generic_solutions(self) -> List[Dict[str, Any]]:
        """获取通用解决方案

        Returns:
            通用方案列表
        """
        generic_solutions = {
            "bug-fix": [
                {
                    "name": "Root Cause Analysis",
                    "description": "通过日志分析、调试工具定位问题根源",
                    "pros": ["彻底解决问题", "防止复发"],
                    "cons": ["耗时较长"],
                    "complexity": "medium",
                    "source": "standard",
                },
                {
                    "name": "Quick Patch",
                    "description": "快速修复症状，后续再深入分析",
                    "pros": ["快速恢复服务"],
                    "cons": ["可能治标不治本"],
                    "complexity": "low",
                    "source": "standard",
                },
            ],
            "new-feature": [
                {
                    "name": "Iterative Development",
                    "description": "分阶段实现，逐步完善功能",
                    "pros": ["风险可控", "快速反馈"],
                    "cons": ["需要多次迭代"],
                    "complexity": "medium",
                    "source": "agile",
                },
                {
                    "name": "MVP First",
                    "description": "先实现最小可行产品，验证需求",
                    "pros": ["快速验证", "降低浪费"],
                    "cons": ["功能不完整"],
                    "complexity": "low",
                    "source": "lean",
                },
            ],
            "refactor": [
                {
                    "name": "Strangler Pattern",
                    "description": "逐步替换旧代码，降低风险",
                    "pros": ["风险低", "可回滚"],
                    "cons": ["周期长"],
                    "complexity": "medium",
                    "source": "martin-fowler",
                },
                {
                    "name": "Big Rewrite",
                    "description": "一次性重写，快速完成",
                    "pros": ["彻底改造"],
                    "cons": ["风险高", "影响大"],
                    "complexity": "high",
                    "source": "standard",
                },
            ],
            "new-product": [
                {
                    "name": "MVP 起步",
                    "description": "先交付最小可行产品，快速验证核心价值，再逐步扩展功能",
                    "pros": ["快速验证市场", "降低试错成本", "早期用户反馈"],
                    "cons": ["功能不完整", "需要后续多轮迭代"],
                    "complexity": "medium",
                    "source": "lean-startup",
                },
                {
                    "name": "完整产品规划",
                    "description": "完整规划所有功能模块，按优先级分阶段交付",
                    "pros": ["系统完整", "架构合理", "用户体验一致"],
                    "cons": ["周期较长", "前期投入大"],
                    "complexity": "high",
                    "source": "waterfall-agile-hybrid",
                },
            ],
            "from-scratch": [
                {
                    "name": "技术选型优先",
                    "description": "先确定技术栈和架构，再开始功能开发",
                    "pros": ["技术债务少", "架构可扩展"],
                    "cons": ["前期投入较大"],
                    "complexity": "medium",
                    "source": "standard",
                },
            ],
        }

        return generic_solutions.get(self.intent, [])

    def _generate_solutions(
        self,
        project_context: Dict[str, Any],
        industry_solutions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """生成实现方案

        结合项目上下文和业界方案，生成具体的实现建议。

        Args:
            project_context: 项目代码分析结果
            industry_solutions: 业界方案列表

        Returns:
            [
                {
                    "id": str,                     # 方案 ID
                    "title": str,                  # 方案标题
                    "description": str,            # 详细描述
                    "steps": List[str],            # 实施步骤
                    "estimated_effort": str,       # 预估工作量
                    "risk_level": str,             # 风险等级 (low/medium/high)
                    "dependencies": List[str],     # 依赖项
                    "score": float,                # 评分 (0-100)
                },
                ...
            ]
        """
        solutions = []

        # 1. 生成保守方案（低风险、稳定）
        conservative = self._generate_conservative_solution(
            project_context, industry_solutions
        )
        solutions.append(conservative)

        # 2. 生成推荐方案（平衡风险和收益）
        recommended = self._generate_recommended_solution(
            project_context, industry_solutions
        )
        solutions.append(recommended)

        # 3. 生成创新方案（高风险、高收益）
        innovative = self._generate_innovative_solution(
            project_context, industry_solutions
        )
        solutions.append(innovative)

        # 4. 如果有业界方案，融合生成额外方案
        if industry_solutions:
            for idx, ind_sol in enumerate(industry_solutions[:2]):
                adapted = self._adapt_industry_solution(
                    ind_sol, project_context, idx
                )
                solutions.append(adapted)

        # 为所有方案评分
        for solution in solutions:
            solution["score"] = self._calculate_solution_score(
                solution, project_context
            )

        # 按评分排序
        solutions.sort(key=lambda x: x["score"], reverse=True)

        return solutions

    def _generate_conservative_solution(
        self,
        project_context: Dict[str, Any],
        industry_solutions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成保守方案

        Args:
            project_context: 项目上下文
            industry_solutions: 业界方案列表

        Returns:
            保守方案
        """
        # 基于意图生成保守方案
        intent_templates = {
            "bug-fix": {
                "title": "方案A: 渐进式修复",
                "description": "通过日志分析和单元测试定位问题，最小化修改范围",
                "steps": [
                    "1. 分析错误日志和堆栈信息",
                    "2. 编写复现问题的单元测试",
                    "3. 定位问题根源代码",
                    "4. 实施最小化修复",
                    "5. 运行测试验证修复",
                    "6. 代码审查和文档更新",
                ],
                "estimated_effort": "1-2天",
                "risk_level": "low",
            },
            "new-feature": {
                "title": "方案A: MVP 迭代开发",
                "description": "先实现核心功能的最小可行版本，逐步迭代完善",
                "steps": [
                    "1. 定义最小可行产品范围",
                    "2. 设计核心接口和数据结构",
                    "3. 实现基础功能",
                    "4. 编写单元测试",
                    "5. 内部验证和反馈",
                    "6. 根据反馈迭代优化",
                ],
                "estimated_effort": "3-5天",
                "risk_level": "low",
            },
            "refactor": {
                "title": "方案A: 渐进式重构",
                "description": "使用 Strangler Pattern 逐步替换，保持系统稳定",
                "steps": [
                    "1. 识别需要重构的模块",
                    "2. 编写保护性测试",
                    "3. 创建新实现",
                    "4. 逐步切换调用",
                    "5. 移除旧代码",
                    "6. 验证和清理",
                ],
                "estimated_effort": "5-7天",
                "risk_level": "low",
            },
            "new-product": {
                "title": "方案A: MVP 优先",
                "description": "从最小可行产品出发，验证核心假设后再扩展",
                "steps": [
                    "1. 定义核心用户价值和最小功能集",
                    "2. 完成 PRD 和架构设计",
                    "3. 搭建基础框架和 CI/CD",
                    "4. 实现 MVP 功能",
                    "5. 内测和用户反馈收集",
                    "6. 迭代优化",
                ],
                "estimated_effort": "4-8周",
                "risk_level": "low",
            },
            "from-scratch": {
                "title": "方案A: 渐进式构建",
                "description": "从基础设施开始，逐步添加功能层",
                "steps": [
                    "1. 选定技术栈和架构模式",
                    "2. 搭建基础工程结构",
                    "3. 实现核心模块",
                    "4. 分层添加功能",
                    "5. 完善测试覆盖",
                    "6. 文档和运维准备",
                ],
                "estimated_effort": "3-6周",
                "risk_level": "low",
            },
        }

        template = intent_templates.get(
            self.intent,
            {
                "title": "方案A: 稳健实施",
                "description": "采用成熟方案，确保系统稳定性",
                "steps": [
                    "1. 分析现状和需求",
                    "2. 制定详细计划",
                    "3. 分阶段实施",
                    "4. 测试验证",
                    "5. 代码审查",
                    "6. 文档更新",
                ],
                "estimated_effort": "3-5天",
                "risk_level": "low",
            },
        )

        return {
            "id": "solution-conservative",
            **template,
            "dependencies": project_context.get("dependencies", [])[:5],
            "pros": ["风险低", "可回滚", "稳定性高"],
            "cons": ["周期较长", "创新性不足"],
        }

    def _generate_recommended_solution(
        self,
        project_context: Dict[str, Any],
        industry_solutions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成推荐方案

        Args:
            project_context: 项目上下文
            industry_solutions: 业界方案列表

        Returns:
            推荐方案
        """
        # 基于意图生成推荐方案
        intent_templates = {
            "bug-fix": {
                "title": "方案B: 根因修复 + 预防",
                "description": "不仅修复当前问题，还添加防护机制防止类似问题",
                "steps": [
                    "1. 深入分析问题根因",
                    "2. 编写全面的测试用例",
                    "3. 修复核心问题",
                    "4. 添加防御性编程",
                    "5. 增加监控和告警",
                    "6. 更新最佳实践文档",
                ],
                "estimated_effort": "2-3天",
                "risk_level": "medium",
            },
            "new-feature": {
                "title": "方案B: 完整功能实现",
                "description": "一次性实现完整功能，包含边界情况和错误处理",
                "steps": [
                    "1. 完整需求分析和设计",
                    "2. 设计 API 和数据模型",
                    "3. 实现核心逻辑",
                    "4. 处理边界情况和错误",
                    "5. 编写完整测试套件",
                    "6. 性能优化和文档",
                ],
                "estimated_effort": "5-7天",
                "risk_level": "medium",
            },
            "refactor": {
                "title": "方案B: 模块化重构",
                "description": "重新设计模块边界，提升代码质量和可维护性",
                "steps": [
                    "1. 分析当前架构问题",
                    "2. 设计新的模块结构",
                    "3. 定义清晰的接口",
                    "4. 逐模块重构",
                    "5. 集成测试",
                    "6. 性能验证",
                ],
                "estimated_effort": "7-10天",
                "risk_level": "medium",
            },
            "new-product": {
                "title": "方案B: 敏捷全栈开发",
                "description": "按迭代交付完整功能闭环，每个迭代包含开发、测试、用户验证",
                "steps": [
                    "1. 完整需求分析和优先级排序",
                    "2. 设计支持扩展的系统架构",
                    "3. 按迭代计划分批开发",
                    "4. 每迭代包含自动化测试",
                    "5. 持续集成和部署",
                    "6. 用户反馈驱动迭代调整",
                ],
                "estimated_effort": "8-16周",
                "risk_level": "medium",
            },
            "from-scratch": {
                "title": "方案B: 领域驱动设计",
                "description": "以业务领域为核心设计系统边界和模块划分",
                "steps": [
                    "1. 领域分析和边界划分",
                    "2. 定义核心领域模型",
                    "3. 设计领域服务和接口",
                    "4. 实现基础设施层",
                    "5. 集成和端到端测试",
                    "6. 性能调优",
                ],
                "estimated_effort": "6-10周",
                "risk_level": "medium",
            },
        }

        template = intent_templates.get(
            self.intent,
            {
                "title": "方案B: 平衡实施",
                "description": "在风险和收益之间取得平衡",
                "steps": [
                    "1. 分析需求和约束",
                    "2. 设计实施方案",
                    "3. 实现核心功能",
                    "4. 测试和优化",
                    "5. 代码审查",
                    "6. 部署和监控",
                ],
                "estimated_effort": "5-7天",
                "risk_level": "medium",
            },
        )

        return {
            "id": "solution-recommended",
            **template,
            "dependencies": project_context.get("dependencies", [])[:5],
            "pros": ["风险可控", "收益较好", "质量较高"],
            "cons": ["工作量适中", "需要经验"],
        }

    def _generate_innovative_solution(
        self,
        project_context: Dict[str, Any],
        industry_solutions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成创新方案

        Args:
            project_context: 项目上下文
            industry_solutions: 业界方案列表

        Returns:
            创新方案
        """
        # 基于意图生成创新方案
        intent_templates = {
            "bug-fix": {
                "title": "方案C: 架构优化修复",
                "description": "通过架构调整彻底解决问题，提升系统健壮性",
                "steps": [
                    "1. 分析系统架构缺陷",
                    "2. 设计改进方案",
                    "3. 引入新架构组件",
                    "4. 重构相关模块",
                    "5. 全面测试",
                    "6. 灰度发布",
                ],
                "estimated_effort": "5-10天",
                "risk_level": "high",
            },
            "new-feature": {
                "title": "方案C: 创新方案探索",
                "description": "尝试新技术或架构，追求最优解决方案",
                "steps": [
                    "1. 调研新技术方案",
                    "2. 原型验证",
                    "3. 架构设计",
                    "4. 实现和测试",
                    "5. 性能基准测试",
                    "6. 技术分享",
                ],
                "estimated_effort": "10-15天",
                "risk_level": "high",
            },
            "refactor": {
                "title": "方案C: 架构升级",
                "description": "采用现代架构模式，全面提升系统能力",
                "steps": [
                    "1. 评估新技术栈",
                    "2. 设计目标架构",
                    "3. 搭建新架构框架",
                    "4. 迁移核心功能",
                    "5. 全面测试",
                    "6. 切换和监控",
                ],
                "estimated_effort": "15-20天",
                "risk_level": "high",
            },
            "new-product": {
                "title": "方案C: 平台化思维",
                "description": "从第一天起按平台化设计，支持未来扩展和生态建设",
                "steps": [
                    "1. 定义平台核心能力和扩展点",
                    "2. 设计插件化架构",
                    "3. 实现平台基础和 SDK",
                    "4. 开发第一个标准应用",
                    "5. 开放 API 和开发者文档",
                    "6. 建立开发者生态",
                ],
                "estimated_effort": "12-24周",
                "risk_level": "high",
            },
            "from-scratch": {
                "title": "方案C: 云原生优先",
                "description": "从零开始按云原生规范设计，充分利用云平台能力",
                "steps": [
                    "1. 选定云平台和托管服务",
                    "2. 设计微服务边界",
                    "3. 实现服务网格和可观测性",
                    "4. 容器化和 K8s 部署",
                    "5. 自动扩缩容配置",
                    "6. 灾备和多区域部署",
                ],
                "estimated_effort": "8-16周",
                "risk_level": "high",
            },
        }

        template = intent_templates.get(
            self.intent,
            {
                "title": "方案C: 创新实施",
                "description": "采用新技术或方法，追求最优结果",
                "steps": [
                    "1. 调研创新方案",
                    "2. 可行性分析",
                    "3. 原型开发",
                    "4. 完整实现",
                    "5. 性能测试",
                    "6. 知识沉淀",
                ],
                "estimated_effort": "10-15天",
                "risk_level": "high",
            },
        )

        return {
            "id": "solution-innovative",
            **template,
            "dependencies": project_context.get("dependencies", [])[:5],
            "pros": ["创新性强", "长期收益高", "技术提升"],
            "cons": ["风险高", "周期长", "需要学习"],
        }

    def _adapt_industry_solution(
        self,
        industry_solution: Dict[str, Any],
        project_context: Dict[str, Any],
        index: int
    ) -> Dict[str, Any]:
        """适配业界方案到项目

        Args:
            industry_solution: 业界方案
            project_context: 项目上下文
            index: 索引

        Returns:
            适配后的方案
        """
        return {
            "id": f"solution-industry-{index}",
            "title": f"方案{chr(68+index)}: {industry_solution.get('name', '业界方案')}",
            "description": industry_solution.get("description", ""),
            "steps": [
                "1. 理解业界方案原理",
                "2. 评估适用性",
                "3. 调整适配项目",
                "4. 实施和测试",
                "5. 验证效果",
                "6. 文档记录",
            ],
            "estimated_effort": "5-10天",
            "risk_level": industry_solution.get("complexity", "medium"),
            "dependencies": project_context.get("dependencies", [])[:5],
            "pros": industry_solution.get("pros", ["业界验证"]),
            "cons": industry_solution.get("cons", ["需要适配"]),
            "reference": industry_solution.get("source", ""),
        }

    def _calculate_solution_score(
        self,
        solution: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> float:
        """计算方案评分

        Args:
            solution: 方案
            project_context: 项目上下文

        Returns:
            评分 (0-100)
        """
        score = 50.0  # 基础分

        # 风险等级评分
        risk_scores = {"low": 10, "medium": 5, "high": 0}
        score += risk_scores.get(solution.get("risk_level", "medium"), 5)

        # 优点数量评分
        pros_count = len(solution.get("pros", []))
        score += min(pros_count * 3, 15)

        # 缺点数量扣分
        cons_count = len(solution.get("cons", []))
        score -= min(cons_count * 2, 10)

        # 项目匹配度评分
        if solution.get("dependencies"):
            project_deps = set(project_context.get("dependencies", []))
            solution_deps = set(solution.get("dependencies", []))
            if project_deps & solution_deps:
                score += 10

        # 业界方案加分
        if solution.get("reference"):
            score += 10

        # 推荐方案加分
        if "recommended" in solution.get("id", ""):
            score += 5

        # 确保分数在 0-100 范围内
        return max(0.0, min(100.0, round(score, 1)))

    def _recommend(
        self,
        solutions: List[Dict[str, Any]]
    ) -> tuple[str, float]:
        """推荐最优方案

        从候选方案中选择最优方案。

        Args:
            solutions: 候选方案列表

        Returns:
            (推荐方案 ID, 置信度)
        """
        if not solutions:
            return ("no-solution", 0.0)

        # TODO: 实现推荐逻辑
        # 当前简单返回评分最高的方案
        best = max(solutions, key=lambda x: x.get("score", 0))
        score = best.get("score", 50)
        confidence = round(min(0.95, max(0.1, score / 100.0)), 2)
        return (best.get("id", "unknown"), confidence)

    def _detect_project_type(self) -> str:
        """检测项目类型

        Returns:
            项目类型: web/cli/mobile/data-pipeline/microservices
        """
        # 尝试使用 project_type_detector
        try:
            from .project_type_detector import detect_from_arch

            arch_path = self.root / "Docs" / "tech" / "ARCH.md"
            if arch_path.exists():
                return detect_from_arch(str(arch_path))
        except Exception:
            pass

        # 降级：基于文件特征检测
        indicators = {
            "web": ["index.html", "app.js", "package.json", "templates"],
            "cli": ["__main__.py", "cli.py", "main.go"],
            "mobile": ["android", "ios", "react-native", "flutter"],
            "data-pipeline": ["pipeline.py", "etl.py", "airflow", "spark"],
            "microservices": ["docker-compose.yml", "kubernetes", "grpc"],
        }

        for proj_type, files in indicators.items():
            for file in files:
                if (self.root / file).exists():
                    return proj_type

        # 默认返回 web
        return "web"

    def _detect_language(self) -> str:
        """检测主要编程语言

        Returns:
            语言名称
        """
        # 基于文件扩展名统计
        extensions = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
            ".java": "java",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
        }

        counts = {lang: 0 for lang in extensions.values()}

        SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.env', 'dist', 'build', '.pytest_cache'}

        def _should_skip(path: Path) -> bool:
            return any(part in SKIP_DIRS for part in path.parts)

        try:
            all_files = [f for f in self.root.rglob("*") if not _should_skip(f)]
            for file_path in all_files:
                if file_path.is_file():
                    ext = file_path.suffix
                    if ext in extensions:
                        counts[extensions[ext]] += 1
        except Exception:
            pass

        if max(counts.values()) > 0:
            return max(counts, key=counts.get)

        return "unknown"

    def _detect_framework(self) -> str:
        """检测使用的框架

        Returns:
            框架名称
        """
        # Python 框架检测
        framework_indicators = {
            "Flask": ["flask"],
            "Django": ["django"],
            "FastAPI": ["fastapi"],
            "Express": ["express"],
            "React": ["react"],
            "Vue": ["vue"],
            "Angular": ["angular"],
        }

        # 检查依赖文件
        dep_files = [
            "requirements.txt",
            "pyproject.toml",
            "package.json",
            "go.mod",
        ]

        all_deps = []
        for dep_file in dep_files:
            file_path = self.root / dep_file
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    all_deps.append(content.lower())
                except Exception:
                    pass

        combined = " ".join(all_deps)

        for framework, keywords in framework_indicators.items():
            if any(kw in combined for kw in keywords):
                return framework

        return "unknown"

    def _analyze_dependencies(self) -> List[str]:
        """分析项目依赖

        Returns:
            依赖列表
        """
        dependencies = []

        # Python 依赖
        req_file = self.root / "requirements.txt"
        if req_file.exists():
            try:
                content = req_file.read_text(encoding="utf-8", errors="ignore")
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # 提取包名（去掉版本号）
                        pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0]
                        if pkg:
                            dependencies.append(pkg)
            except Exception:
                pass

        # pyproject.toml 依赖
        pyproject = self.root / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding="utf-8", errors="ignore")
                # 简单解析 [dependencies] 段
                in_deps = False
                for line in content.splitlines():
                    if "[project.dependencies]" in line or "[dependencies]" in line:
                        in_deps = True
                        continue
                    if in_deps:
                        if line.strip().startswith("["):
                            break
                        if "=" in line:
                            pkg = line.split("=")[0].strip()
                            if pkg:
                                dependencies.append(pkg)
            except Exception:
                pass

        return dependencies

    def _scan_code_structure(self) -> tuple[List[str], List[str]]:
        """扫描代码结构，提取模块和函数

        Returns:
            (模块列表, 函数列表)
        """
        modules = []
        functions = []

        # 扫描常见代码目录
        code_dirs = ["scripts", "src", "lib", "app", "core"]

        for code_dir in code_dirs:
            dir_path = self.root / code_dir
            if not dir_path.exists():
                continue

            try:
                for py_file in dir_path.rglob("*.py"):
                    # 提取模块名
                    module_name = py_file.stem
                    if module_name not in ["__init__", "__main__"]:
                        modules.append(module_name)

                    # 提取函数名
                    try:
                        content = py_file.read_text(encoding="utf-8", errors="ignore")
                        import re
                        # 匹配函数定义
                        func_pattern = r"^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\("
                        for match in re.finditer(func_pattern, content, re.MULTILINE):
                            func_name = match.group(1)
                            if not func_name.startswith("_"):
                                functions.append(f"{func_name}()")
                    except Exception:
                        pass
            except Exception:
                pass

        # 去重并限制数量
        modules = list(dict.fromkeys(modules))[:20]
        functions = list(dict.fromkeys(functions))[:30]

        return modules, functions

    def _analyze_structure(self) -> Dict[str, Any]:
        """分析项目结构

        Returns:
            结构信息字典
        """
        structure = {
            "has_docs": False,
            "has_tests": False,
            "has_config": False,
            "directories": [],
        }

        try:
            # 检查关键目录
            structure["has_docs"] = (self.root / "Docs").exists()
            structure["has_tests"] = (self.root / "tests").exists() or (self.root / "test").exists()
            structure["has_config"] = (self.root / ".lifecycle").exists()

            # 列出主要目录
            for item in self.root.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    structure["directories"].append(item.name)

            structure["directories"] = structure["directories"][:10]
        except Exception:
            pass

        return structure

    def _detect_patterns(self) -> List[str]:
        """检测已使用的代码模式

        Returns:
            模式列表
        """
        patterns = []

        # 常见模式关键词
        pattern_keywords = {
            "MVC": ["model", "view", "controller"],
            "Factory": ["factory", "create"],
            "Singleton": ["singleton", "instance"],
            "Observer": ["observer", "subscribe", "notify"],
            "Strategy": ["strategy", "algorithm"],
            "Repository": ["repository", "repo"],
            "Service Layer": ["service", "business"],
        }

        SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.env', 'dist', 'build', '.pytest_cache'}

        def _should_skip(path: Path) -> bool:
            return any(part in SKIP_DIRS for part in path.parts)

        try:
            # 扫描代码文件查找模式
            all_py_files = [f for f in self.root.rglob("*.py") if not _should_skip(f)]
            for py_file in all_py_files:
                try:
                    content = py_file.read_text(encoding="utf-8", errors="ignore").lower()
                    for pattern, keywords in pattern_keywords.items():
                        if any(kw in content for kw in keywords):
                            if pattern not in patterns:
                                patterns.append(pattern)
                except Exception:
                    pass
        except Exception:
            pass

        return patterns[:10]

    def _estimate_test_coverage(self) -> float:
        """估算测试覆盖率

        Returns:
            覆盖率 (0.0-1.0)
        """
        try:
            # 统计代码文件和测试文件数量
            code_files = 0
            test_files = 0

            for py_file in self.root.rglob("*.py"):
                if "test" in py_file.name.lower() or "tests" in str(py_file).lower():
                    test_files += 1
                else:
                    code_files += 1

            if code_files > 0:
                # 简单估算：测试文件数 / 代码文件数
                ratio = min(test_files / code_files, 1.0)
                return round(ratio, 2)
        except Exception:
            pass

        return 0.0


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def analyze_solution(
    project_root: str | Path,
    intent: str,
    user_input: str
) -> Dict[str, Any]:
    """便捷函数：分析实现方案

    Args:
        project_root: 项目根目录
        intent: 用户意图
        user_input: 用户输入

    Returns:
        分析结果字典
    """
    analyzer = SolutionAnalyzer(project_root)
    return analyzer.analyze(intent, user_input)
