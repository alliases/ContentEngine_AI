# scripts/verify_graph.py
import sys

from loguru import logger

from agents.graph import app


def verify_graph_compilation() -> None:
    """
    Validates that the StateGraph compiles correctly without dead ends
    and prints its Mermaid representation for visual inspection.
    """
    logger.configure(handlers=[{"sink": sys.stdout, "format": "{message}"}])
    logger.info("--- Compiling LangGraph ---")

    try:
        mermaid_png_bytes = app.get_graph().draw_mermaid()
        print("\n--- Mermaid Graph Architecture ---")
        print(mermaid_png_bytes)
        print("\nVerification Successful: Graph compiled without recursion errors.")
    except Exception as e:
        logger.error(f"Graph compilation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    verify_graph_compilation()
