import logging
import re
from dataclasses import dataclass
from typing import Optional, Dict
from app.schemas.agent import ChatConfig
from app.core.llm.client import get_llm
from app.services.config_service import ConfigService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeModelInfo:
    """Non-sensitive description of the model selected for the current phase."""

    configured_model: str
    effective_model_id: str
    source: str
    phase: str = "primary_agent"
    is_fallback: bool = False
    resolution_status: str = "direct"
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    def public_dict(self) -> Dict[str, object]:
        return {
            "configured_model": self.configured_model,
            "effective_model_id": self.effective_model_id,
            "source": self.source,
            "phase": self.phase,
            "is_fallback": self.is_fallback,
            "resolution_status": self.resolution_status,
        }


async def _lookup_registered_model(model: str):
    """Look up an active model alias without exposing its credentials."""
    try:
        from app.core.orm import AsyncSessionLocal
        from app.models.ai_model import AIModel
        from sqlalchemy import or_, select

        async with AsyncSessionLocal() as session:
            stmt = select(AIModel).where(
                AIModel.is_active == True,
                or_(AIModel.model_id == model, AIModel.name == model),
            )
            result = await session.execute(stmt)
            return result.scalars().first()
    except Exception as exc:
        logger.warning("Failed to lookup runtime model registry: %s", exc)
        raise


async def resolve_runtime_model_info(
    *,
    config: Optional[ChatConfig] = None,
    model_override: Optional[str] = None,
    debug_options: Optional[Dict[str, object]] = None,
    phase: str = "primary_agent",
    is_fallback: bool = False,
) -> RuntimeModelInfo:
    """Resolve the public, effective model identity using the LLM priority order."""
    llm_config = await ConfigService.get_all_from_db()

    def get_val(key: str, default: str) -> str:
        return llm_config.get(key, {}).get("value") or default

    from app.core.context import get_debug_option

    explicit_debug_model = (debug_options or {}).get("model")
    debug_model = explicit_debug_model or get_debug_option("model")
    if model_override:
        configured_model = str(model_override)
        source = "runtime_override"
    elif debug_model:
        configured_model = str(debug_model)
        source = "debug_override"
    elif config and config.model_name:
        configured_model = str(config.model_name)
        source = "agent_config"
    else:
        configured_model = str(get_val("llm_model_name", "deepseek-chat"))
        source = "system_default"

    try:
        registered = await _lookup_registered_model(configured_model)
    except Exception:
        return RuntimeModelInfo(
            configured_model=configured_model,
            effective_model_id=configured_model,
            source=source,
            phase=phase,
            is_fallback=is_fallback,
            resolution_status="registry_unresolved",
        )

    if registered is not None:
        return RuntimeModelInfo(
            configured_model=configured_model,
            effective_model_id=str(getattr(registered, "model_id", None) or configured_model),
            source=source,
            phase=phase,
            is_fallback=is_fallback,
            resolution_status="registry_resolved",
            api_key=getattr(registered, "api_key", None),
            base_url=getattr(registered, "api_base_url", None),
        )

    return RuntimeModelInfo(
        configured_model=configured_model,
        effective_model_id=configured_model,
        source=source,
        phase=phase,
        is_fallback=is_fallback,
        resolution_status="direct",
    )

