import re
from core.common.exceptions import DriverError
from core.common.logger import log


class NexacroCleaner:
    """Sanitizes Nexacro XML responses by stripping namespaces and unwanted XML attributes."""

    @staticmethod
    def clean_xml(xml_text: str) -> str:
        if not xml_text or not xml_text.strip():
            raise DriverError("Empty or null XML response received from Nexacro endpoint.")

        try:
            # 1. Remove XML Declarations if duplicated or malformed
            cleaned = re.sub(r'<\?xml[^>]*\?>', '', xml_text)

            # 2. Strip xmlns and xmlns:* namespace attributes from all XML tags
            cleaned = re.sub(r'\s+xmlns(?::\w+)?="[^"]*"', '', cleaned)

            # 3. Strip namespace prefixes from tag names (e.g., <ns2:Dataset> -> <Dataset>)
            cleaned = re.sub(r'</?\w+:', '<', cleaned)
            cleaned = re.sub(r'</\w+:', '</', cleaned)

            return cleaned.strip()

        except Exception as e:
            raise DriverError(f"Failed to clean Nexacro XML payload: {str(e)}")