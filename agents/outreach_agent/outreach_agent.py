import os
import logging
from agents.agent.base_agent import BaseAgent
from agents.outreach_agent.outreach_tools import OutreachTools

logger = logging.getLogger(__name__)

class OutreachAgent(BaseAgent):
    """
    OutreachAgent is designed to handle a minimal, railroaded email workflow with a single step:
      1. process_email_and_label

    It follows the same three-step workflow as other BaseAgent descendants:
      1. Deliberation (no tools)
      2. Execution loop (with tools)
      3. Final response

    This agent is specialized to use `EmailTools` for interacting with Gmail (via GmailClient).
    """

    # ---------------------------------------------------------
    # Agent Persona & Tools Description
    # ---------------------------------------------------------
    PERSONA = (
        "You are an OutreachAgent. Your primary focus is to assist with a minimal email workflow:\n"
        "\n"
        "RESPONSIBILITIES:\n"
        "1. Process an email with an optional attachment.\n"
        "2. Automatically label the email for easy retrieval.\n"
        "3. If a request is unclear, ask clarifying questions.\n"
        "4. If you are given a specific email address to send to, pass that specific email address along to Execution.\n\n"
        "LIMITATIONS:\n"
        "1. You can only use the 'process_email_and_label' method from EmailTools.\n"
        "2. You must NEVER send an actual email unless explicitly prompted (and the method to do so isn’t provided here).\n"
        "3. If exact draft text is provided by the user, you must use it **exactly as written**, without making any edits, additions, or omissions.\n\n"
        "GUIDING PRINCIPLE:\n"
        "Focus on correctness and minimalism. Fulfill the user’s requests regarding processing emails and labeling them, "
        "without deviating from provided instructions."
    )

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o-mini",
        outreach_label: str = "default_label",
        send_mode: bool = False
    ):
        """
        Initialize the OutreachAgent.

        :param api_key: The API key for your OpenAI-based model (inherited from BaseAgent).
        :param model_name: Which model to use (inherited from BaseAgent).
        """
        super().__init__(api_key=api_key, model_name=model_name)

        logger.debug("Initializing OutreachAgent...")

        # 1. Persona & Tools Description
        self.add_system_message(self.deliberation_messages, self.PERSONA)
        self.add_system_message(self.execution_messages, self.PERSONA)

        # 2. Load any optional JSON schema describing the tool definitions
        script_dir = os.path.dirname(__file__)
        tools_path = os.path.join(script_dir, "outreach_tools.json")
        self.load_tools_from_json(tools_path)

        # 3. Instantiate EmailTools
        self.email_tools = OutreachTools(outreach_label=outreach_label, send_mode=send_mode)

        logger.debug("OutreachAgent initialized successfully.")

    # -------------------------------------------------------------------------
    # Tool Handling
    # -------------------------------------------------------------------------
    def _handle_specific_tool(self, function_name: str, arguments: dict):
        """
        Overrides BaseAgent's method to handle OutreachAgent's specific minimal workflow tool:
          - process_email_and_label
        """
        logger.debug(f"Handling tool call: {function_name} with arguments: {arguments}")

        if function_name == "process_email_and_label":
            return self._process_process_email_and_label(arguments)
        else:
            logger.warning(f"Unrecognized tool call: {function_name}")
            return {"error": f"Tool {function_name} not recognized by OutreachAgent."}

    # -------------------------------------------------------------------------
    # Tool-Specific Processor
    # -------------------------------------------------------------------------
    def _process_process_email_and_label(self, arguments: dict):
        """
        Processor for process_email_and_label(to_addrs, subject, body, attachment_path|attachment_paths).

        Expected arguments:
          - to_addrs (List[str]): Recipient email addresses
          - subject (str): Email subject
          - body (str): Email body
          - Either:
                attachment_paths (List[str]) for multiple attachments
             OR attachment_path (str) for a single attachment
        """
        to_addrs = arguments.get("to_addrs", [])
        subject = arguments.get("subject", "")
        body = arguments.get("body", "")

        # For backwards compatibility, check if we have `attachment_path` (single) or `attachment_paths` (multiple)
        attachment_paths = arguments.get("attachment_paths", None)
        single_path = arguments.get("attachment_path", None)

        # If a single attachment path is provided, convert it to a list
        if attachment_paths is None and single_path:
            attachment_paths = [single_path]
        elif attachment_paths is None:
            attachment_paths = []

        # Validate required parameters
        if not to_addrs or not subject or not body:
            logger.error(
                "process_email_and_label aborted: Missing 'to_addrs', 'subject', or 'body'."
            )
            return {
                "error": (
                    "process_email_and_label aborted: 'to_addrs', 'subject', and 'body' are all required parameters."
                )
            }

        return self.email_tools.process_email_and_label(
            to_addrs=to_addrs,
            subject=subject,
            body=body,
            attachment_paths=attachment_paths,
        )