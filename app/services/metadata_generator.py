from typing import Dict, Any, List, Optional
import logging
import json
import re
from pydantic import BaseModel, Field
from app.services.ai.runtime.agentscope.compat import HumanMessage, SystemMessage
from app.services.ai.agent_manager import AgentManagerService
from app.services.ai.config import AgentConfigProvider
from app.core.orm import AsyncSessionLocal

logger = logging.getLogger(__name__)

class ColumnMetadata(BaseModel):
    physical_name: str = Field(description="数据库物理列名")
    term: str = Field(description="业务术语，如 '机房名称' 而非 'room_name'")
    type: str = Field(description="字段数据类型")
    description: str = Field(description="详细的业务含义描述")
    enums: List[Dict[str, Any]] = Field(default=[], description="枚举值列表，如 [{'value': 0, 'label': '正常'}]")
    synonyms: List[str] = Field(default=[], description="该字段的同义词，用于增强检索")

class TableMetadata(BaseModel):
    physical_name: str = Field(description="数据库物理表名")
    term: str = Field(description="业务术语，如 '资产配置表'")
    description: str = Field(description="该表存储的数据内容概要")
    synonyms: List[str] = Field(default=[], description="表的同义词")
    columns: List[ColumnMetadata] = Field(description="字段列表")

class MetricMetadata(BaseModel):
    name: str = Field(description="指标物理名")
    display_name: str = Field(description="指标显示名")
    description: str = Field(description="指标逻辑描述")
    calculation_logic: str = Field(description="具体的 SQL 计算逻辑")
    unit: str = Field(default="", description="单位 (e.g. 'kWh', '%')")

class RelationshipMetadata(BaseModel):
    source_table: str = Field(description="源表物理名")
    target_table: str = Field(description="目标表物理名")
    type: str = Field(description="关联类型: one_to_one, one_to_many, many_to_one")
    condition: str = Field(description="关联条件 (e.g. 't1.id = t2.t1_id')")
    description: str = Field(description="关系描述")

class ImportResult(BaseModel):
    tables: List[TableMetadata] = Field(description="识别出的所有表结构")
    metrics: List[MetricMetadata] = Field(default=[], description="识别出的业务指标")
    relationships: List[RelationshipMetadata] = Field(default=[], description="识别出的表关联关系")

class RelationshipRecommendation(BaseModel):
    source_table: str = Field(description="源表物理名（必须是 Schema 中实际存在的物理表名）")
    target_table: str = Field(description="目标表物理名（必须是 Schema 中实际存在的物理表名）")
    condition: str = Field(description="关联条件 JOIN 表达式，如 't1.id = t2.t1_id'，使用物理表/字段名")
    relation_type: str = Field(description="关联类型: one_to_one, one_to_many, many_to_one")
    description: str = Field(description="该关联关系的业务含义描述")
    confidence: float = Field(
        description="置信度打分，0~1 之间的小数，值越高表示模型对这条关联关系越有把握",
        ge=0,
        le=1,
    )
    source: str = Field(default="AI", description="推荐来源标识，默认 'AI'，可填 'FK'/'NAMING'/'AI' 等")

class RelationshipRecommendationResult(BaseModel):
    relationships: List[RelationshipRecommendation] = Field(description="推荐的表关联关系列表")

class MetricRecommendationResult(BaseModel):
    metrics: List[MetricMetadata] = Field(description="推荐的高价值业务指标列表")

class DatasetEnhanceResult(BaseModel):
    description: str = Field(description="数据集的业务背景描述，100字以内")
    tags: List[str] = Field(description="数据集的标签列表，如 ['财务', '生产', '核心数据']")

