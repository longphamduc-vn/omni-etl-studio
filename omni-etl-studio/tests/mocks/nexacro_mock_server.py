import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from typing import Dict, Tuple

class NexacroMockHandler(BaseHTTPRequestHandler):
    """Mock HTTP request handler simulating Nexacro XML responses."""

    def _send_xml_response(self, xml_content: str, status_code: int = 200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/xml; charset=UTF-8")
        self.end_headers()
        self.wfile.write(xml_content.encode("utf-8"))

    def _parse_params(self, body_str: str) -> Dict[str, str]:
        """Extracts parameters from Nexacro XML request body."""
        params = {}
        if not body_str.strip():
            return params
        try:
            root = ET.fromstring(body_str)
            for param in root.findall(".//Parameter"):
                p_id = param.get("id")
                if p_id:
                    params[p_id] = param.text or ""
        except Exception:
            pass
        return params

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""
        params = self._parse_params(body)

        if self.path == "/nexacro/students":
            response_xml = """<?xml version="1.0" encoding="UTF-8"?>
            <Root xmlns:ns="http://www.nexacro.com/platform">
                <Parameters>
                    <Parameter id="ErrorCode">0</Parameter>
                    <Parameter id="ErrorMsg">SUCCESS</Parameter>
                </Parameters>
                <Dataset id="ds_students">
                    <ColumnInfo>
                        <Column id="student_id" type="STRING" size="256"/>
                        <Column id="name" type="STRING" size="256"/>
                        <Column id="status" type="STRING" size="256"/>
                    </ColumnInfo>
                    <Rows>
                        <Row>
                            <Col id="student_id">STU_001</Col>
                            <Col id="name">Alice Smith</Col>
                            <Col id="status">ACTIVE</Col>
                        </Row>
                        <Row>
                            <Col id="student_id">STU_002</Col>
                            <Col id="name">Bob Jones</Col>
                            <Col id="status">INACTIVE</Col>
                        </Row>
                        <Row>
                            <Col id="student_id">STU_003</Col>
                            <Col id="name">Charlie Brown</Col>
                            <Col id="status">ACTIVE</Col>
                        </Row>
                    </Rows>
                </Dataset>
            </Root>
            """
            self._send_xml_response(response_xml)

        elif self.path == "/nexacro/scores":
            student_id = params.get("student_id", "STU_001")
            
            # Dynamic response generation based on student_id
            if student_id == "STU_001":
                scores = [("CS101", 95), ("CS102", 88)]
            elif student_id == "STU_003":
                scores = [("CS101", 42), ("CS102", 78)] # Has one failing score (< 50)
            else:
                scores = [("CS101", 60)]

            rows_xml = "".join([
                f"<Row><Col id=\"student_id\">{student_id}</Col><Col id=\"subject_code\">{sub}</Col><Col id=\"score\">{sc}</Col></Row>"
                for sub, sc in scores
            ])

            response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
            <Root>
                <Dataset id="ds_scores">
                    <ColumnInfo>
                        <Column id="student_id" type="STRING" size="256"/>
                        <Column id="subject_code" type="STRING" size="256"/>
                        <Column id="score" type="INT" size="256"/>
                    </ColumnInfo>
                    <Rows>
                        {rows_xml}
                    </Rows>
                </Dataset>
            </Root>
            """
            self._send_xml_response(response_xml)

        elif self.path == "/nexacro/inventory":
            response_xml = """<?xml version="1.0" encoding="UTF-8"?>
            <Root>
                <Dataset id="ds_inventory">
                    <ColumnInfo>
                        <Column id="item_id" type="STRING" size="256"/>
                        <Column id="category" type="STRING" size="256"/>
                        <Column id="quantity" type="INT" size="256"/>
                    </ColumnInfo>
                    <Rows>
                        <Row><Col id="item_id">ITM_01</Col><Col id="category">Electronics</Col><Col id="quantity">10</Col></Row>
                        <Row><Col id="item_id">ITM_02</Col><Col id="category">Electronics</Col><Col id="quantity">15</Col></Row>
                        <Row><Col id="item_id">ITM_03</Col><Col id="category">Furniture</Col><Col id="quantity">5</Col></Row>
                    </Rows>
                </Dataset>
            </Root>
            """
            self._send_xml_response(response_xml)
        else:
            self._send_xml_response("<Root><Error>Endpoint Not Found</Error></Root>", status_code=404)

    def log_message(self, format, *args):
        # Suppress standard HTTP log clutter during test execution
        pass


class MockNexacroServer:
    """Server manager to run NexacroMockHandler in a background thread."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8088):
        self.server_address: Tuple[str, int] = (host, port)
        self.httpd = HTTPServer(self.server_address, NexacroMockHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()