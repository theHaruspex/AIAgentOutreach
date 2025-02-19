import logging

logger = logging.getLogger(__name__)


def end_execution_loop(summary: str) -> dict:
    """
    Function to indicate that the execution loop is complete and provide a summary.

    Args:
        summary (str): A short summary explaining why execution is ending.

    Returns:
        dict: A standardized response indicating that the execution loop has ended, including the summary.
    """
    if not summary:
        raise ValueError("The 'summary' parameter is required and cannot be empty.")

    # Log or process the summary if needed
    logger.info(f"Execution loop ended with summary: {summary}")

    # Return the standardized response
    return {
        "status": "Execution loop completed",
        "summary": summary
    }
