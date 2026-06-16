# agents/graph.py
from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph  # type: ignore[import-untyped]
from loguru import logger

from agents.reviewer import ReviewerAgent
from agents.state import CarouselState, FeedbackModel, SlideContent
from agents.writer import WriterAgent


# --- Dummy Nodes (To be implemented in subsequent steps) ---
async def scout_node(state: CarouselState) -> dict[str, Any]:
    logger.info(
        {
            "event": "node_execution",
            "node": "scout",
            "carousel_id": state["carousel_id"],
        }
    )
    return {"status": "WRITING"}


async def rag_node(state: CarouselState) -> dict[str, Any]:
    logger.info(
        {"event": "node_execution", "node": "rag", "carousel_id": state["carousel_id"]}
    )
    return {"status": "WRITING"}


async def writer_node(state: CarouselState) -> dict[str, Any]:
    logger.info(
        {
            "event": "node_execution",
            "node": "writer",
            "carousel_id": state["carousel_id"],
        }
    )

    news = state.get("raw_news")
    context = state.get("rag_context")
    raw_drafts = state.get("draft_slides")

    # CRITICAL: Deserialize feedback dict to Pydantic Model
    raw_feedback = state.get("feedback")
    feedback = FeedbackModel.model_validate(raw_feedback) if raw_feedback else None
    if not news or not context:
        logger.error(
            {
                "event": "writer_missing_context",
                "carousel_id": state["carousel_id"],
                "has_news": bool(news),
                "has_context": bool(context),
            }
        )
        return {
            "error_message": "Missing news or context for writing",
            "status": "FALLBACK",
        }

    # CRITICAL: Convert dicts back to Pydantic models for the Agent
    draft_slides = (
        [SlideContent.model_validate(slide) for slide in raw_drafts]
        if raw_drafts
        else None
    )
    writer = WriterAgent()

    try:
        slides = await writer.generate(
            topic=news.title,
            news=news,
            context=context,
            draft_slides=draft_slides,
            feedback=feedback,
        )
        # CRITICAL: Serialize Pydantic models back to dicts for safe checkpointing
        serialized_slides = [slide.model_dump() for slide in slides]
        return {"draft_slides": serialized_slides, "status": "REVIEWING"}

    except Exception as e:
        logger.error(
            {
                "event": "writer_node_failed_irrecoverably",
                "carousel_id": state["carousel_id"],
                "error": str(e),
            }
        )
        # Fallback to manual review if LLM fails after all retries
        return {"error_message": f"Writer failed: {e}", "status": "FALLBACK"}


async def reviewer_node(state: CarouselState) -> dict[str, Any]:
    logger.info(
        {
            "event": "node_execution",
            "node": "reviewer_node",
            "carousel_id": state["carousel_id"],
        }
    )

    raw_slides = state.get("draft_slides")
    context = state.get("rag_context")

    # Increment iteration counter strictly to maintain Invariant 2
    new_count = state.get("iteration_count", 0) + 1

    if not raw_slides or not context:
        logger.error(
            {"event": "reviewer_missing_data", "carousel_id": state["carousel_id"]}
        )
        return {
            "error_message": "Missing slides or context",
            "status": "FALLBACK",
            "iteration_count": new_count,
        }

    # CRITICAL: Convert dicts back to Pydantic models
    slides = [SlideContent(**slide) for slide in raw_slides]
    reviewer = ReviewerAgent()

    try:
        feedback = await reviewer.review(slides, context)
        return {
            "feedback": feedback.model_dump(),
            "iteration_count": new_count,
            "status": "APPROVED_BY_AI"
            if feedback.overall_status == "APPROVED"
            else "NEEDS_REVISION",
        }
    except Exception as e:
        logger.error({"event": "reviewer_failed_irrecoverably", "error": str(e)})
        return {
            "error_message": f"Reviewer failed: {e}",
            "status": "FALLBACK",
            "iteration_count": new_count,
        }


async def designer_node(state: CarouselState) -> dict[str, Any]:
    logger.info(
        {
            "event": "node_execution",
            "node": "designer",
            "carousel_id": state["carousel_id"],
        }
    )
    return {"status": "RENDERING"}


# --- Conditional Routing Logic ---
def route_after_review(
    state: CarouselState,
) -> Literal["approved", "revise", "fallback"]:
    """
    Determines the next node after the Reviewer Agent.
    Enforces strict invariant: Max 3 iterations to prevent infinite loops.
    """
    if state.get("iteration_count", 0) >= 3:
        logger.warning(
            {
                "event": "max_iterations_reached",
                "carousel_id": state["carousel_id"],
                "action": "routing_to_fallback",
            }
        )
        return "fallback"

    feedback = state.get("feedback")
    if feedback and feedback.overall_status == "APPROVED":
        return "approved"

    return "revise"


# --- Graph Definition ---
workflow = StateGraph(CarouselState)

workflow.add_node("scout", scout_node)  # type: ignore[reportUnknownMemberType]
workflow.add_node("rag", rag_node)  # type: ignore[reportUnknownMemberType]
workflow.add_node("writer", writer_node)  # type: ignore[reportUnknownMemberType]
workflow.add_node("reviewer_node", reviewer_node)  # type: ignore[reportUnknownMemberType]
workflow.add_node("designer", designer_node)  # type: ignore[reportUnknownMemberType]

workflow.set_entry_point("scout")
workflow.add_edge("scout", "rag")
workflow.add_edge("rag", "writer")
workflow.add_edge("writer", "reviewer_node")  # Updated reference

# Actor-Critic Loop
workflow.add_conditional_edges(
    "reviewer_node",
    route_after_review,
    {
        "approved": "designer",
        "revise": "writer",
        "fallback": END,
    },
)

workflow.add_edge("designer", END)
memory = MemorySaver()
# Compile the graph into an executable application
# PostgresSaver (checkpointing) will be injected here during integration
app = workflow.compile(checkpointer=memory, interrupt_before=["reviewer_node"])  # type: ignore[reportUnknownMemberType]
