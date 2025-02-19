import json
import os
from typing import Optional

from ndt_logger import initialize_logging

from agents.outreach_agent.outreach_agent import OutreachAgent
from agents.outreach_agent.outreach_prompt import AGENT_PROMPT

class EmailOutreachProcessor:
    """
    Processes a specific slice of recipients: [begin_index, end_index), with each recipient
    stored as a separate file in `dormant_customers_db`.
    """

    def __init__(
        self,
        recipients_dir: str,             # <-- Now points to a directory, not a single JSON
        begin_index: int,
        end_index: int,
        stop_time: Optional[int] = None,
        outreach_label: str = "default_label",
        send_mode: bool = False,
        log_filename: str = "dormant_sales.log"
    ):
        """
        Parameters:
        - recipients_dir (str): Path to the directory containing individual recipient JSON files.
        - begin_index (int): Start index (inclusive).
        - end_index (int): End index (exclusive).
        - stop_time (int): (Optional) Hour after which processing stops (e.g. 10 -> 10 AM).
        - outreach_label (str): Label for emails processed.
        - send_mode (bool): If True, mark 'email_sent' as True after "sending".
        - log_filename (str): Unique log file name for this thread.
        """
        self.logger = initialize_logging(
            log_dir='logs',
            log_file=log_filename
        )

        # Treat this as the "database" directory
        self.recipients_dir = recipients_dir
        self.begin_index = begin_index
        self.end_index = end_index  # EXCLUSIVE
        self.stop_time = stop_time
        self.outreach_label = outreach_label
        self.send_mode = send_mode
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")

    def process_slice(self, prompt: str) -> None:
        """
        Process recipients in [self.begin_index, self.end_index).
        Reads and writes each recipient file independently, so no global file locking is necessary.
        """
        self.logger.info("\n" + "-" * 50 + "\n")

        for i in range(self.begin_index, self.end_index):
            # Construct the file path for this recipient
            recipient_file = os.path.join(self.recipients_dir, f"customer_{i}.json")

            # If the file doesn't exist, we skip
            if not os.path.isfile(recipient_file):
                self.logger.info(f"No file found for index {i} at {recipient_file}. Skipping.")
                continue

            # Load the recipient data
            try:
                with open(recipient_file, 'r') as f:
                    recipient = json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load recipient at index {i}: {e}")
                continue

            # Check if this recipient is already sent
            if recipient.get("email_sent"):
                self.logger.info(f"Index {i}: Already marked 'email_sent=True'. Skipping.")
                continue

            # Process
            try:
                name = recipient.get("source_name", "UNKNOWN")
                email = recipient.get("email", "UNKNOWN")
                self.logger.info(f"Processing index {i}: {name} <{email}>")

                # Construct the personalized prompt
                personalized_prompt = prompt.replace("{Insert JSON Here}", str(recipient))

                # Invoke your email-sending (or generation) agent
                agent = OutreachAgent(
                    api_key=self.openai_api_key,
                    model_name="gpt-4o-mini",
                    outreach_label=self.outreach_label,
                    send_mode=self.send_mode
                )

                final_response = agent.process_user_input(personalized_prompt)
                self.logger.info(f"Email to {email}:\n{final_response}")
                self.logger.info(f"Email successfully processed for: {name}")

                # If send_mode is True, mark the recipient as having an email sent
                if self.send_mode:
                    recipient["email_sent"] = True
                    try:
                        with open(recipient_file, 'w') as f:
                            json.dump(recipient, f, indent=4)
                        self.logger.info(f"Updated 'email_sent' for index {i}.")
                    except Exception as e:
                        self.logger.error(f"Failed to save recipient {i} updates: {e}")

            except Exception as e:
                self.logger.error(f"Error processing recipient at index {i}: {e}")

        self.logger.info("-" * 50 + "\n")

    def run(self, prompt: str) -> None:
        """
        Orchestrate the entire outreach for this slice, from begin_index to end_index.
        """
        self.logger.info(f"Starting email outreach. Slice: [{self.begin_index}, {self.end_index})")

        # (Optional) You could enforce stop_time checks here if desired.

        self.process_slice(prompt)

        self.logger.info("Email outreach process completed.")


def run_processor(
    name: str,
    recipients_dir: str,
    begin_index: int,
    end_index: int,
    stop_time: int,
    outreach_label: str,
    send_mode: bool,
    log_file_prefix: str
):
    """
    This function is the 'target' for each thread. It creates and runs an
    EmailOutreachProcessor with the given arguments.
    """
    print(f"[{name}] Thread starting...")

    # Create a unique log filename for this thread
    log_filename = f"{log_file_prefix}_{name}.log"

    processor = EmailOutreachProcessor(
        recipients_dir=recipients_dir,
        begin_index=begin_index,
        end_index=end_index,
        stop_time=stop_time,
        outreach_label=outreach_label,
        send_mode=send_mode,
        log_filename=log_filename  # Pass unique log filename for this thread
    )

    # Run the outreach process with a shared prompt
    processor.run(AGENT_PROMPT)

    print(f"[{name}] Thread finished.")

