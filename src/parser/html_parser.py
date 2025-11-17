"""HTML parser for KAD case cards."""

import re
from datetime import datetime
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag

from src.core.exceptions import HTMLParseException
from src.core.logging import get_logger
from src.storage.database.models import CaseType, DocumentType, ParticipantRole

logger = get_logger(__name__)


class HTMLCaseParser:
    """Parser for KAD case card HTML."""

    def __init__(self, html: str) -> None:
        """Initialize parser with HTML content.

        Args:
            html: HTML content of case card
        """
        self.html = html
        try:
            self.soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            raise HTMLParseException(f"Failed to parse HTML: {e}") from e

    def parse_case_info(self) -> dict[str, Any]:
        """Parse basic case information.

        Returns:
            Dictionary with case information

        Raises:
            HTMLParseException: If parsing fails
        """
        try:
            case_info: dict[str, Any] = {}

            # Parse case number
            case_number_elem = self.soup.find("div", class_="case-number")
            if case_number_elem:
                case_info["case_number"] = case_number_elem.get_text(strip=True)

            # Parse court name
            court_elem = self.soup.find("div", class_="court-name")
            if court_elem:
                case_info["court_name"] = court_elem.get_text(strip=True)

            # Parse judge
            judge_elem = self.soup.find("div", class_="judge")
            if judge_elem:
                case_info["judge_name"] = judge_elem.get_text(strip=True)

            # Parse case type from case number
            if "case_number" in case_info:
                case_info["case_type"] = self._extract_case_type(case_info["case_number"])

            # Parse filing date
            date_elem = self.soup.find("div", class_="filing-date")
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                case_info["filing_date"] = self._parse_date(date_text)

            # Parse category
            category_elem = self.soup.find("div", class_="case-category")
            if category_elem:
                case_info["category"] = category_elem.get_text(strip=True)

            # Parse subject
            subject_elem = self.soup.find("div", class_="case-subject")
            if subject_elem:
                case_info["subject"] = subject_elem.get_text(strip=True)

            logger.debug("parsed_case_info", case_info=case_info)
            return case_info

        except Exception as e:
            logger.error("case_info_parse_error", error=str(e))
            raise HTMLParseException(f"Failed to parse case info: {e}") from e

    def parse_participants(self) -> list[dict[str, Any]]:
        """Parse case participants.

        Returns:
            List of participant dictionaries

        Raises:
            HTMLParseException: If parsing fails
        """
        try:
            participants = []

            # Find participants section
            participants_section = self.soup.find("div", class_="participants")
            if not participants_section:
                return participants

            # Parse each participant type
            for role_section in participants_section.find_all("div", class_="participant-role"):
                role_name = role_section.find("h3")
                if not role_name:
                    continue

                role = self._map_participant_role(role_name.get_text(strip=True))

                # Find all participants for this role
                for participant_elem in role_section.find_all("div", class_="participant"):
                    name_elem = participant_elem.find("span", class_="name")
                    if not name_elem:
                        continue

                    participant = {
                        "name": name_elem.get_text(strip=True),
                        "role": role,
                    }

                    # Try to extract INN
                    inn_elem = participant_elem.find("span", class_="inn")
                    if inn_elem:
                        inn_text = inn_elem.get_text(strip=True)
                        inn_match = re.search(r"\d{10,12}", inn_text)
                        if inn_match:
                            participant["inn"] = inn_match.group()

                    # Extract address
                    address_elem = participant_elem.find("span", class_="address")
                    if address_elem:
                        participant["address"] = address_elem.get_text(strip=True)

                    participants.append(participant)

            logger.debug("parsed_participants", count=len(participants))
            return participants

        except Exception as e:
            logger.error("participants_parse_error", error=str(e))
            raise HTMLParseException(f"Failed to parse participants: {e}") from e

    def parse_documents(self) -> list[dict[str, Any]]:
        """Parse case documents.

        Returns:
            List of document dictionaries

        Raises:
            HTMLParseException: If parsing fails
        """
        try:
            documents = []

            docs_section = self.soup.find("div", class_="documents")
            if not docs_section:
                return documents

            for doc_elem in docs_section.find_all("div", class_="document"):
                document: dict[str, Any] = {}

                # Parse document title
                title_elem = doc_elem.find("a", class_="document-link")
                if title_elem:
                    document["title"] = title_elem.get_text(strip=True)
                    document["file_url"] = title_elem.get("href")

                # Parse document type
                type_elem = doc_elem.find("span", class_="doc-type")
                if type_elem:
                    document["doc_type"] = self._map_document_type(
                        type_elem.get_text(strip=True)
                    )

                # Parse document date
                date_elem = doc_elem.find("span", class_="doc-date")
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    document["doc_date"] = self._parse_date(date_text)

                # Parse document number
                number_elem = doc_elem.find("span", class_="doc-number")
                if number_elem:
                    document["doc_number"] = number_elem.get_text(strip=True)

                if document:
                    documents.append(document)

            logger.debug("parsed_documents", count=len(documents))
            return documents

        except Exception as e:
            logger.error("documents_parse_error", error=str(e))
            raise HTMLParseException(f"Failed to parse documents: {e}") from e

    def parse_hearings(self) -> list[dict[str, Any]]:
        """Parse court hearings.

        Returns:
            List of hearing dictionaries

        Raises:
            HTMLParseException: If parsing fails
        """
        try:
            hearings = []

            hearings_section = self.soup.find("div", class_="hearings")
            if not hearings_section:
                return hearings

            for hearing_elem in hearings_section.find_all("div", class_="hearing"):
                hearing: dict[str, Any] = {}

                # Parse hearing date
                date_elem = hearing_elem.find("span", class_="hearing-date")
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    hearing["hearing_date"] = self._parse_datetime(date_text)

                # Parse hearing type
                type_elem = hearing_elem.find("span", class_="hearing-type")
                if type_elem:
                    hearing["hearing_type"] = type_elem.get_text(strip=True)

                # Parse result
                result_elem = hearing_elem.find("span", class_="hearing-result")
                if result_elem:
                    hearing["result"] = result_elem.get_text(strip=True)

                if hearing:
                    hearings.append(hearing)

            logger.debug("parsed_hearings", count=len(hearings))
            return hearings

        except Exception as e:
            logger.error("hearings_parse_error", error=str(e))
            raise HTMLParseException(f"Failed to parse hearings: {e}") from e

    def _extract_case_type(self, case_number: str) -> Optional[str]:
        """Extract case type from case number.

        Args:
            case_number: Case number (e.g., А40-123456/2024)

        Returns:
            Case type or None
        """
        if case_number.startswith("А"):
            return CaseType.ADMINISTRATIVE.value
        elif case_number.startswith("Г"):
            return CaseType.CIVIL.value
        elif case_number.startswith("Б"):
            return CaseType.BANKRUPTCY.value
        return None

    def _map_participant_role(self, role_text: str) -> str:
        """Map Russian role text to ParticipantRole enum.

        Args:
            role_text: Role text in Russian

        Returns:
            ParticipantRole value
        """
        role_lower = role_text.lower()
        if "истец" in role_lower or "заявител" in role_lower:
            return ParticipantRole.PLAINTIFF.value
        elif "ответчик" in role_lower:
            return ParticipantRole.DEFENDANT.value
        elif "третье лицо" in role_lower or "3-е лицо" in role_lower:
            return ParticipantRole.THIRD_PARTY.value
        return ParticipantRole.OTHER.value

    def _map_document_type(self, doc_type_text: str) -> str:
        """Map Russian document type to DocumentType enum.

        Args:
            doc_type_text: Document type text in Russian

        Returns:
            DocumentType value
        """
        doc_type_lower = doc_type_text.lower()
        if "решение" in doc_type_lower:
            return DocumentType.DECISION.value
        elif "определение" in doc_type_lower:
            return DocumentType.RULING.value
        elif "протокол" in doc_type_lower:
            return DocumentType.PROTOCOL.value
        elif "заявление" in doc_type_lower:
            return DocumentType.PETITION.value
        elif "жалоба" in doc_type_lower:
            return DocumentType.COMPLAINT.value
        return DocumentType.OTHER.value

    def _parse_date(self, date_text: str) -> Optional[str]:
        """Parse date string to ISO format.

        Args:
            date_text: Date string (various formats)

        Returns:
            ISO format date string or None
        """
        try:
            # Try common formats
            for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]:
                try:
                    dt = datetime.strptime(date_text.strip(), fmt)
                    return dt.date().isoformat()
                except ValueError:
                    continue
            return None
        except Exception:
            return None

    def _parse_datetime(self, datetime_text: str) -> Optional[str]:
        """Parse datetime string to ISO format.

        Args:
            datetime_text: Datetime string

        Returns:
            ISO format datetime string or None
        """
        try:
            # Try common formats
            for fmt in ["%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M"]:
                try:
                    dt = datetime.strptime(datetime_text.strip(), fmt)
                    return dt.isoformat()
                except ValueError:
                    continue
            return None
        except Exception:
            return None
