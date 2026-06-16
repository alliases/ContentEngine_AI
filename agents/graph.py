# agents/graph.py
from typing import Any, Literal

from langgraph.graph import END, StateGraph  # type: ignore[import-untyped]
from loguru import logger

from agents.state import CarouselState


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
    return {"status": "REVIEWING"}


async def reviewer_node(state: CarouselState) -> dict[str, Any]:
    logger.info(
        {
            "event": "node_execution",
            "node": "reviewer",
            "carousel_id": state["carousel_id"],
        }
    )
    # Increment iteration count on each review
    new_count = state.get("iteration_count", 0) + 1
    return {"iteration_count": new_count}


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
workflow.add_node("reviewer", reviewer_node)  # type: ignore[reportUnknownMemberType]
workflow.add_node("designer", designer_node)  # type: ignore[reportUnknownMemberType]

workflow.set_entry_point("scout")

workflow.add_edge("scout", "rag")
workflow.add_edge("rag", "writer")
workflow.add_edge("writer", "reviewer")

# Actor-Critic Loop
workflow.add_conditional_edges(
    "reviewer",
    route_after_review,
    {
        "approved": "designer",
        "revise": "writer",
        "fallback": END,
    },
)

workflow.add_edge("designer", END)

# Compile the graph into an executable application
# PostgresSaver (checkpointing) will be injected here during integration
app = workflow.compile()  # type: ignore[reportUnknownMemberType]