class MetadataGeneratorService:
    @staticmethod
    def _format_instructions(model_cls: type[BaseModel]) -> str:
        schema = json.dumps(model_cls.model_json_schema(), ensure_ascii=False)
        return (
            "必须只返回一个 JSON 对象，不要 Markdown，不要解释文字。"
            f"JSON Schema:\n{schema}"
        )

    @staticmethod
    def _extract_json(raw: str) -> Dict[str, Any]:
        """从模型输出中提取完整的 JSON 对象，兼容说明文字和 Markdown 代码块。"""
        text = (raw or "").strip()
        if not text:
            raise ValueError("模型返回内容为空，无法解析 JSON")

        # 代码块优先解析，避免说明文字中出现 JSON 示例时误取外层文本。
        candidates = [text]
        fenced_match = re.search(
            r"```(?:json)?\s*(.*?)```",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if fenced_match:
            candidates.insert(0, fenced_match.group(1).strip())

        decoder = json.JSONDecoder()
        last_error: Optional[Exception] = None
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
                last_error = ValueError("模型返回的 JSON 顶层结构不是对象")
            except json.JSONDecodeError as exc:
                last_error = exc

            # 使用 JSONDecoder 扫描每个对象起点，正确处理字符串中的花括号，
            # 同时避免原贪婪正则把多个对象或截断文本拼成一个无效 JSON。
            valid_objects = []
            stripped_candidate = candidate.lstrip()
            if stripped_candidate.startswith("{"):
                # 输出以对象开头时只尝试外层对象，避免外层截断后误返回嵌套对象。
                scan_starts = [candidate.find("{")]
            else:
                # 输出包含前置说明时，扫描所有对象起点以兼容说明文字。
                scan_starts = [
                    start for start, char in enumerate(candidate) if char == "{"
                ]

            for start in scan_starts:
                try:
                    parsed, end = decoder.raw_decode(candidate[start:])
                except json.JSONDecodeError as exc:
                    last_error = exc
                    continue
                if isinstance(parsed, dict):
                    valid_objects.append((end, parsed))

            if valid_objects:
                # 外层对象通常覆盖范围最大，优先返回它而不是字符串中的嵌套对象。
                _, parsed = max(valid_objects, key=lambda item: item[0])
                logger.info(
                    "从模型输出中提取嵌入式 JSON 对象成功: raw_length=%s",
                    len(candidate),
                )
                return parsed

        logger.error(
            "模型 JSON 输出解析失败: raw_length=%s, error=%s",
            len(text),
            last_error,
        )
        if last_error is not None:
            raise last_error
        raise ValueError("模型返回内容无法解析为 JSON 对象")

    @staticmethod
    async def _invoke_json(
        llm: Any,
        result_model: type[BaseModel],
        system_prompt_template: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        system_prompt = system_prompt_template.replace(
            "{format_instructions}",
            MetadataGeneratorService._format_instructions(result_model),
        )
        response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        raw = getattr(response, "content", "") or str(response)
        try:
            data = MetadataGeneratorService._extract_json(raw)
            return result_model.model_validate(data).model_dump()
        except (json.JSONDecodeError, ValueError) as first_error:
            # 截断或轻微格式漂移时重试一次，避免把一次模型输出异常直接暴露给接口。
            logger.warning(
                "模型结构化输出首次解析失败，准备重试: model=%s, raw_length=%s, error=%s",
                getattr(llm, "model", "unknown"),
                len(raw),
                first_error,
            )
            retry_system_prompt = (
                f"{system_prompt}\n\n"
                "【结构化输出重试要求】上一次输出未通过 JSON 或 Schema 校验。"
                "请重新生成完整结果：只返回一个可被 json.loads 解析的 JSON 对象，"
                "不要 Markdown、不要解释文字；保持描述简洁、避免重复关系，确保所有字符串、"
                "数组及对象都完整闭合。"
            )
            retry_response = await llm.ainvoke(
                [
                    SystemMessage(content=retry_system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
            retry_raw = getattr(retry_response, "content", "") or str(retry_response)
            try:
                retry_data = MetadataGeneratorService._extract_json(retry_raw)
                return result_model.model_validate(retry_data).model_dump()
            except (json.JSONDecodeError, ValueError) as retry_error:
                logger.error(
                    "模型结构化输出重试仍然失败: model=%s, first_raw_length=%s, "
                    "retry_raw_length=%s, error=%s",
                    getattr(llm, "model", "unknown"),
                    len(raw),
                    len(retry_raw),
                    retry_error,
                    exc_info=True,
                )
                raise retry_error from first_error

    @staticmethod
    async def _save_trace_log(trace_id: str, step: int, event: str, output: Any, error: str = None, execution_time: float = 0):
        """Helper to save a single trace log entry"""
        try:
            from app.core.orm import AsyncSessionLocal
            from app.models.audit import AgentExecutionTrace
            from app.services.ai.audit_payload import bound_audit_payload
            import json
            from datetime import datetime
            
            async with AsyncSessionLocal() as session:
                log = AgentExecutionTrace(
                    trace_id=trace_id,
                    step_number=step,
                    event_type=event,
                    agent_name="MetadataGenerator",
                    tool_name="LLM",
                    tool_input={}, # Can be populated if needed
                    tool_output=bound_audit_payload(
                        output if isinstance(output, (dict, list)) else {"raw": str(output)}
                    ),
                    execution_time_ms=execution_time,
                    status="error" if error else "success",
                    error_message=error,
                    created_at=datetime.now()
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to save trace log: {e}", exc_info=True)

    @staticmethod
    async def generate_from_ddl(
        content: str,
        data_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        利用 LLM 对输入内容进行深度语义分析，提取并推断业务元数据。
        支持 DDL、Markdown 表格或自然语言描述。
        """
        from app.services.config_service import ConfigService
        import uuid
        import time
        
        trace_id = f"import-{str(uuid.uuid4())}"
        start_total = time.time()
        
        try:
            # Step 1: Initialization
            await MetadataGeneratorService._save_trace_log(
                trace_id,
                1,
                "start",
                {
                    "input_length": len(content),
                    "preview": content[:200],
                    "data_source": data_source or "default_clickhouse",
                },
            )

            # 1. 获取 LLM (适配 Model Management)
            from app.services.ai.config import AgentConfigProvider
            from app.schemas.agent import ChatConfig
            
            # 3. 获取智能体配置 (Metadata Specialist)
            async with AsyncSessionLocal() as session:
                agent_config = await AgentManagerService.get_active_agent_config(
                    session, agent_name='metadata-specialist'
                )
            
            # Prepare overrides if agent_config exists
            # Prepare overrides if agent_config exists
            chat_config = agent_config
            
            if not chat_config:
                logger.warning("Metadata Specialist config not found in DB, using system default model.")

            # Get configured LLM (automatically handles ai_models lookup or system default)
            llm = await AgentConfigProvider.get_configured_llm(streaming=False, config=chat_config)

            # 4. Resolve System Prompt
            if not agent_config or not agent_config.system_prompt:
                system_prompt_template = (
                    "你是一个资深的业务分析师和数据库建模专家。\n"
                    "请分析用户提供的数据库 DDL、Markdown 表格或自然语言描述，提取出精确的元数据结构。\n"
                    "确保推断出合理的业务术语(term)和详细的字段描述。\n"
                    "{format_instructions}"
                )
            else:
                system_prompt_template = agent_config.system_prompt
                # Ensure format_instructions is present if not already in DB prompt
                if "{format_instructions}" not in system_prompt_template:
                    system_prompt_template += "\n\n{format_instructions}"

            from app.services.sql_query_execution_service import dialect_from_data_source

            sql_dialect = dialect_from_data_source(data_source)
            dialect_instruction = (
                "PostgreSQL 标准 SQL（日期转换使用 CAST、DATE_TRUNC、EXTRACT，禁止使用 toDate、"
                "parseDateTimeBestEffort、toDateTime、toYYYYMM 等 ClickHouse 函数）"
                if sql_dialect == "postgres"
                else f"{sql_dialect} 标准 SQL（禁止使用其他数据库的专有函数）"
            )
            # 将方言约束放入系统提示，避免数据库专属提示词覆盖用户消息中的兼容要求。
            system_prompt_template = (
                f"{system_prompt_template.rstrip()}\n\n"
                f"【业务指标 SQL 方言要求】calculation_logic 必须使用{dialect_instruction}。"
            )
            logger.info(
                "开始从 DDL 生成元数据: data_source=%s, sql_dialect=%s",
                data_source or "default_clickhouse",
                sql_dialect,
            )

            logger.info(f"Generating metadata for content (first 100 chars): {content[:100]}...")
            
            
            # 3. 调用 LLM
            start_llm = time.time()
            result = await MetadataGeneratorService._invoke_json(
                llm,
                ImportResult,
                system_prompt_template,
                f"请分析以下内容并生成元数据。业务指标 calculation_logic 必须使用{dialect_instruction}。\n\n{content}",
            )
            
            duration_llm = (time.time() - start_llm) * 1000
            
            logger.info(f"LLM Result: {json.dumps(result, ensure_ascii=False)[:200]}...")
            
            table_name = result.get('physical_name') or (result.get('tables')[0].get('physical_name') if result.get('tables') else 'unknown')
            logger.info(f"Successfully generated metadata for table: {table_name}")
            
            await MetadataGeneratorService._save_trace_log(trace_id, 4, "llm_success", result, execution_time=duration_llm)
            
            # Return result AND trace_id
            if isinstance(result, dict):
                result["_trace_id"] = trace_id
            
            return result
        except Exception as e:
            logger.error(f"Error generating metadata: {str(e)}", exc_info=True)
            duration_error = (time.time() - start_total) * 1000
            await MetadataGeneratorService._save_trace_log(trace_id, 5, "error", {"error_str": str(e)}, error=str(e), execution_time=duration_error)
            
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"智能解析失败，请检查日志。Trace ID: {trace_id}. Error: {str(e)}")

    @staticmethod
    async def recommend_metrics(
        dataset_id: int,
        schema_context: str,
        user_prompt: Optional[str] = None,
        existing_metrics: Optional[List[Any]] = None,
        data_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        根据数据集 Schema 推荐业务指标，支持用户自定义需求与10分钟内防重复推荐
        """
        import uuid
        import time
        from app.core.redis import get_redis
        from app.services.config_service import ConfigService
        from app.services.ai.agent_manager import AgentManagerService
        from app.schemas.agent import ChatConfig
        
        trace_id = f"metric-rec-{str(uuid.uuid4())}"
        start_total = time.time()
        
        try:
            # 1. Log Start
            await MetadataGeneratorService._save_trace_log(
                trace_id, 1, "start_recommendation",
                {"dataset_id": dataset_id, "schema_len": len(schema_context), "has_user_prompt": bool(user_prompt)}
            )

            # 2. 读取 10 分钟内近期已推荐指标 (Redis) 和数据库已有指标
            redis_client = await get_redis()
            recent_key = f"metadata:metric_rec:recent:{dataset_id}"
            recent_names: set[str] = set()
            if redis_client:
                try:
                    cached_items = await redis_client.smembers(recent_key)
                    if cached_items:
                        for item in cached_items:
                            val = item.decode("utf-8") if isinstance(item, bytes) else str(item)
                            if val.strip():
                                recent_names.add(val.strip())
                except Exception as ex:
                    logger.warning(f"Failed to read recent recommended metrics from Redis: {ex}")

            db_existing_names: set[str] = set()
            if existing_metrics:
                for m in existing_metrics:
                    name = getattr(m, "name", None) or (m.get("name") if isinstance(m, dict) else "")
                    display_name = getattr(m, "display_name", None) or (m.get("display_name") if isinstance(m, dict) else "")
                    if name and str(name).strip():
                        db_existing_names.add(str(name).strip())
                    if display_name and str(display_name).strip():
                        db_existing_names.add(str(display_name).strip())

            all_excluded_names = db_existing_names.union(recent_names)

            # 3. Get Agent Config
            async with AsyncSessionLocal() as session:
                agent_config = await AgentManagerService.get_active_agent_config(
                    session, agent_name='metadata-specialist'
                )
            
            chat_config = agent_config
            if not chat_config:
                 logger.warning("Metadata Specialist config not found, using default.")

            # Get configured LLM
            llm = await AgentConfigProvider.get_configured_llm(streaming=False, config=chat_config)

            # 4. 根据数据集绑定的数据源生成方言约束，避免 PostgreSQL 误用 ClickHouse 函数。
            from app.services.sql_query_execution_service import dialect_from_data_source

            sql_dialect = dialect_from_data_source(data_source)
            dialect_instructions = {
                "postgres": (
                    "目标数据源为 PostgreSQL。calculation_logic 必须使用 PostgreSQL 标准 SQL；"
                    "日期转换使用 CAST(field AS DATE/TIMESTAMP)、DATE_TRUNC、EXTRACT，"
                    "禁止使用 ClickHouse 的 toDate、parseDateTimeBestEffort、toDateTime、toYYYYMM 等函数。"
                ),
                "mysql": (
                    "目标数据源为 MySQL。calculation_logic 必须使用 MySQL 标准 SQL；"
                    "日期转换使用 DATE(field)、DATE_FORMAT 等函数，禁止使用 ClickHouse 专有函数。"
                ),
                "oracle": (
                    "目标数据源为 Oracle。calculation_logic 必须使用 Oracle 标准 SQL；"
                    "日期转换使用 TRUNC、TO_DATE、TO_CHAR 等函数，禁止使用 ClickHouse 专有函数。"
                ),
                "tsql": (
                    "目标数据源为 SQL Server。calculation_logic 必须使用 SQL Server 标准 SQL；"
                    "日期转换使用 CAST/CONVERT、DATEPART 等函数，禁止使用 ClickHouse 专有函数。"
                ),
            }
            dialect_instruction = dialect_instructions.get(
                sql_dialect,
                "目标数据源为 ClickHouse。calculation_logic 可以使用 ClickHouse 标准 SQL 日期函数。",
            )
            logger.info(
                "开始推荐业务指标: dataset_id=%s, data_source=%s, sql_dialect=%s",
                dataset_id,
                data_source or "未指定",
                sql_dialect,
            )

            # 5. 组装 Prompt
            prompt_segments = [
                "你是一个精通数据分析的 BI 专家。",
                "请分析给定的数据库 Schema（包含表结构、字段含义），推荐 5-10 个**最有业务价值**的分析指标。",
                "指标类型可以是：",
                "1. **聚合型 (KPI)**: 如总数、平均值、比率 (e.g., 'PUE均值', '机房总数')。",
                "2. **维度分布 (Dimension)**: 如按类别分组统计 (e.g., '各区域机房分布', '设备类型占比')。",
                "3. **常用视图 (Data View)**: 常用查询字段组合 (e.g., '机房详细列表: 名称, 编码, 地址')。\n",
                "对于 SQL (calculation_logic 字段)：",
                f"- {dialect_instruction}",
                "- 对于分布/视图类，请写出完整的 `SELECT ... FROM ... [GROUP BY ...]` 语句。",
                "- 禁止使用中文别名。"
            ]

            if user_prompt and user_prompt.strip():
                prompt_segments.append(
                    f"\n【用户特定业务需求与偏好】：\n{user_prompt.strip()}\n请务必重点贴合上述用户需求来设计和发掘指标。"
                )

            if all_excluded_names:
                excluded_list_str = "、".join(sorted(list(all_excluded_names))[:40])
                prompt_segments.append(
                    f"\n【去重与排除约束（严禁重复推荐）】：\n以下指标已在系统中存在或近期10分钟内刚刚推荐过，请务必不要推荐名称或业务含义与下列重复/雷同的指标：\n{excluded_list_str}\n请发掘其他未被覆盖的高价值业务分析维度或指标。"
                )

            prompt_segments.append("{format_instructions}")
            system_prompt = "\n".join(prompt_segments)
            
            # 6. Invoke LLM
            start_llm = time.time()
            result = await MetadataGeneratorService._invoke_json(
                llm,
                MetricRecommendationResult,
                system_prompt,
                f"Schema 定义如下：\n\n{schema_context}",
            )
            duration_llm = (time.time() - start_llm) * 1000

            # 7. 后置去重过滤与写入 Redis 10分钟缓存
            raw_metrics = result.get("metrics", []) if isinstance(result, dict) else (getattr(result, "metrics", []) if hasattr(result, "metrics") else [])
            filtered_metrics = []
            new_metric_names = []

            for m in raw_metrics:
                m_dict = m if isinstance(m, dict) else (m.model_dump() if hasattr(m, "model_dump") else dict(m))
                name = (m_dict.get("name") or "").strip()
                display_name = (m_dict.get("display_name") or "").strip()

                # 后置过滤与已有名称完全冲突的项
                if name in all_excluded_names or display_name in all_excluded_names:
                    logger.info(f"Filtered out duplicate recommended metric: {name} / {display_name}")
                    continue

                filtered_metrics.append(m_dict)
                if name:
                    new_metric_names.append(name)
                if display_name:
                    new_metric_names.append(display_name)

            # 更新结果列表（若全被过滤则保留原始结果，避免返回空）
            if isinstance(result, dict):
                result["metrics"] = filtered_metrics if filtered_metrics else raw_metrics
                result["_trace_id"] = trace_id

            # 写入 Redis 缓存，TTL 600 秒
            if redis_client and new_metric_names:
                try:
                    await redis_client.sadd(recent_key, *new_metric_names)
                    await redis_client.expire(recent_key, 600)
                except Exception as ex:
                    logger.warning(f"Failed to save recommended metrics to Redis: {ex}")
            
            # 8. Log Success
            await MetadataGeneratorService._save_trace_log(trace_id, 4, "llm_success", result, execution_time=duration_llm)
                
            return result

        except Exception as e:
            logger.error(f"Error recommending metrics: {e}", exc_info=True)
            await MetadataGeneratorService._save_trace_log(trace_id, 5, "error", {"error": str(e)})
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"指标推荐失败: {str(e)}")

    @staticmethod
    async def recommend_relationships(
        dataset_id: int,
        schema_context: str,
        user_prompt: Optional[str] = None,
        existing_relationships: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        根据数据集 Schema 智能推荐实体（表）之间的关联关系。
        支持 10 分钟内 Redis 历史去重、DB 已有关系排除以及用户自定义 Prompt 偏好注入。
        仅输出建议，不自动入库，供用户人工判断确认。
        """
        import uuid
        import time
        import json
        from app.core.redis import get_redis
        from app.services.ai.agent_manager import AgentManagerService

        trace_id = f"rel-rec-{str(uuid.uuid4())}"
        start_total = time.time()

        # 1. 查询近 10 分钟已推荐的关联关系缓存（避免短期内频繁推荐相同关联）
        recent_recommended_keys = set()
        redis_client = None
        redis_key = f"metadata:rel_rec:recent:{dataset_id}"
        try:
            redis_client = await get_redis()
            cached_data = await redis_client.get(redis_key)
            if cached_data:
                recent_list = json.loads(cached_data)
                for item in recent_list:
                    src = item.get("source_table", "").strip().lower()
                    tgt = item.get("target_table", "").strip().lower()
                    cond = item.get("condition", "").strip().lower()
                    if src and tgt:
                        pair_key = tuple(sorted([src, tgt])) + (cond,)
                        recent_recommended_keys.add(pair_key)
        except Exception as e:
            logger.warning(f"Failed to read recent relationship recommendations from Redis: {e}")

        # 整理负向排除清单（既有关系 + 近期推荐关系）
        exclude_descriptions = []
        if existing_relationships:
            for r in existing_relationships:
                exclude_descriptions.append(f"- 已存在关系: {r}")

        try:
            # 1. Log Start
            await MetadataGeneratorService._save_trace_log(
                trace_id, 1, "start_recommendation",
                {
                    "dataset_id": dataset_id,
                    "schema_len": len(schema_context),
                    "user_prompt": user_prompt,
                    "recent_cached_count": len(recent_recommended_keys),
                    "existing_rels_count": len(existing_relationships or [])
                },
            )

            # 2. Get Agent Config
            async with AsyncSessionLocal() as session:
                agent_config = await AgentManagerService.get_active_agent_config(
                    session, agent_name='metadata-specialist'
                )

            chat_config = agent_config
            if not chat_config:
                logger.warning("Metadata Specialist config not found, using default.")

            # Get configured LLM
            llm = await AgentConfigProvider.get_configured_llm(streaming=False, config=chat_config)

            # 3. Prompt Construction
            system_prompt = (
                "你是一个精通数据建模的 DBA/数据架构师。\n"
                "请分析给定的数据库 Schema（包含每张表的字段、业务术语、字段描述），推断表与表之间可能存在的高质量关联关系。\n\n"
                "推断规则：\n"
                "1. **字段语义匹配**：优先基于字段的业务术语/描述、命名相似性（如某表的 'id'/'code' 对应另一表的 'xxx_id'/'xxx_code'、主外键命名模式）推断关联。\n"
                "2. **业务逻辑关联**：结合表名与字段描述判断它们是否描述同一业务实体（如订单与订单明细、用户与用户日志）。\n"
                "3. **避免重复与负向约束**：**严禁推荐数据库中已存在或近期已推荐过的关联关系**，只输出新的潜在关联。\n"
                "4. **只推荐当前 Schema 内真实存在的表**：source_table/target_table 必须使用 Schema 中的物理表名。\n\n"
            )

            if exclude_descriptions:
                system_prompt += (
                    "【必须严格排除的已有关系列表】（请勿再次推荐以下关系）：\n"
                    + "\n".join(exclude_descriptions[:20])
                    + "\n\n"
                )

            if user_prompt:
                system_prompt += (
                    "【用户自定义业务偏好与重点关注方向】（必须优先结合此偏好发掘关联）：\n"
                    f"{user_prompt}\n\n"
                )

            system_prompt += (
                "输出要求：\n"
                "- 根据给定的 Schema 规模，尽可能多地输出所有合理且有实际业务价值的关联关系，"
                "不设置数量上限；表较多时优先输出高置信度关系，并确保 JSON 完整闭合。\n"
                "- condition 使用 '物理表别名1.字段 = 物理表别名2.字段' 形式，例如 't1.order_id = t2.id'。\n"
                "- relation_type 取值：one_to_one / one_to_many / many_to_one。\n"
                "- confidence 是 0~1 之间的小数，表示你对该关联关系成立的自信心（优先输出高置信度的关系）。\n"
                "- description 用不超过 80 个中文字符简述该关联的业务含义。\n"
                "{format_instructions}"
            )

            # 4. Invoke
            start_llm = time.time()
            result = await MetadataGeneratorService._invoke_json(
                llm,
                RelationshipRecommendationResult,
                system_prompt,
                f"Schema 定义如下：\n\n{schema_context}",
            )
            duration_llm = (time.time() - start_llm) * 1000

            # 5. 代码级后置去重与 Redis 写入 (TTL 10 分钟 = 600s)
            raw_relationships = result.get("relationships", []) if isinstance(result, dict) else []
            filtered_relationships = []
            new_cache_items = []

            for rel in raw_relationships:
                src = (rel.get("source_table") or "").strip().lower()
                tgt = (rel.get("target_table") or "").strip().lower()
                cond = (rel.get("condition") or "").strip().lower()
                if not src or not tgt:
                    continue

                pair_key = tuple(sorted([src, tgt])) + (cond,)
                if pair_key in recent_recommended_keys:
                    continue

                filtered_relationships.append(rel)
                new_cache_items.append({
                    "source_table": rel.get("source_table"),
                    "target_table": rel.get("target_table"),
                    "condition": rel.get("condition"),
                    "ts": time.time()
                })

            if isinstance(result, dict):
                result["relationships"] = filtered_relationships
                result["_trace_id"] = trace_id

            if redis_client and new_cache_items:
                try:
                    await redis_client.setex(
                        redis_key,
                        600,
                        json.dumps(new_cache_items, ensure_ascii=False)
                    )
                except Exception as ex:
                    logger.warning(f"Failed to cache recent relationship recommendations to Redis: {ex}")

            # 6. Log Success
            await MetadataGeneratorService._save_trace_log(
                trace_id, 4, "llm_success", result, execution_time=duration_llm
            )

            return result

        except Exception as e:
            logger.error(f"Error recommending relationships: {e}", exc_info=True)
            await MetadataGeneratorService._save_trace_log(trace_id, 5, "error", {"error": str(e)})
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"关系推荐失败: {str(e)}")

    @staticmethod
    async def enhance_dataset_metadata(dataset_id: int, tables_summary: str) -> Dict[str, Any]:
        """
        AI 辅助: 根据表信息动态生成数据集的【描述】和【标签】
        """
        import uuid
        import time
        from app.services.ai.agent_manager import AgentManagerService
        
        trace_id = f"ds-enhance-{str(uuid.uuid4())}"
        start_total = time.time()
        
        try:
            # 1. Log Start
            await MetadataGeneratorService._save_trace_log(trace_id, 1, "start_dataset_enhance", {"dataset_id": dataset_id, "tables_summary": tables_summary})

            # 2. Get Agent Config
            async with AsyncSessionLocal() as session:
                agent_config = await AgentManagerService.get_active_agent_config(
                    session, agent_name='metadata-specialist'
                )
            
            # Get configured LLM
            llm = await AgentConfigProvider.get_configured_llm(streaming=False, config=agent_config)

            # 3. Prompt
            system_prompt = (
                "你是一个精通元数据管理的业务架构师。\n"
                "请分析给定的数据集包含的【表信息】（物理名及业务术语），为该数据集生成专业的【业务描述】和【分类标签】。\n\n"
                "要求：\n"
                "1. description: 100字以内的业务背景描述，说明该数据集主要用于解决什么业务问题。\n"
                "2. tags: 3-5个简短的标签，如 ['财务', '生产', '核心', '监控'] 等。\n"
                "{format_instructions}"
            )
            
            # 4. Invoke
            start_llm = time.time()
            result = await MetadataGeneratorService._invoke_json(
                llm,
                DatasetEnhanceResult,
                system_prompt,
                f"该数据集包含以下表信息：\n\n{tables_summary}",
            )
            duration_llm = (time.time() - start_llm) * 1000
            
            # 5. Log Success
            await MetadataGeneratorService._save_trace_log(trace_id, 4, "llm_success", result, execution_time=duration_llm)
            
            if isinstance(result, dict):
                result["_trace_id"] = trace_id
                
            return result

        except Exception as e:
            logger.error(f"Error enhancing dataset metadata: {e}", exc_info=True)
            await MetadataGeneratorService._save_trace_log(trace_id, 5, "error", {"error": str(e)})
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"AI 辅助生成元数据失败: {str(e)}")
