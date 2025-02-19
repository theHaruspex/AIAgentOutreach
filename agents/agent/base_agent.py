# agents/agent/base_agent.py

import json
import logging

from openai import OpenAI
import tiktoken

logger = logging.getLogger("reply_tests")

class BaseAgent:
    BASE_SYSTEM_MESSAGE = (
        "You are a specialized multi-stage agent designed to solve complex tasks by operating in two distinct stages:\n\n"
        "**1. Deliberation Period (Stage 1)**:\n"
        "**2. Execution Loop (Stage 2)**:\n"

        "**Memory Access and Scope**:\n"
        "- You will only have access to memory relevant to the current stage you are in.\n"
        "- Context from previous stages will be summarized and provided to you as needed.\n"
        "- Your task is to trust the information provided for the current stage and work within those constraints.\n\n"

        "**Overall Objectives**:\n"
        "- Efficiently plan, execute, and synthesize a solution while minimizing unnecessary actions or redundant tool calls.\n"
        "- Always strive for clarity, conciseness, and relevance in your outputs.\n\n"

        "**Stimuli and Responses**:\n"
        "- When given a user query (Stage 1), create a clear and actionable plan.\n"
        "- When entering Stage 2, follow the plan and adapt based on the tool outputs.\n"

        "Remember, your success depends on adhering to the staged workflow and producing meaningful, stage-appropriate outputs."
    )
    # -------------------------------------------------------------------------
    # Stage-Specific System Messages
    # -------------------------------------------------------------------------
    DELIBERATION_MESSAGE = (
        "You are in Stage 1: **Deliberation Period (Tools Unavailable)**.\n\n"

        "Your task in this stage is to carefully analyze the user's query and create an extremely detailed, granular, step-by-step plan to achieve their goal. "
        "You do not have access to tools at this stage, but you can review the tools available to you and their required arguments.\n\n"

        "**Instructions**:\n"
        "1. **Understand the Query**: Start by interpreting the user's request and determining the core objectives.\n"
        "   - If the user's request implies multiple repetitive actions, explicitly detail each individual step as a separate function call, "
        "     even if the steps involve performing the same operation repeatedly.\n"
        "   - Every single operation must be broken down into its smallest possible actionable unit, corresponding to a single function call.\n"
        "   - If the number of steps (e.g., iterations or repeated actions) is unclear, explicitly document this uncertainty and include a plan for how Execution will determine the total step count using available tools.\n\n"

        "2. **Analyze Available Tools**: Examine the tools available to you, including their functions and the required arguments.\n"
        "   - Consider how each tool might help address different parts of the query.\n"
        "   - If a tool is used repetitively, ensure that each invocation is planned separately with explicit details for every instance.\n"
        "   - If the query requires determining the scope of a task (e.g., how many items exist to process), identify and incorporate a tool call early in Execution to calculate or verify this scope.\n\n"

        "3. **Incorporate Progress Monitoring**:\n"
        "   - Identify tools that can periodically check progress or validate results during execution.\n"
        "   - Plan to include these progress-checking steps at logical intervals, especially for repetitive or multi-step tasks.\n"
        "   - Use these checks to ensure intermediate steps are being performed correctly and to adjust the plan if needed.\n\n"

        "4. **Create a Granular Step-by-Step Plan**:\n"
        "   - Break down the user's query into the smallest possible steps.\n"
        "   - For **each and every step**, specify:\n"
        "       a. The exact tool you plan to use.\n"
        "       b. The arguments you will provide to the tool for that specific call.\n"
        "       c. The expected results from the tool.\n"
        "       d. How the result will contribute to solving the user's query.\n"
        "       e. Any progress-checking or validation steps needed after the tool call.\n"
        "   - If a step requires calling the same tool multiple times (e.g., retrieving 10 messages individually), explicitly document each call as a separate step.\n"
        "   - If the number of steps is unknown or dynamic, include a plan for Execution to determine this count (e.g., by listing items first).\n\n"

        "5. **Conclude with 'end_execution_loop'**:\n"
        "   - The final step of your plan must always include the function call `end_execution_loop`.\n"
        "   - Use this function to signal the completion of all planned actions or to provide a summary if the task cannot be completed.\n"
        "   - Include any relevant final summary or status as part of the `end_execution_loop` call.\n\n"

        "6. **Summarize Your Playbook**: Provide a highly detailed and granular strategy that explains your approach:\n"
        "   - Include a complete sequence of individual tool calls, even if repetitive.\n"
        "   - Ensure that the plan collectively addresses the user's query in a logical, step-by-step manner.\n"
        "   - Highlight where progress checks will occur and how they will be used to refine execution.\n"
        "   - Include an explicit total step count (or steps for each repeated action). If the step count cannot be determined during Deliberation, document the exact method for how Execution will calculate it.\n\n"

        "7. **Data Transfer to Execution**:\n"
        "   - During Deliberation, identify any relevant raw data from the user's query that is needed in Execution.\n"
        "   - Explicitly repeat that data  **verbatim** in your plan summary for the Execution stage, ensuring no details are lost or altered.\n"
        "   - If portions of the user query might be reused in multiple function calls, outline where and how that data will be passed.\n\n"

        "**Constraints**:\n"
        "- Ensure every step is planned in the smallest possible actionable units.\n"
        "- Avoid skipping details or combining steps, even if repetitive tasks are involved.\n"
        "- Ensure the plan always ends with the function call `end_execution_loop`.\n"
        "- If the user's request is unclear, specify the ambiguities and how you plan to clarify them in subsequent stages.\n\n"

        "Your primary goal in this stage is to create an exhaustive and actionable playbook for the next stage (Execution Loop), "
        "ensuring every function call is individually detailed and accounted for, regardless of repetition or simplicity. "
        "Incorporate progress-monitoring steps to validate and refine the process during execution as needed."
    )

    EXECUTION_MESSAGE = (
        "You are now in Stage 2: **Execution Loop (Tools Optional)**.\n"
        "- Your primary goal in this stage is to execute all planned actions step by step without skipping or combining any steps.\n"
        "- Emphasize a 'look before you leap' approach: For every action, first forecast what you will do in one message, then execute it in a separate message.\n\n"

        "**Core Responsibilities**:\n"
        "1. **Step-by-Step Execution**:\n"
        "   - Execute each tool call exactly as planned, ensuring that every single action is performed individually.\n"
        "   - **Look Before You Leap Workflow**:\n"
        "     1. **Forecast Message**: Before making a tool call, provide a short explanation of what you are about to do and why.\n"
        "        - Example: 'Next, I will use the `list_items` tool to retrieve all pending items for processing.'\n"
        "     2. **Execution Message**: In the following message, perform the actual tool call or action.\n"
        "     - If making multiple calls to the same tool, maintain a running tally of your progress.\n"
        "       - Example: Executing tool call 1/20, 2/20, so on and so forth.\n\n"

        "2. **Progress Tracking and Verification**:\n"
        "   - At regular intervals or when you believe the task may be nearing completion, double-check your progress.\n"
        "   - Use tools (if available) to confirm that all planned steps have been completed and no remaining work is left.\n"
        "   - If verification reveals remaining tasks, continue executing the plan until everything is complete.\n\n"

        "3. **Error Handling**:\n"
        "   - If an error prevents progress on a specific step, retry the action once. If the error persists, log the issue and proceed to the next step.\n"
        "   - If multiple errors prevent further progress, summarize partial findings and prepare to exit the loop.\n\n"

        "**Ending the Execution Loop**:\n"
        "1. **Explicit Exit Requirement**:\n"
        "   - You must call the function `end_execution_loop` explicitly to indicate that the Execution Stage is complete.\n\n"

        "2. **Final Checks Before Exiting**:\n"
        "   - Before calling `end_execution_loop`, confirm that all planned steps are completed or that further progress is impossible.\n"
        "   - Use tools, if necessary, to verify task completion.\n"
        "   - Example: 'I will now use `list_items` to confirm that no pending items remain.'\n\n"

        "3. **Provide a Summary**:\n"
        "   - When calling `end_execution_loop`, include a concise summary of:\n"
        "     - What was accomplished.\n"
        "     - Any remaining work, if applicable.\n"
        "     - Any errors or issues encountered.\n"
        "   - Example: 'All items have been processed successfully. No remaining tasks.'\n\n"

        "When you have either:\n"
        " - Completed all planned steps, **or**\n"
        " - Encountered unrecoverable errors preventing further progress,\n"
        "call `end_execution_loop` with an appropriate summary. This will signal the end of Stage 2."
    )

    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini"):
        """
        BaseAgent initializes common agent behavior:
        - Manages stage-specific conversations to reduce token usage.
        - Loads and stores tool definitions.
        - Tracks token usage for budgeting.
        """

        import os

        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name

        # Maintain separate message lists for each stage
        self.deliberation_messages = []
        self.execution_messages = []

        # Also store the user's original input for reference
        self.user_input = None

        # Tooling and token usage
        self.tools = []
        self.total_tokens = 0

        # Dynamically resolve the relative path to `base_agent_tools.json`
        base_dir = os.path.dirname(__file__)  # Directory of the BaseAgent module
        self.tools_description = ''
        json_path = os.path.join(base_dir, "base_agent_tools.json")

        # Load base tools
        try:
            self.load_tools_from_json(json_path)
            logger.info(f"Tools loaded successfully: {self.tools}")
        except FileNotFoundError:
            logger.error(f"File not found: {json_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON in {json_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error while loading tools from {json_path}: {str(e)}")

        # Add the BASE_SYSTEM_MESSAGE to all message tracks
        self.add_system_message(self.deliberation_messages, self.BASE_SYSTEM_MESSAGE)
        self.add_system_message(self.execution_messages, self.BASE_SYSTEM_MESSAGE)

    # -------------------------------------------------------------------------
    # Message Management
    # -------------------------------------------------------------------------
    def add_system_message(self, stage_messages: list, content: str):
        stage_messages.append({"role": "system", "content": content})

    def add_user_message(self, stage_messages: list, content: str):
        stage_messages.append({"role": "user", "content": content})

    def add_assistant_message(self, stage_messages: list, content: str):
        stage_messages.append({"role": "assistant", "content": content})

    # -------------------------------------------------------------------------
    # Tooling and Token Usage
    # -------------------------------------------------------------------------
    def load_tools_from_json(self, json_path: str):
        """
        Loads a JSON file containing 'tools' definitions (array or dict with a 'tools' key),
        appends them to self.tools, and generates a string description saved in self.tools_description.
        """
        try:
            # Read the JSON file
            with open(json_path, "r", encoding="utf-8") as f:
                tool_data = json.load(f)

            # Check if tool_data is a list or a dictionary with a 'tools' key
            if isinstance(tool_data, list):
                tools = tool_data
            elif isinstance(tool_data, dict) and "tools" in tool_data:
                tools = tool_data["tools"]
            else:
                logger.warning(
                    f"Invalid JSON structure in {json_path}. Expected a top-level list or a dictionary with a 'tools' key."
                )
                return

            # Extend the tools list
            self.tools.extend(tools)

            # Generate the tools description
            tool_descriptions = []
            for tool in tools:
                function = tool.get("function", {})
                name = function.get("name", "Unknown Tool")
                description = function.get("description", "No description available.")
                parameters = function.get("parameters", {}).get("properties", {})
                params_str = "\n      ".join(
                    f"- {name} ({details.get('type', 'Unknown')}): {details.get('description', 'No description.')}"
                    for name, details in parameters.items()
                )
                tool_descriptions.append(
                    f"Tool: {name}\n"
                    f"  Description: {description}\n"
                    f"  Parameters:\n      {params_str if parameters else 'None'}"
                )

            # Save the generated description
            self.tools_description = "\n\n".join(tool_descriptions)

            logger.info(f"Tools successfully loaded and description generated from {json_path}.")

        except FileNotFoundError as e:
            logger.error(f"File {json_path} not found.")
            raise(e)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {json_path}: {str(e)}")


    def track_token_usage(self, response) -> int:
        """
        Updates the total token usage for this instance based on the response.
        """
        tokens_used = response.usage.total_tokens
        self.total_tokens += tokens_used
        return tokens_used

    def _num_tokens_from_string(self, string: str, encoding_name: str) -> int:
        """
        Returns the number of tokens in a text string.
        """
        encoding = tiktoken.get_encoding(encoding_name)
        num_tokens = len(encoding.encode(string))
        return num_tokens

    # -------------------------------------------------------------------------
    # Model Call Handling
    # -------------------------------------------------------------------------
    def _call_model(
            self,
            messages: list,
            use_tools: bool = True,
            max_retries: int = 5
    ):
        """
        Makes a call to the OpenAI ChatCompletion API with the given messages.
        Optionally includes function-calling `tools` if `use_tools` is True.
        Retries if a token limit error occurs.
        """
        if not hasattr(self, "_token_error_count"):
            self._token_error_count = 0

        while self._token_error_count < max_retries:
            try:
                tools = self.tools if use_tools else None

                # Estimate token usage for the messages
                str_messages = "".join(msg["content"] for msg in messages if "content" in msg)
                expected_tokens = self._num_tokens_from_string(str_messages, "cl100k_base")

                if expected_tokens > 13000:
                    raise ValueError("Token usage exceeds the maximum allowed limit of 13000.")

                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=tools
                )

                # # Log the raw response for infoging
                logger.info("Model response received:")
                logger.info(self.extract_response_content(response))

                # Track token usage
                self.track_token_usage(response)
                self._token_error_count = 0  # Reset on success
                return response

            except ValueError as e:
                self._token_error_count += 1
                if self._token_error_count >= max_retries:
                    raise ValueError("Repeated token limit errors. Unable to proceed.") from e

                # Add a system message warning the agent in the same message list
                warning_message = (
                    "Warning: The previous response exceeded the token limit. "
                    "The next response must be shorter."
                )
                self.add_system_message(messages, warning_message)
                logger.warning(f"Token limit exceeded. Warning issued: {warning_message}")

    def extract_response_content(self, response: dict) -> str:
        """
        Extracts the assistant's content from the response object.
        """
        try:
            return response.choices[0].message.content
        except (AttributeError, IndexError) as e:
            raise ValueError("Invalid response object format") from e

    def _parse_tool_call(self, response):
        """
        Checks if the model decided to call any tool. If so, parses the
        function arguments, and returns them for further handling.
        """
        if not response.choices:
            return None, None, response

        tool_calls = response.choices[0].message.tool_calls
        if not tool_calls:
            return None, None, response

        tool_call = tool_calls[0]
        function_name = tool_call.function.name
        arguments_str = tool_call.function.arguments

        try:
            arguments = json.loads(arguments_str)
        except json.JSONDecodeError:
            return None, None, response

        return function_name, arguments, response

    # -------------------------------------------------------------------------
    # Public Workflow Entry
    # -------------------------------------------------------------------------
    def process_user_input(self, user_message: str):
        """
        Public entry point for handling user input across Deliberation,
        Execution, and Synthesis, returning the final user-facing response.
        """
        self.user_input = user_message

        # 1) Deliberation Stage (No Tools)
        plan_content = self._enforce_deliberation_stage()

        # 2) Execution Stage (Tools Allowed)
        self.add_user_message(self.execution_messages, user_message)
        execution_exit_statement = self._execute_plan(plan_content)

        return execution_exit_statement

    # -------------------------------------------------------------------------
    # Deliberation Stage
    # -------------------------------------------------------------------------
    def _enforce_deliberation_stage(self) -> str:
        """
        Ensures the agent operates in Deliberation mode to produce a plan/playbook
        without calling any tools. Returns the plan content.
        """

        # Add system message for Deliberation
        self.add_system_message(self.deliberation_messages, self.DELIBERATION_MESSAGE)

        # Add the user's message so the model knows the original query
        self.add_user_message(self.deliberation_messages, self.user_input)

        # Add the description of available tools for planning
        self.add_system_message(self.deliberation_messages, self.tools_description)

        # Call the model with no tools
        response = self._call_model(self.deliberation_messages, use_tools=False)
        plan_content = self.extract_response_content(response)

        # Record the plan content from the assistant
        self.add_assistant_message(self.deliberation_messages, plan_content)

        return plan_content

    # -------------------------------------------------------------------------
    # Execution Stage
    # -------------------------------------------------------------------------
    def _execute_plan(self, plan_content: str, max_iterations: int = 99, final_checks: int = 0) -> str:
        """
        Executes the plan (i.e., calls tools as necessary) until an 'end_execution_loop' function call is made.
        Includes an additional confirmation step to ensure the agent is ready to finalize the loop.
        Returns the final summary from the Execution stage.
        """
        logger.info("Execution Stage: Starting execution of the plan.")
        logger.info(f"Execution Stage: Initial plan content:\n{plan_content}")

        # Add system message for Execution
        self.add_system_message(self.execution_messages, self.EXECUTION_MESSAGE)

        # Add user message for Execution
        self.add_user_message(self.execution_messages, self.user_input)


        # Pass the plan content as a system-level message
        self.add_system_message(self.execution_messages, f"Deliberation Plan: {plan_content}")

        iteration_count = 0
        exit_statement = ""
        exit_attempts = 0  # Tracks the number of times 'end_execution_loop' is called

        while iteration_count < max_iterations:
        # while True:
        #     self.add_system_message("okay, actually, the exit function loop is turned off. so continue")

            logger.info(f"Execution Stage: Iteration {iteration_count + 1}.")

            try:
                # Make a call to the model (tools allowed)
                response = self._call_model(self.execution_messages, use_tools=True)
                function_name, arguments, _ = self._parse_tool_call(response)

                # Log the response and parsed function call
                logger.info(f"Model response:\n{response}")
                logger.info(f"Function call detected: {function_name}, with arguments: {arguments}")

                if not function_name:
                    # The model returned no function calls, which is not valid under the new rules
                    warning_message = (
                        "Warning: You must call the function 'end_execution_loop' to finalize Execution Stage. "
                        "No function calls were detected in your last response. Please either continue tool usage or "
                        "call 'end_execution_loop' if you are finished."
                    )
                    logger.warning("Execution Stage: No function call detected. Adding warning to system messages.")
                    self.add_system_message(self.execution_messages, warning_message)
                    iteration_count += 1
                    continue

                if function_name == "end_execution_loop":
                    # The agent is indicating it's done or cannot proceed
                    logger.info(
                        "Execution Stage: Detected 'end_execution_loop'. Parsing summary and confirming readiness to exit.")
                    exit_statement = arguments.get("summary", "")
                    if not exit_statement:
                        logger.warning("Execution Stage: No summary provided in 'end_execution_loop' call.")
                        exit_statement = "No summary provided by end_execution_loop."

                    # Record the assistant message to store the final content
                    self.add_assistant_message(
                        self.execution_messages,
                        f"[end_execution_loop] Summary: {exit_statement}"
                    )

                    if exit_attempts < final_checks:
                        # Prompt the agent to confirm if it's ready to exit
                        confirmation_message = (
                            f"Confirmation Needed: This is your attempt {exit_attempts} to end the Execution Loop. "
                            "Are you positive this is the final answer? If so, submit a final `end_execution_loop` call. "
                            "If not, please continue working to finalize the task.\n"
                            "HINT: If you have a tool to check your progress, use it!"
                        )
                        logger.info("Execution Stage: Adding confirmation message for final checks.")
                        self.add_system_message(self.execution_messages, confirmation_message)
                        exit_attempts += 1
                        iteration_count += 1
                        continue  # Allow the agent to confirm or continue
                    else:
                        break  # Final exit confirmed

                else:
                    # Handle a normal tool call
                    logger.info(f"Execution Stage: Handling tool call '{function_name}'.")
                    tool_result = self._handle_specific_tool(function_name, arguments)
                    logger.info(f"Tool result for '{function_name}': {tool_result}")

                    formatted_result = self._format_tool_result(tool_result)
                    logger.info(f"Formatted tool result for '{function_name}':\n{formatted_result}")

                    # Log the tool usage into the conversation
                    self.add_system_message(
                        self.execution_messages,
                        f"Function called: {function_name}\n"
                        f"Arguments passed: {json.dumps(arguments, indent=2)}\n"
                        f"Result:\n{formatted_result}"
                    )

            except Exception as e:
                raise(e)
                logger.error(f"Execution Stage: Error encountered during iteration {iteration_count + 1}: {e}")
                self.add_system_message(
                    self.execution_messages,
                    f"Error encountered: {str(e)}. Execution will continue if possible."
                )

            iteration_count += 1
            logger.info(f"Execution Stage: Iteration {iteration_count} completed.")

        if iteration_count >= max_iterations:
            logger.warning(f"Execution Stage: Maximum iterations ({max_iterations}) reached. Exiting loop.")
            self.add_system_message(
                self.execution_messages,
                "Execution stopped due to reaching the maximum iteration limit."
            )

        logger.info("Execution Stage: Exiting with summary.")
        logger.info(f"Final exit statement: {exit_statement}")
        return exit_statement
    # -------------------------------------------------------------------------
    # Synthesis Stage
    # -------------------------------------------------------------------------

    def _format_tool_result(self, tool_result: dict, indent: int = 2, max_length: int = 1000) -> str:
        """
        Formats tool results from JSON to a human-readable string.

        Args:
            tool_result (dict): The raw tool result in JSON format.
            indent (int): Indentation level for pretty printing.
            max_length (int): Maximum length of the formatted result string.

        Returns:
            str: A formatted and human-readable version of the tool result.
        """
        try:
            # Convert the JSON to a pretty-printed string
            formatted_result = json.dumps(tool_result, indent=indent)

            # Truncate if the result is too long
            if len(formatted_result) > max_length:
                formatted_result = formatted_result[:max_length] + "... [truncated]"

            return formatted_result
        except (TypeError, ValueError) as e:
            # Handle non-JSON serializable tool results gracefully
            return f"Unable to format tool result: {str(e)}"


    # -------------------------------------------------------------------------
    # Optional: Tool Handling
    # -------------------------------------------------------------------------
    def _handle_specific_tool(self, function_name: str, arguments: dict):
        """
        Subclasses may override this method to implement custom behavior
        for each tool. Returns the result or intermediate data.
        """
        # Default behavior: No specific tool handling
        return None
