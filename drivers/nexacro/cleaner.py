import re


class NexacroCleaner:
    """Cleans invalid control characters and leading/trailing whitespace from XML payloads."""

    @staticmethod
    def clean_xml(xml_text: str) -> str:
        if not xml_text:
            return "<Root></Root>"
        
        # Remove invalid XML control characters
        cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", xml_text)
        return cleaned.strip()