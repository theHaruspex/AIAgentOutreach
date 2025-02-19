import logging
from typing import List, Optional

from utils.gmail_client.client import GmailClient

logger = logging.getLogger(__name__)


class OutreachTools:
    """
    A minimal wrapper around GmailClient for specific email workflows.
    Now supports:
    - HTML emails by default.
    - Multiple attachments via a list of file paths.
    - Sending OR saving draft depending on class-wide toggle.
    """

    def __init__(self, outreach_label: str = "default_label", send_mode: bool = False):
        """
        Initialize OutreachTools with a predefined label for categorizing outreach emails.

        Args:
            outreach_label (str): The label to assign to outreach emails.
            send_mode (bool): If True, emails are sent immediately instead of saved as drafts.
        """
        self.outreach_label = outreach_label
        self.send_mode = send_mode  # <-- NEW TOGGLE
        self.client = GmailClient()

    # ----------------------------------------------------------------
    #                 Public Methods (Main Workflow)
    # ----------------------------------------------------------------

    def process_email_and_label(
        self,
        to_addrs: List[str],
        subject: str,
        body: str,
        attachment_paths: Optional[List[str]] = None,
    ) -> dict:
        """
        Either saves a draft (HTML by default) or sends an email with optional attachments,
        then labels it for easy retrieval.

        Args:
            to_addrs (List[str]): Recipient email addresses.
            subject (str): Subject of the email.
            body (str): Body of the email (HTML by default).
            attachment_paths (Optional[List[str]]): List of file paths to attach (if any).

        Returns:
            dict: Status message indicating success or failure.
        """
        try:
            if self.send_mode:
                logger.debug("send_mode=True; attempting to send email immediately.")
                success = self._send_email(subject, body, to_addrs, attachment_paths)
                # If sending failed, raise an exception
                if not success:
                    raise Exception("Failed to send email.")

                # Once an email is sent, it's in 'Sent' rather than in 'Drafts'
                message_ids = self._search_messages(f"in:sent subject:{subject}")
                if not message_ids:
                    raise Exception("Failed to locate the sent email for labeling.")
                message_id = message_ids[0]

            else:
                logger.debug("send_mode=False; saving draft email instead.")
                success = self._save_draft(subject, body, to_addrs, attachment_paths)
                if not success:
                    raise Exception("Failed to save draft.")

                # The newly created draft should appear in 'Drafts'
                draft_ids = self._search_messages(f"in:drafts subject:{subject}")
                if not draft_ids:
                    raise Exception("Failed to locate the saved draft for labeling.")
                message_id = draft_ids[0]

            # Now label the message (draft or sent, depending on mode)
            self._add_label(message_id, self.outreach_label)
            logger.debug("Email successfully processed (sent or drafted) and labeled.")

            return {
                "status": (
                    "Email sent and labeled successfully."
                    if self.send_mode
                    else "Draft saved and labeled successfully."
                )
            }
        except Exception as e:
            logger.error(f"Error in process_email_and_label: {e}")
            return {"error": str(e)}

    # ----------------------------------------------------------------
    #                   Private Helper Methods
    # ----------------------------------------------------------------

    def _save_draft(
        self,
        subject: str,
        body: str,
        to_addrs: List[str],
        attachment_paths: Optional[List[str]] = None,
    ) -> bool:
        """
        Saves a draft email (HTML by default) with optional attachments.

        Args:
            subject (str): Email subject.
            body (str): Email body (HTML by default).
            to_addrs (List[str]): Recipient email addresses.
            attachment_paths (Optional[List[str]]): List of attachment file paths.

        Returns:
            bool: True if successful, False otherwise.
        """
        return self.client.save_draft(
            to_addrs=to_addrs,
            subject=subject,
            body=body,
            attachment_paths=attachment_paths
        )

    def _send_email(
        self,
        subject: str,
        body: str,
        to_addrs: List[str],
        attachment_paths: Optional[List[str]] = None,
    ) -> bool:
        """
        Sends an email (HTML by default) with optional attachments.

        Args:
            subject (str): Email subject.
            body (str): Email body (HTML by default).
            to_addrs (List[str]): Recipient email addresses.
            attachment_paths (Optional[List[str]]): List of attachment file paths.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            self.client.send_email(
                to_addrs=to_addrs,
                subject=subject,
                body=body,
                attachment_paths=attachment_paths
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _search_messages(self, criterion: str) -> List[str]:
        """
        Searches messages using a Gmail search criterion.

        Args:
            criterion (str): Gmail search query.

        Returns:
            List[str]: List of message IDs matching the criterion.
        """
        return self.client.search_messages(criterion)

    def _add_label(self, msg_id: str, label: str) -> None:
        """
        Adds a label to a specific message.

        Args:
            msg_id (str): ID of the message.
            label (str): Label name to add.
        """
        self.client.switch_label(
            msg_id=msg_id,
            add_labels=[label]
        )