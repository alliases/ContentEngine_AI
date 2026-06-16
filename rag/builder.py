# rag/builder.py
from loguru import logger

from agents.state import FewShotContext
from rag.retriever import StyleRetriever


async def build_few_shot_context(
    news_text: str, tenant_id: str, trace_id: str
) -> FewShotContext:
    """
    Constructs the Few-Shot context for the LLM by combining similar posts
    and generating a brand voice summary. Strictly isolates execution per tenant.
    """
    # Inject trace_id and tenant_id into all subsequent loguru calls within this block
    with logger.contextualize(trace_id=trace_id, tenant_id=tenant_id):
        logger.info({"event": "building_few_shot_context_started"})

        try:
            retriever = StyleRetriever()

            # Retrieve similar texts isolated by tenant_id
            examples = await retriever.get_similar_posts(
                query_text=news_text, tenant_id=tenant_id
            )

            # Since the current StyleRetriever returns list[str], we mock the scores.
            # In a fully refined version, the retriever would return ScoredPoint equivalents.
            similarity_scores = [0.85] * len(examples)

            # Fallback/Basic brand voice summary.
            # In Phase 4, this could be an LLM-generated summary based on the examples.
            brand_voice_summary = (
                "Professional, insightful, and concise. "
                "Uses structured bullet points and engaging hooks."
            )

            context = FewShotContext(
                examples=examples,
                similarity_scores=similarity_scores,
                brand_voice_summary=brand_voice_summary,
            )

            logger.info(
                {
                    "event": "building_few_shot_context_completed",
                    "examples_found": len(examples),
                }
            )
            return context

        except Exception as e:
            logger.error(
                {
                    "event": "few_shot_context_failed",
                    "error": str(e),
                }
            )
            # Fault Tolerance: Return empty valid context to prevent pipeline crash
            return FewShotContext(
                examples=[],
                similarity_scores=[],
                brand_voice_summary="Neutral and professional tone.",
            )