class AgentConfigProvider:
    """
    Handles LLM instantiation and environment configuration for Agents.
    """
    
    @staticmethod
    async def get_configured_llm(
        streaming: bool = True, 
        config: Optional[ChatConfig] = None,
        model_override: Optional[str] = None,
        temp_override: Optional[float] = None
    ):
        """
        Instantiates an AgentScope LLM based on system config, agent-specific overrides, or runtime overrides.
        
        Priority:
        1. Runtime Override (model_override/temp_override from Tool Runtime Config)
        2. Debug Options (User session debug)
        3. Agent Config (ChatConfig)
        4. System Defaults
        """
        # Fetch dynamic config from DB
        llm_config = await ConfigService.get_all_from_db()
        
        def get_val(key, default):
            return llm_config.get(key, {}).get("value") or default

        runtime_model_info = await resolve_runtime_model_info(
            config=config,
            model_override=model_override,
        )

        # Check Debug Context Overrides
        from app.core.context import get_debug_option

        # 1. Model Name Priority (centralized in resolve_runtime_model_info)
        model = runtime_model_info.effective_model_id

        # 2. Temperature Priority
        debug_temp = get_debug_option("temperature")
        
        if temp_override is not None:
            temperature = float(temp_override)
        elif debug_temp is not None:
             temperature = float(debug_temp)
        elif config and config.temperature is not None:
             temperature = float(config.temperature)
        else:
             temp_str = get_val("llm_temperature", None)
             temperature = float(temp_str) if temp_str is not None else 0.0
             
        api_key = get_val("llm_api_key", None)
        base_url = get_val("llm_base_url", None)

        # 3. Model registry credentials are kept out of the public metadata payload.
        if runtime_model_info.api_key:
            api_key = runtime_model_info.api_key
        if runtime_model_info.base_url:
            base_url = runtime_model_info.base_url

        return get_llm(
            streaming=streaming,
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature
        )

    @staticmethod
    async def get_synthesis_llm(
        streaming: bool = True, 
        config: Optional[ChatConfig] = None
    ):
        """
        Instantiates the LLM specifically for the Synthesis (final response) phase.
        
        Fallback Logic:
        1. Synthesis-specific config (synthesis_model_name)
        2. Primary Agent config (model_name)
        3. System Defaults
        """
        if config and config.synthesis_model_name:
            # Use synthesis-specific overrides
            return await AgentConfigProvider.get_configured_llm(
                streaming=streaming,
                config=config,
                model_override=config.synthesis_model_name,
                temp_override=config.synthesis_temperature
            )
        
        # Default fallback to primary model
        return await AgentConfigProvider.get_configured_llm(
            streaming=streaming,
            config=config
        )

    @staticmethod
    async def get_fallback_llm(
        streaming: bool = True,
        config: Optional[ChatConfig] = None,
        exclude_model: Optional[str] = None,
    ):
        """Fallback native model for AgentScope ModelConfig: system default only."""
        try:
            llm_config = await ConfigService.get_all_from_db()
        except Exception:
            llm_config = {}

        def get_val(key, default=None):
            return llm_config.get(key, {}).get("value") or default

        candidate = get_val("llm_model_name")
        if not candidate or (exclude_model and candidate == exclude_model):
            return None
        try:
            return await AgentConfigProvider.get_configured_llm(
                streaming=streaming,
                config=config,
                model_override=candidate,
            )
        except Exception:
            return None

    @staticmethod
    async def _generate_dataset_menu_content(user_id: Optional[int] = None, is_admin: bool = False) -> str:
        """
        Internal method to generate the dataset menu string from DB, filtered by permissions and status.
        """
        menu = "Available Datasets (Look for Table terms to find relevant data):\n"
        try:
            from app.core.orm import AsyncSessionLocal
            from app.models.metadata import MetaDataset
            from app.services.metadata_service import MetadataService
            from sqlalchemy.orm import selectinload

            async with AsyncSessionLocal() as session:
                # 使用 MetadataService.search_datasets 进行权限和状态过滤 (status=1 为启用)
                datasets = await MetadataService.search_datasets(
                    session,
                    query=None,
                    user_id=user_id,
                    is_admin=is_admin,
                    status=1 # 仅限启用状态
                )
            
            if not datasets:
                return menu + "  (No authorized datasets available)"
            else:
                for ds in datasets:
                    name = getattr(ds, "name", "unknown")
                    display_name = str(getattr(ds, "display_name", "") or "").strip()
                    desc = getattr(ds, "description", "No description")
                    tags = getattr(ds, "tags", [])

                    tag_str = f" [{', '.join(tags)}]" if isinstance(tags, list) and tags else ""
                    menu += f"- Dataset: {name}{tag_str}\n"
                    if display_name and display_name != name:
                        menu += f"  Display Name: {display_name}\n"
                    menu += f"  Description: {desc}\n"

                    active_tables = [
                        tbl for tbl in (getattr(ds, "tables", None) or [])
                        if getattr(tbl, "status", 1) != 0
                    ]
                    table_terms: list[str] = []
                    for tbl in active_tables:
                        term = str(getattr(tbl, "term", None) or getattr(tbl, "physical_name", "") or "").strip()
                        if term:
                            table_terms.append(term)
                    if table_terms:
                        menu += f"  Includes Tables: {', '.join(table_terms)}\n"
                        menu += "  Table Details:\n"
                        for tbl in active_tables:
                            term = str(getattr(tbl, "term", None) or getattr(tbl, "physical_name", "") or "").strip()
                            if not term:
                                continue
                            table_desc = re.sub(
                                r"\s+",
                                " ",
                                str(getattr(tbl, "description", "") or "").strip(),
                            )
                            if table_desc:
                                menu += f"    - {term}: {table_desc}\n"
                            else:
                                menu += f"    - {term}\n"

                    metrics = [
                        m for m in (getattr(ds, "metrics", None) or [])
                        if getattr(m, "display_name", None) or getattr(m, "name", None)
                    ]
                    if metrics:
                        metric_labels = [
                            str(getattr(m, "display_name", None) or getattr(m, "name", "")).strip()
                            for m in metrics
                        ]
                        metric_labels = [label for label in metric_labels if label]
                        if metric_labels:
                            menu += f"  Metrics: {', '.join(metric_labels)}\n"

                    menu += "\n"
                return menu
        except Exception as e:
            logger.error(f"Failed to load dataset menu internally: {e}")
            return menu + f"  (System Error: Failed to load dataset menu)"

    @staticmethod
    async def get_dataset_menu(user_id: Optional[int] = None, is_admin: bool = False, force_refresh: bool = False) -> str:
        """
        Fetches authorized datasets to assist LLM reasoning. Cached via Redis per user.
        """
        from app.core.redis import get_redis
        redis = await get_redis()
        
        # 1. Try Cache (按用户隔离，admin 共享一个 key)
        cache_key = f"agent:dataset_menu:{'admin' if is_admin else user_id or 'anon'}"
        if not force_refresh:
            try:
                if redis:
                    cached_menu = await redis.get(cache_key)
                    if cached_menu:
                        return cached_menu
            except Exception as e:
                logger.warning(f"Redis error for dataset menu: {e}")

        # 2. Cache Miss: Fetch from DB
        content = await AgentConfigProvider._generate_dataset_menu_content(user_id, is_admin)

        # 3. Save to Cache (TTL: 90 days)
        try:
            if redis:
                await redis.set(cache_key, content, ex=90 * 24 * 60 * 60)
        except Exception as e:
            logger.warning(f"Redis set error: {e}")
        
        return content

    @staticmethod
    async def refresh_dataset_menu():
        """
        Force regenerate the dataset menu and update Redis cache.
        Should be called when datasets or tables are modified.
        """
        from app.core.redis import get_redis
        from app.services.dataset_navigation_service import DatasetNavigationService

        try:
            redis = await get_redis()
            if redis:
                async for key in redis.scan_iter(match="agent:dataset_menu:*", count=200):
                    await redis.delete(key)
                await redis.delete("agent:dataset_menu")
            await DatasetNavigationService.invalidate_all_navigation_caches()
            logger.info("Dataset menu and navigation caches invalidated.")
            # 异步启动后台预热任务，温和预热最近活跃用户的门户缓存
            import asyncio
            asyncio.create_task(DatasetNavigationService.warm_up_navigation_caches_background())
        except Exception as e:
            logger.error(f"Failed to refresh dataset menu cache: {e}")

    @staticmethod
    async def invalidate_dataset_menu_cache(user_id: Optional[int] = None, is_admin: bool = False):
        """
        Invalidate dataset menu cache for a specific user.
        """
        from app.core.redis import get_redis
        try:
            redis = await get_redis()
            if redis:
                cache_key = f"agent:dataset_menu:{'admin' if is_admin else user_id or 'anon'}"
                await redis.delete(cache_key)
                logger.info(f"Dataset menu cache invalidated for key: {cache_key}")
            from app.services.dataset_navigation_service import DatasetNavigationService
            await DatasetNavigationService.invalidate_navigation_cache_for_user(
                user_id=user_id,
                is_admin=is_admin,
            )
        except Exception as e:
            logger.warning(f"Failed to invalidate dataset menu cache for user {user_id}: {e}")
