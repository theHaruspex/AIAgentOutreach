import os
import os.path
from typing import List, Dict, Optional

import html

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import base64

import logging

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# SCOPES define the level of access your app is requesting.
# ------------------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.labels",
]


class GmailClient:
    def __init__(self):
        """
        Initializes the GmailClient by loading or acquiring credentials,
        and building a service instance.
        """
        self.creds = self._get_credentials()
        self.service = build("gmail", "v1", credentials=self.creds)

    def _get_credentials(self):
        """
        Acquires OAuth credentials from agents/email_agent/gmail_client/config/token.json (if valid),
        otherwise runs the OAuth flow to generate a new token.json.
        """
        token_path = "utils/gmail_client/config/token.json"
        creds = None

        # Load existing token if it exists
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        # If there are no valid credentials available, request login
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "utils/gmail_client/config/credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())

        return creds

    def list_mailboxes(self) -> List[str]:
        """
        Returns a list of mailbox (label) names in the user's Gmail.
        """
        try:
            response = self.service.users().labels().list(userId="me").execute()
            labels = response.get("labels", [])
            return [label["name"] for label in labels]
        except HttpError as error:
            logger.debug(f"An error occurred while listing labels: {error}")
            return []

    def search_messages(self, search_criterion: str = "ALL", max_results: Optional[int] = None) -> List[str]:
        """
        Searches messages using a Gmail query (e.g., 'label:INBOX from:someone').
        Returns a list of message IDs that match the search criterion.

        Handles Gmail's 100-message pagination limit.

        :param search_criterion: Gmail search query (e.g., 'label:INBOX from:someone').
        :param max_results: Optional limit on the number of message IDs to return.
        :return: List of message IDs matching the search criterion.
        """
        query = "" if search_criterion.upper() == "ALL" else search_criterion
        message_ids = []
        next_page_token = None

        try:
            while True:
                response = self.service.users().messages().list(
                    userId="me",
                    q=query,
                    maxResults=100,  # Gmail max limit per request
                    pageToken=next_page_token
                ).execute()

                messages = response.get("messages", [])
                message_ids.extend([msg["id"] for msg in messages])

                # Stop if we reach the max_results limit
                if max_results and len(message_ids) >= max_results:
                    return message_ids[:max_results]

                # Get the next page token
                next_page_token = response.get("nextPageToken")

                # If there's no more data, break
                if not next_page_token:
                    break

        except HttpError as error:
            logger.debug(f"An error occurred while searching messages: {error}")

        return message_ids
    
    def fetch_message(self, msg_id: str) -> Dict[str, str]:
        """
        Fetches a single message by ID. Returns a dictionary containing
        commonly used fields (subject, from, date, snippet, etc.).
        """
        try:
            message = self.service.users().messages().get(
                userId="me",
                id=msg_id,
                format="metadata",
                metadataHeaders=["Subject", "From", "Date", "To"]
            ).execute()

            headers = message.get("payload", {}).get("headers", [])
            header_map = {h["name"].lower(): h["value"] for h in headers}
            snippet = message.get("snippet", "")

            return {
                "id": msg_id,
                "subject": header_map.get("subject", ""),
                "from": header_map.get("from", ""),
                "date": header_map.get("date", ""),
                "to": header_map.get("to", ""),
                "snippet": snippet,
            }
        except HttpError as error:
            logger.debug(f"An error occurred while fetching message {msg_id}: {error}")
            return {}

    def _remove_labels(self, msg_id: str, labels: List[str]):
        """
        Private method to remove labels from a message.
        """
        try:
            label_ids = [self._get_or_create_label(lbl) for lbl in labels]
            logger.debug(f"Removing labels from message {msg_id}: {labels} -> IDs: {label_ids}")
            self.service.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"removeLabelIds": label_ids}
            ).execute()
            logger.debug(f"Labels {labels} successfully removed from message {msg_id}.")
        except HttpError as error:
            logger.debug(f"An error occurred while removing labels from message {msg_id}: {error}")

    def _add_labels(self, msg_id: str, labels: List[str]):
        """
        Private method to add labels to a message.
        """
        try:
            label_ids = [self._get_or_create_label(lbl) for lbl in labels]
            logger.debug(f"Adding labels to message {msg_id}: {labels} -> IDs: {label_ids}")
            self.service.users().messages().modify(
                userId="me",
                id=msg_id,
                body={"addLabelIds": label_ids}
            ).execute()
            logger.debug(f"Labels {labels} successfully added to message {msg_id}.")
        except HttpError as error:
            logger.debug(f"An error occurred while adding labels to message {msg_id}: {error}")

    def switch_label(
            self,
            msg_id: str,
            remove_labels: Optional[List[str]] = None,
            add_labels: Optional[List[str]] = None,
    ):
        """
        Removes the given `remove_labels` and adds the `add_labels` to every message
        in the thread of the given `msg_id`.
        """
        try:
            # Fetch the thread ID for the given message
            message = self.service.users().messages().get(userId="me", id=msg_id).execute()
            thread_id = message.get("threadId")

            # Fetch all messages in the thread
            thread = self.service.users().threads().get(userId="me", id=thread_id).execute()
            messages = thread.get("messages", [])

            # Apply label changes to each message in the thread
            for msg in messages:
                current_msg_id = msg["id"]
                if remove_labels:
                    self._remove_labels(current_msg_id, remove_labels)
                if add_labels:
                    self._add_labels(current_msg_id, add_labels)

                logger.debug(
                    f"Message {current_msg_id} in thread {thread_id} updated: "
                    f"removed {remove_labels or []}, added {add_labels or []}."
                )

        except HttpError as error:
            logger.debug(f"An error occurred while switching labels on thread: {error}")
        except Exception as error:
            logger.debug(f"An unexpected error occurred: {error}")

    # -------------------------------------------------------------------------
    # Updated helper method: Build MIME message (HTML by default), multiple attachments
    # -------------------------------------------------------------------------
    def _build_mime_message(
        self,
        to_addrs: List[str],
        subject: str,
        body: str,
        from_addr: Optional[str] = None,
        cc_addrs: Optional[List[str]] = None,
        bcc_addrs: Optional[List[str]] = None,
        attachment_paths: Optional[List[str]] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
        is_html: bool = True
    ) -> MIMEMultipart:
        """
        Builds a MIMEMultipart email. Sends HTML by default,
        and can attach multiple files if attachment_paths is provided.
        """
        message = MIMEMultipart()
        message["to"] = ", ".join(to_addrs)
        message["subject"] = subject
        if from_addr:
            message["from"] = from_addr
        if cc_addrs:
            message["cc"] = ", ".join(cc_addrs)
        if bcc_addrs:
            message["bcc"] = ", ".join(bcc_addrs)

        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = references

        # Attach the body as HTML or plaintext
        subtype = "html" if is_html else "plain"
        message.attach(MIMEText(body, subtype))

        # Attach multiple files if provided
        if attachment_paths:
            for attach_path in attachment_paths:
                if attach_path and os.path.exists(attach_path):
                    with open(attach_path, "rb") as f:
                        mime_base = MIMEBase("application", "octet-stream")
                        mime_base.set_payload(f.read())
                    encoders.encode_base64(mime_base)
                    filename = os.path.basename(attach_path)
                    mime_base.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{filename}"'
                    )
                    message.attach(mime_base)

        return message

    def send_email(
            self,
            to_addrs: List[str],
            subject: str,
            body: str,
            from_addr: Optional[str] = None,
            cc_addrs: Optional[List[str]] = None,
            bcc_addrs: Optional[List[str]] = None,
            attachment_paths: Optional[List[str]] = None,
            msg_id: Optional[str] = None  # New parameter for replying to a specific message
    ):
        """
        Sends an email (HTML by default). Supports replying to a specific message if `msg_id` is provided.
        """
        try:
            in_reply_to = None
            references = None
            thread_id = None

            # If replying to an existing message, fetch its headers and thread information
            if msg_id:
                original_message = self.service.users().messages().get(
                    userId="me", id=msg_id
                ).execute()
                thread_id = original_message.get("threadId")
                for header in original_message.get("payload", {}).get("headers", []):
                    if header["name"] == "Message-ID":
                        in_reply_to = header["value"]
                        references = header["value"]

            # Validate attachment paths
            if attachment_paths:
                for path in attachment_paths:
                    if not os.path.isfile(path):
                        raise FileNotFoundError(f"Attachment path is invalid: {path}")

            # Build the MIME message (HTML)
            message = self._build_mime_message(
                to_addrs=to_addrs,
                subject=subject,
                body=body,
                from_addr=from_addr,
                cc_addrs=cc_addrs,
                bcc_addrs=bcc_addrs,
                attachment_paths=attachment_paths,
                in_reply_to=in_reply_to,
                references=references,
                is_html=True
            )

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            send_body = {
                "raw": encoded_message
            }

            # Include thread ID if replying to a specific message
            if thread_id:
                send_body["threadId"] = thread_id

            # Send the email
            self.service.users().messages().send(
                userId="me",
                body=send_body
            ).execute()

            logger.debug("Email sent successfully (HTML).")
        except FileNotFoundError as error:
            logger.error(f"File error: {error}")
            raise  # Re-raise the error to indicate a critical failure
        except HttpError as error:
            logger.debug(f"An error occurred while sending email: {error}")
        except Exception as error:
            logger.debug(f"An unexpected error occurred: {error}")

    def save_draft(
            self,
            to_addrs: List[str],
            subject: str,
            body: str,
            msg_id: Optional[str] = None,  # The ID of the email to reply to
            from_addr: Optional[str] = None,
            cc_addrs: Optional[List[str]] = None,
            bcc_addrs: Optional[List[str]] = None,
            attachment_paths: Optional[List[str]] = None
    ) -> bool:
        """
        Saves an email draft as HTML by default.
        If `msg_id` is provided, attaches the draft to that thread.
        Supports multiple attachments. Validates attachment paths.
        """
        try:
            in_reply_to = None
            references = None
            thread_id = None

            # If replying to an existing message, fetch its headers & thread info
            if msg_id:
                original_message = self.service.users().messages().get(
                    userId="me", id=msg_id
                ).execute()
                thread_id = original_message.get("threadId")
                for header in original_message.get("payload", {}).get("headers", []):
                    if header["name"] == "Message-ID":
                        in_reply_to = header["value"]
                        references = header["value"]
                    elif header["name"] == "Subject":
                        # Optionally keep or modify the subject here
                        pass

            # Validate attachment paths
            if attachment_paths:
                for path in attachment_paths:
                    if not os.path.isfile(path):
                        raise FileNotFoundError(f"Attachment path is invalid: {path}")

            # Build the MIME message (HTML)
            message = self._build_mime_message(
                to_addrs=to_addrs,
                subject=subject,
                body=body,
                from_addr=from_addr,
                cc_addrs=cc_addrs,
                bcc_addrs=bcc_addrs,
                attachment_paths=attachment_paths,
                in_reply_to=in_reply_to,
                references=references,
                is_html=True
            )

            encoded_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode("utf-8")

            draft_body = {
                "message": {
                    "threadId": thread_id,
                    "raw": encoded_message
                }
            }

            self.service.users().drafts().create(
                userId="me",
                body=draft_body
            ).execute()

            logger.debug("Draft saved successfully (HTML).")
            return True
        except FileNotFoundError as error:
            logger.error(f"File error: {error}")
            raise  # Re-raise the error to indicate a critical failure
        except HttpError as error:
            logger.debug(f"An error occurred while saving draft: {error}")
            return False
        except Exception as error:
            logger.debug(f"An unexpected error occurred: {error}")
            return False

    def fetch_thread(self, root_msg_id: str) -> List[Dict[str, str]]:
        """
        Fetches a thread given the root message ID. Returns a list of messages
        (dict) with minimal fields: subject, from, date, snippet, etc.
        """
        try:
            msg = self.service.users().messages().get(userId="me", id=root_msg_id).execute()
            thread_id = msg.get("threadId")

            thread = self.service.users().threads().get(userId="me", id=thread_id).execute()
            messages = thread.get("messages", [])

            results = []
            for m in messages:
                headers = m.get("payload", {}).get("headers", [])
                header_map = {h["name"].lower(): h["value"] for h in headers}
                snippet = m.get("snippet", "")

                snippet_trimmed = html.unescape(self._trim_snippet(snippet))

                results.append({
                    "id": m["id"],
                    "threadId": thread_id,
                    "subject": header_map.get("subject", ""),
                    "from": header_map.get("from", ""),
                    "date": header_map.get("date", ""),
                    "to": header_map.get("to", ""),
                    "snippet": snippet_trimmed,
                })

            return results
        except HttpError as error:
            logger.debug(f"An error occurred while fetching thread for message {root_msg_id}: {error}")
            return []

    def _trim_snippet(self, snippet: str) -> str:
        """
        Naïvely removes reply/forward quoted text from the snippet
        by looking for certain markers like 'On ', ' wrote:', etc.
        """
        possible_markers = [
            "On ",
            "wrote:",
            "From:",
            "Subject:"
        ]

        lower_snippet = snippet.lower()
        cut_positions = []

        for marker in possible_markers:
            idx = lower_snippet.find(marker.lower())
            if idx != -1:
                cut_positions.append(idx)

        if not cut_positions:
            return snippet

        cutoff = min(cut_positions)
        trimmed = snippet[:cutoff].rstrip()

        return trimmed if trimmed else snippet

    def _get_or_create_label(self, label_name: str) -> str:
        """
        Returns the label ID for `label_name`. If it doesn't exist,
        creates it and returns the new label ID.
        """
        response = self.service.users().labels().list(userId="me").execute()
        labels = response.get("labels", [])
        for lbl in labels:
            if lbl["name"].lower() == label_name.lower():
                return lbl["id"]

        label_body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show"
        }
        new_label = self.service.users().labels().create(
            userId="me",
            body=label_body
        ).execute()

        return new_label["id"]

    def format_thread(self, thread: List[Dict[str, str]]) -> str:
        """
        Formats a list of messages in a thread into a human-readable string.
        """
        formatted_thread = []
        for i, message in enumerate(thread):
            formatted_thread.append(
                f"Message {i + 1}:\n"
                f"  From: {message['from']}\n"
                f"  Date: {message['date']}\n"
                f"  Subject: {message['subject']}\n"
                f"  Body: {message['snippet']}\n"
                f"{'-' * 40}\n"
            )
        return "\n".join(formatted_thread)

    def get_labels(self, msg_id: str) -> List[str]:
        """
        Returns the labels attached to a specific message.
        """
        try:
            message = self.service.users().messages().get(
                userId="me",
                id=msg_id,
                format="metadata"
            ).execute()
            return message.get("labelIds", [])
        except HttpError as error:
            logger.debug(f"An error occurred while fetching labels for message {msg_id}: {error}")
            return []