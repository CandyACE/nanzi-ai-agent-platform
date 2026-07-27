import logging
import json
from typing import Optional
from app.services.ai.tools.tool_compat import tool
from app.services.chatbi_example_service import ExampleService

logger = logging.getLogger(__name__)

@tool
async def search_qa_examples(query: str, top_k: Optional[int] = 5) -> str:
    """
    Search historical Q&A examples from the approved example library (问答经验库).
    This tool should be used when you need to find similar historical questions and their corresponding SQL implementations as a reference.

    Args:
        query: The user's question or search keywords to find similar historical examples.
        top_k: (Optional) Max number of examples to return. Defaults to 5.
    """
    try:
        logger.info(f"[ExampleSearchTool] Called with query='{query}', top_k={top_k}")
        
        # We don't have explicit dataset_id and history in this generic tool call, 
        # so we pass None to let it search globally across approved examples.
        examples = await ExampleService.search_examples(
            query=query, 
            dataset_id=None, 
            top_k=top_k, 
            history=None
        )
        
        if not examples:
            return json.dumps({
                "status": "empty",
                "message": f"未在经验库中找到与 '{query}' 相关的优质案例。"
            }, ensure_ascii=False)
            
        # Format the result nicely for the LLM
        formatted_context = "【检索到的经验库案例】:\n\n"
        for i, ex in enumerate(examples):
            question = ex.get('question', '未知问题')
            sql = ex.get('sql', '无 SQL')
            dataset_name = ex.get('dataset_name', '通用')
            similarity = ex.get('similarity', 0)
            
            formatted_context += f"--- 案例 {i+1} [相似度: {similarity:.2f} | 数据集: {dataset_name}] ---\n"
            formatted_context += f"用户问题: {question}\n"
            formatted_context += f"优质 SQL:\n```sql\n{sql}\n```\n\n"
            
        # Return structured JSON so that if needed, other layers can parse it
        result = {
            "status": "success",
            "content": formatted_context,
            "count": len(examples)
        }
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as e:
        err_msg = str(e)
        logger.error(f"[ExampleSearchTool] Failed to search examples: {e}", exc_info=True)
        return f"[Tool Error] 经验库检索失败: {err_msg}"
