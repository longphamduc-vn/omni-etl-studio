=== FILE: ./config/settings.py ===
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """System-wide configuration settings loaded from environment variables or .env file."""

    # Project Information
    PROJECT_NAME: str = Field(default="omni-etl-studio", validation_alias="PROJECT_NAME")
    APP_ENV: str = Field(default="development", validation_alias="APP_ENV")
    DEBUG: bool = Field(default=True, validation_alias="DEBUG")

    # DuckDB Storage Settings
    DUCKDB_PATH: str = Field(default=":memory:", validation_alias="DUCKDB_PATH")

    # HTTP & Driver Timeouts
    DEFAULT_HTTP_TIMEOUT: int = Field(default=30, validation_alias="DEFAULT_HTTP_TIMEOUT")
    MAX_RETRIES: int = Field(default=3, validation_alias="MAX_RETRIES")

    # Directories
    WORKFLOWS_DIR: Path = BASE_DIR / "workflows"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Pydantic V2 Configuration for .env file
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()


=== FILE: ./config/__init__.py ===



=== FILE: ./tests/integration/test_pipeline_e2e.py ===
import pytest
import pandas as pd
from pathlib import Path

from config.settings import settings
from core.registry.workflow_registry import WorkflowRegistry
from core.engine.runner import PipelineRunner
from tests.mocks.nexacro_mock_server import MockNexacroServer


@pytest.fixture(scope="module")
def mock_server():
    """Starts the background HTTP Nexacro mock server for E2E integration tests."""
    server = MockNexacroServer(host="127.0.0.1", port=8088)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def workflow_registry():
    """Provides a WorkflowRegistry instance pointing to the workflows/ directory."""
    return WorkflowRegistry()


def test_academic_student_score_chained_e2e(mock_server, workflow_registry):
    """End-to-End Integration Test for 'academic_student_score_chained' workflow:
    1. Step 1 (batch): Fetches students -> filters for status=='ACTIVE' (excludes Bob Jones).
    2. Step 2 (chained_loop): Iterates over active students (STU_001, STU_003) ->
       fetches scores -> filters out score < 50 (excludes score 42 for STU_003) ->
       applies DuckDB deduplication.
    """
    # 1. Fetch workflow config
    workflow_config = workflow_registry.get_workflow("academic_student_score_chained")
    
    # 2. Instantiate and run pipeline
    runner = PipelineRunner(workflow=workflow_config, pipeline_id="e2e_test_academic")
    global_input = {"dept_code": "CS"}
    
    context = runner.run(global_input=global_input)

    try:
        # 3. Verify Step 1 Output Dataset ('active_students')
        step1_df = context.get_dataframe("active_students")
        assert not step1_df.empty
        assert len(step1_df) == 2  # STU_001 (Alice) and STU_003 (Charlie), STU_002 filtered out
        assert set(step1_df["student_id"]) == {"STU_001", "STU_003"}
        assert "INACTIVE" not in step1_df["status"].values

        # 4. Verify Step 2 Output Dataset ('passed_student_scores')
        step2_df = context.get_dataframe("passed_student_scores")
        assert not step2_df.empty
        
        # Expected scores after filter (score >= 50):
        # STU_001: CS101 (95), CS102 (88)
        # STU_003: CS102 (78)  [CS101 (42) filtered out]
        assert len(step2_df) == 3
        
        # Ensure all scores in dataset are >= 50
        assert (step2_df["score"].astype(int) >= 50).all()
        
        # Ensure STU_003 only has CS102 subject present
        stu003_subjects = step2_df[step2_df["student_id"] == "STU_003"]["subject_code"].tolist()
        assert stu003_subjects == ["CS102"]

    finally:
        # Cleanup isolated DuckDB schema namespace
        context.close()


def test_inventory_batch_sync_e2e(mock_server, workflow_registry):
    """End-to-End Integration Test for 'inventory_batch_sync' workflow:
    1. Step 1 (batch): Fetches inventory dataset -> applies DuckDB 'group_by' operator 
       summing quantities by category.
    """
    workflow_config = workflow_registry.get_workflow("inventory_batch_sync")
    
    runner = PipelineRunner(workflow=workflow_config, pipeline_id="e2e_test_inventory")
    global_input = {"warehouse_id": "WH-01"}
    
    context = runner.run(global_input=global_input)

    try:
        summary_df = context.get_dataframe("category_inventory_summary")
        assert not summary_df.empty
        assert len(summary_df) == 2  # Electronics, Furniture

        # Verify SQL aggregation math:
        # Electronics: ITM_01 (10) + ITM_02 (15) = 25
        # Furniture: ITM_03 (5) = 5
        electronics_qty = summary_df[summary_df["category"] == "Electronics"]["quantity_sum"].iloc[0]
        furniture_qty = summary_df[summary_df["category"] == "Furniture"]["quantity_sum"].iloc[0]

        assert float(electronics_qty) == 25.0
        assert float(furniture_qty) == 5.0

    finally:
        context.close()


=== FILE: ./tests/mocks/nexacro_mock_server.py ===
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


=== FILE: ./tests/unit/test_nexacro_xml_json.py ===
import pytest
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
import pandas as pd

from drivers.nexacro.builder import NexacroBuilder
from drivers.nexacro.cleaner import NexacroCleaner
from drivers.nexacro.parser import NexacroParser


class NexacroXmlJsonConverter:
    """Helper chuyển đổi hai chiều giữa Nexacro XML và JSON/Dict chuẩn."""

    @staticmethod
    def nexacro_xml_to_json(xml_str: str, dataset_id: str = None) -> Dict[str, Any]:
        """Chuyển đổi Nexacro XML -> JSON Dict chuẩn."""
        cleaned_xml = NexacroCleaner.clean_xml(xml_str)
        root = ET.fromstring(cleaned_xml)

        # 1. Parse Parameters
        parameters = {}
        for param in root.findall(".//Parameter"):
            p_id = param.get("id")
            if p_id:
                parameters[p_id] = param.text or ""

        # 2. Parse Datasets sang Pandas DF -> JSON Records
        df = NexacroParser.parse_xml_to_dataframe(cleaned_xml, dataset_id=dataset_id)
        records = df.to_dict(orient="records")

        return {
            "parameters": parameters,
            "data": records
        }

    @staticmethod
    def json_to_nexacro_xml(json_data: Dict[str, Any], dataset_id: str = "ds_output") -> str:
        """Chuyển đổi JSON Dict chuẩn -> Nexacro XML."""
        parameters = json_data.get("parameters", {})
        data_records = json_data.get("data", [])

        payload_df = pd.DataFrame(data_records) if data_records else None
        return NexacroBuilder.build_xml_payload(
            variables=parameters,
            payload_df=payload_df,
            dataset_id=dataset_id
        )


# ==============================================================================
# UNIT TESTS
# ==============================================================================

def test_nexacro_xml_to_json_conversion():
    """Test chuyển đổi từ Nexacro XML thô sang JSON Dict cấu trúc sạch."""
    nexacro_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <Root xmlns:ns="http://www.nexacro.com/platform">
        <Parameters>
            <Parameter id="ErrorCode">0</Parameter>
            <Parameter id="ErrorMsg">SUCCESS</Parameter>
        </Parameters>
        <Dataset id="ds_students">
            <ColumnInfo>
                <Column id="student_id" type="STRING" size="256"/>
                <Column id="name" type="STRING" size="256"/>
                <Column id="score" type="INT" size="256"/>
            </ColumnInfo>
            <Rows>
                <Row>
                    <Col id="student_id">STU_001</Col>
                    <Col id="name">Alice</Col>
                    <Col id="score">95</Col>
                </Row>
                <Row>
                    <Col id="student_id">STU_002</Col>
                    <Col id="name">Bob</Col>
                    <Col id="score">88</Col>
                </Row>
            </Rows>
        </Dataset>
    </Root>
    """

    json_result = NexacroXmlJsonConverter.nexacro_xml_to_json(nexacro_xml, dataset_id="ds_students")

    # Kiểm tra Parameters
    assert json_result["parameters"]["ErrorCode"] == "0"
    assert json_result["parameters"]["ErrorMsg"] == "SUCCESS"

    # Kiểm tra Data Rows
    assert len(json_result["data"]) == 2
    assert json_result["data"][0]["student_id"] == "STU_001"
    assert json_result["data"][0]["name"] == "Alice"
    assert json_result["data"][1]["score"] == "88"


def test_json_to_nexacro_xml_conversion():
    """Test chuyển đổi từ JSON Dict sạch sang Nexacro XML chuẩn giao thức."""
    json_input = {
        "parameters": {
            "dept_code": "CS",
            "academic_year": "2026"
        },
        "data": [
            {"item_id": "ITM_01", "category": "Electronics", "quantity": 10},
            {"item_id": "ITM_02", "category": "Furniture", "quantity": 5}
        ]
    }

    xml_output = NexacroXmlJsonConverter.json_to_nexacro_xml(json_input, dataset_id="ds_inventory")

    # Verify XML được sinh ra có cấu trúc Nexacro chuẩn
    root = ET.fromstring(xml_output)
    assert root.tag == "Root"

    # Verify Parameters
    params = {p.get("id"): p.text for p in root.findall(".//Parameter")}
    assert params["dept_code"] == "CS"
    assert params["academic_year"] == "2026"

    # Verify Dataset & Columns & Rows
    ds = root.find(".//Dataset")
    assert ds.get("id") == "ds_inventory"

    cols = [c.get("id") for c in ds.findall("./ColumnInfo/Column")]
    assert set(cols) == {"item_id", "category", "quantity"}

    rows = ds.findall("./Rows/Row")
    assert len(rows) == 2


def test_nexacro_roundtrip_xml_json_xml():
    """Test Roundtrip: JSON -> Nexacro XML -> JSON (Đảm bảo dữ liệu không bị biến dạng)."""
    original_json = {
        "parameters": {"Status": "OK"},
        "data": [
            {"emp_id": "E101", "salary": "5000"},
            {"emp_id": "E102", "salary": "6000"}
        ]
    }

    # Step 1: Convert JSON -> Nexacro XML
    xml_str = NexacroXmlJsonConverter.json_to_nexacro_xml(original_json, dataset_id="ds_emp")

    # Step 2: Convert Nexacro XML -> JSON
    reconstructed_json = NexacroXmlJsonConverter.nexacro_xml_to_json(xml_str, dataset_id="ds_emp")

    # Verify tính toàn vẹn
    assert reconstructed_json["parameters"] == original_json["parameters"]
    assert len(reconstructed_json["data"]) == len(original_json["data"])
    assert reconstructed_json["data"][0]["emp_id"] == "E101"


=== FILE: ./tests/unit/test_context.py ===
import pytest
import pandas as pd
from core.storage.context import PipelineContext
from core.common.exceptions import StorageError


@pytest.fixture
def test_context():
    """Fixture initializing and cleaning up PipelineContext for unit tests."""
    ctx = PipelineContext(pipeline_id="unit_test_context")
    yield ctx
    ctx.close()


def test_pipeline_context_init_and_isolation():
    ctx1 = PipelineContext(pipeline_id="pipe-001")
    ctx2 = PipelineContext(pipeline_id="pipe-002", db_connection=ctx1.conn)

    assert ctx1.schema_name == "ns_pipe_001"
    assert ctx2.schema_name == "ns_pipe_002"

    df1 = pd.DataFrame([{"id": 1, "val": "Alpha"}])
    df2 = pd.DataFrame([{"id": 2, "val": "Beta"}])

    ctx1.save_dataframe("test_tbl", df1)
    ctx2.save_dataframe("test_tbl", df2)

    res1 = ctx1.get_dataframe("test_tbl")
    res2 = ctx2.get_dataframe("test_tbl")

    assert res1.iloc[0]["val"] == "Alpha"
    assert res2.iloc[0]["val"] == "Beta"

    ctx1.close()
    ctx2.close()


def test_execute_sql_and_invalid_table(test_context):
    df = pd.DataFrame([{"amount": 100}, {"amount": 200}])
    test_context.save_dataframe("data", df)

    res_df = test_context.execute_sql(f"SELECT SUM(amount) as total FROM {test_context.schema_name}.data")
    assert res_df.iloc[0]["total"] == 300

    with pytest.raises(StorageError):
        test_context.get_dataframe("non_existent_table")


=== FILE: ./tests/unit/test_nexacro_driver.py ===
import pytest
import pandas as pd
from drivers.nexacro.builder import NexacroBuilder
from drivers.nexacro.cleaner import NexacroCleaner
from drivers.nexacro.parser import NexacroParser
from core.common.exceptions import DriverError

def test_nexacro_builder():
    variables = {"param1": "value1", "param2": 100}
    payload_df = pd.DataFrame([{"col1": "A", "col2": 1}])

    xml_output = NexacroBuilder.build_xml_payload(variables, payload_df, dataset_id="ds_input")

    assert "<Parameter id=\"param1\">value1</Parameter>" in xml_output
    assert "<Dataset id=\"ds_input\">" in xml_output
    assert "<Col id=\"col1\">A</Col>" in xml_output

def test_nexacro_cleaner_strip_namespaces():
    raw_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <Root xmlns:ns="http://www.nexacro.com">
        <ns:Dataset id="ds_data">
            <Rows><Row><Col id="id">101</Col></Row></Rows>
        </ns:Dataset>
    </Root>"""

    cleaned_xml = NexacroCleaner.clean_xml(raw_xml)

    assert "xmlns:ns" not in cleaned_xml
    assert "<Dataset id=\"ds_data\">" in cleaned_xml

def test_nexacro_cleaner_empty_input():
    with pytest.raises(DriverError):
        NexacroCleaner.clean_xml("")

def test_nexacro_parser():
    cleaned_xml = """<Root>
        <Dataset id="ds_result">
            <ColumnInfo>
                <Column id="code" type="STRING"/>
                <Column id="val" type="INT"/>
            </ColumnInfo>
            <Rows>
                <Row><Col id="code">X</Col><Col id="val">50</Col></Row>
                <Row><Col id="code">Y</Col><Col id="val">60</Col></Row>
            </Rows>
        </Dataset>
    </Root>"""

    df = NexacroParser.parse_xml_to_dataframe(cleaned_xml, dataset_id="ds_result")

    assert len(df) == 2
    assert list(df.columns) == ["code", "val"]
    assert df.iloc[0]["code"] == "X"


=== FILE: ./tests/unit/test_operators.py ===
import pytest
import pandas as pd
from core.storage.context import PipelineContext
from core.engine.transformer import DataTransformer
from core.common.schemas import TransformRule

@pytest.fixture
def test_context():
    ctx = PipelineContext(pipeline_id="test_suite")
    yield ctx
    ctx.close()

def test_duckdb_deduplicate_operator(test_context):
    df = pd.DataFrame([
        {"user_id": "A", "score": 100},
        {"user_id": "A", "score": 100},
        {"user_id": "B", "score": 90},
    ])
    test_context.save_dataframe("raw_data", df)

    rules = [
        TransformRule(operator="deduplicate", params={"subset": ["user_id"]})
    ]

    res_table = DataTransformer.transform("raw_data", rules, test_context)
    res_df = test_context.get_dataframe(res_table)

    assert len(res_df) == 2
    assert set(res_df["user_id"]) == {"A", "B"}

def test_duckdb_group_by_operator(test_context):
    df = pd.DataFrame([
        {"dept": "IT", "salary": 1000},
        {"dept": "IT", "salary": 2000},
        {"dept": "HR", "salary": 1500},
    ])
    test_context.save_dataframe("salaries", df)

    rules = [
        TransformRule(
            operator="group_by",
            params={"by": ["dept"], "agg": {"salary": "AVG"}}
        )
    ]

    res_table = DataTransformer.transform("salaries", rules, test_context)
    res_df = test_context.get_dataframe(res_table)

    assert len(res_df) == 2
    it_avg = res_df[res_df["dept"] == "IT"]["salary_avg"].iloc[0]
    assert it_avg == 1500.0


=== FILE: ./tests/unit/test_evaluator.py ===



=== FILE: ./tests/unit/test_transformer.py ===



=== FILE: ./tests/unit/test_duckdb_operators_extended.py ===
import pytest
import pandas as pd
import numpy as np

from core.storage.context import PipelineContext
from core.engine.transformer import DataTransformer
from core.engine.filter import FilterEngine
from core.common.schemas import TransformRule, FilterCondition


@pytest.fixture
def test_context():
    """Tạo isolated DuckDB context cho từng bài unit test và dọn dẹp sau khi chạy."""
    ctx = PipelineContext(pipeline_id="unit_test_operators")
    yield ctx
    ctx.close()


# ==============================================================================
# 1. UNIT TESTS CHO TOÁN TỬ: handle_nulls
# ==============================================================================

def test_handle_nulls_drop_all_columns(test_context):
    """Test handle_nulls dạng 'drop': loại bỏ tất cả các dòng chứa bất kỳ giá trị NULL nào."""
    df = pd.DataFrame([
        {"id": 1, "name": "Alice", "email": "alice@test.com"},
        {"id": 2, "name": "Bob", "email": None},
        {"id": 3, "name": None, "email": "charlie@test.com"},
        {"id": 4, "name": "David", "email": "david@test.com"}
    ])
    test_context.save_dataframe("raw_nulls", df)

    rules = [
        TransformRule(
            operator="handle_nulls",
            params={"action": "drop"}  # Không truyền subset -> drop nếu bất kỳ cột nào bị NULL
        )
    ]

    res_table = DataTransformer.transform("raw_nulls", rules, test_context)
    res_df = test_context.get_dataframe(res_table)

    assert len(res_df) == 2
    assert set(res_df["id"].tolist()) == {1, 4}


def test_handle_nulls_drop_subset_columns(test_context):
    """Test handle_nulls dạng 'drop' trên một tập hợp cột cụ thể (subset)."""
    df = pd.DataFrame([
        {"id": 1, "name": "Alice", "phone": None, "email": "alice@test.com"},
        {"id": 2, "name": "Bob", "phone": "0901234567", "email": None},
        {"id": 3, "name": "Charlie", "phone": None, "email": None}
    ])
    test_context.save_dataframe("raw_nulls_subset", df)

    # Chỉ drop nếu cột 'email' bị NULL (bỏ qua cột 'phone')
    rules = [
        TransformRule(
            operator="handle_nulls",
            params={"action": "drop", "subset": ["email"]}
        )
    ]

    res_table = DataTransformer.transform("raw_nulls_subset", rules, test_context)
    res_df = test_context.get_dataframe(res_table)

    assert len(res_df) == 1
    assert res_df.iloc[0]["name"] == "Alice"


# ==============================================================================
# 2. UNIT TESTS CHO TOÁN TỬ: group_by
# ==============================================================================

def test_group_by_single_column_multi_agg(test_context):
    """Test group_by 1 cột với nhiều hàm gom nhóm (SUM, AVG, COUNT, MAX)."""
    df = pd.DataFrame([
        {"dept": "IT", "salary": 1000},
        {"dept": "IT", "salary": 2000},
        {"dept": "IT", "salary": 3000},
        {"dept": "HR", "salary": 1500},
        {"dept": "HR", "salary": 2500}
    ])
    test_context.save_dataframe("salaries", df)

    rules = [
        TransformRule(
            operator="group_by",
            params={
                "by": ["dept"],
                "agg": {
                    "salary": "AVG"
                }
            }
        )
    ]

    res_table = DataTransformer.transform("salaries", rules, test_context)
    res_df = test_context.get_dataframe(res_table)

    assert len(res_df) == 2
    
    it_row = res_df[res_df["dept"] == "IT"].iloc[0]
    hr_row = res_df[res_df["dept"] == "HR"].iloc[0]

    assert float(it_row["salary_avg"]) == 2000.0
    assert float(hr_row["salary_avg"]) == 2000.0


def test_group_by_multiple_columns(test_context):
    """Test group_by gom nhóm theo nhiều cột đồng thời (Multi-column GroupBy)."""
    df = pd.DataFrame([
        {"region": "North", "status": "ACTIVE", "amount": 100},
        {"region": "North", "status": "ACTIVE", "amount": 200},
        {"region": "North", "status": "PENDING", "amount": 50},
        {"region": "South", "status": "ACTIVE", "amount": 300}
    ])
    test_context.save_dataframe("sales", df)

    rules = [
        TransformRule(
            operator="group_by",
            params={
                "by": ["region", "status"],
                "agg": {"amount": "SUM"}
            }
        )
    ]

    res_table = DataTransformer.transform("sales", rules, test_context)
    res_df = test_context.get_dataframe(res_table)

    assert len(res_df) == 3
    
    north_active = res_df[(res_df["region"] == "North") & (res_df["status"] == "ACTIVE")].iloc[0]
    assert float(north_active["amount_sum"]) == 300.0


# ==============================================================================
# 3. UNIT TESTS CHO: FilterEngine
# ==============================================================================

@pytest.fixture
def sample_filter_df():
    return pd.DataFrame([
        {"id": 1, "code": "A10", "score": 85, "active": True, "category": "Tech"},
        {"id": 2, "code": "B20", "score": 45, "active": False, "category": "Finance"},
        {"id": 3, "code": "A30", "score": 90, "active": True, "category": "Tech"},
        {"id": 4, "code": "C40", "score": 70, "active": True, "category": "Healthcare"},
        {"id": 5, "code": "B50", "score": 50, "active": False, "category": "Finance"}
    ])


def test_filter_comparison_operators(sample_filter_df):
    """Test các toán tử so sánh số học: >, <, >=, <=, ==, !=."""
    # Score >= 70
    cond1 = [FilterCondition(field="score", operator=">=", value=70)]
    res1 = FilterEngine.apply_filters(sample_filter_df, cond1)
    assert len(res1) == 3
    assert set(res1["id"].tolist()) == {1, 3, 4}

    # Score < 50
    cond2 = [FilterCondition(field="score", operator="<", value=50)]
    res2 = FilterEngine.apply_filters(sample_filter_df, cond2)
    assert len(res2) == 1
    assert res2.iloc[0]["id"] == 2


def test_filter_in_and_not_in_operators(sample_filter_df):
    """Test các toán tử tập hợp: IN và NOT IN."""
    # Category IN ['Tech', 'Healthcare']
    cond_in = [FilterCondition(field="category", operator="IN", value=["Tech", "Healthcare"])]
    res_in = FilterEngine.apply_filters(sample_filter_df, cond_in)
    assert len(res_in) == 3
    assert "Finance" not in res_in["category"].values

    # Category NOT IN ['Finance']
    cond_not_in = [FilterCondition(field="category", operator="NOT IN", value=["Finance"])]
    res_not_in = FilterEngine.apply_filters(sample_filter_df, cond_not_in)
    assert len(res_not_in) == 3


def test_filter_contains_operator(sample_filter_df):
    """Test toán tử lọc chuỗi CONTAINS."""
    # Code CONTAINS 'A'
    cond = [FilterCondition(field="code", operator="CONTAINS", value="A")]
    res = FilterEngine.apply_filters(sample_filter_df, cond)
    assert len(res) == 2
    assert set(res["code"].tolist()) == {"A10", "A30"}


def test_filter_chained_multiple_conditions(sample_filter_df):
    """Test chuỗi nhiều điều kiện lọc kết hợp (AND logic)."""
    conditions = [
        FilterCondition(field="active", operator="==", value=True),
        FilterCondition(field="score", operator=">", value=75),
        FilterCondition(field="category", operator="==", value="Tech")
    ]
    res = FilterEngine.apply_filters(sample_filter_df, conditions)
    
    assert len(res) == 2
    assert set(res["id"].tolist()) == {1, 3}


def test_filter_missing_column_warning(sample_filter_df):
    """Test trường hợp field không tồn tại trong DataFrame -> Bỏ qua rule không gây crash."""
    conditions = [
        FilterCondition(field="non_existent_column", operator="==", value="XYZ"),
        FilterCondition(field="score", operator="==", value=85)
    ]
    res = FilterEngine.apply_filters(sample_filter_df, conditions)
    
    # Cột không tồn tại bị bỏ qua, chỉ áp dụng điều kiện score == 85
    assert len(res) == 1
    assert res.iloc[0]["id"] == 1


=== FILE: ./tests/unit/test_validator.py ===
import pytest
from core.registry.validator import WorkflowValidator
from core.common.exceptions import WorkflowValidationError

def test_validate_valid_workflow_dict():
    valid_dict = {
        "workflow_id": "test_wf",
        "description": "Sample workflow",
        "steps": [
            {
                "step_id": "step_1",
                "driver": "nexacro",
                "mode": "batch",
                "endpoint": "http://localhost/api",
                "output_dataset": "ds_out_1"
            }
        ]
    }
    wf_config = WorkflowValidator.validate_dict(valid_dict)
    assert wf_config.workflow_id == "test_wf"
    assert len(wf_config.steps) == 1

def test_validate_duplicate_step_id():
    invalid_dict = {
        "workflow_id": "test_wf_dup",
        "steps": [
            {
                "step_id": "step_same",
                "driver": "nexacro",
                "endpoint": "http://localhost/api1",
                "output_dataset": "ds1"
            },
            {
                "step_id": "step_same",
                "driver": "nexacro",
                "endpoint": "http://localhost/api2",
                "output_dataset": "ds2"
            }
        ]
    }
    with pytest.raises(WorkflowValidationError) as exc_info:
        WorkflowValidator.validate_dict(invalid_dict)
    assert "Duplicate step_id" in str(exc_info.value)


=== FILE: ./tests/unit/test_duckdb_operators.py ===



=== FILE: ./tests/unit/test_runner.py ===
import pytest
import pandas as pd
from unittest.mock import MagicMock

from core.common.schemas import WorkflowConfig, StepConfig
from core.engine.runner import PipelineRunner


@pytest.fixture
def sample_workflow():
    step1 = StepConfig(
        step_id="step1",
        driver="nexacro",
        mode="batch",
        endpoint="http://mock.endpoint/step1",
        output_dataset="result_step1"
    )
    return WorkflowConfig(workflow_id="unit_test_wf", steps=[step1])


def test_runner_batch_step_execution(sample_workflow):
    mock_driver_instance = MagicMock()
    mock_driver_instance.execute.return_value = pd.DataFrame([
        {"id": 1, "status": "OK"},
        {"id": 2, "status": "OK"}
    ])

    runner = PipelineRunner(workflow=sample_workflow, pipeline_id="unit_runner_test")

    # Override driver resolution to return our mock instance
    runner._get_driver_instance = MagicMock(return_value=mock_driver_instance)

    context = runner.run()

    try:
        res_df = context.get_dataframe("result_step1")
        assert len(res_df) == 2
        assert res_df.iloc[0]["status"] == "OK"
        mock_driver_instance.execute.assert_called_once()
    finally:
        context.close()


=== FILE: ./core/common/schemas.py ===
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ColumnConfig(BaseModel):
    """Schema definition for table input columns and output projection."""
    name: Optional[str] = Field(None, description="Unique column field identifier")
    field: Optional[str] = Field(None, description="Source field path")
    alias: Optional[str] = Field(None, description="Target column alias")
    label: Optional[str] = Field(None, description="Human-readable label for UI rendering")
    title: Optional[str] = Field(None, description="Display title for UI table headers")
    type: str = Field(default="string", description="Data type: string, number, boolean")
    default: Optional[Any] = Field(None, description="Default initial value")
    visible: bool = Field(default=True, description="Column visibility status in UI output")


class WorkflowInput(BaseModel):
    """Schema definition for dynamic user inputs submitted via UI or API."""
    name: str = Field(..., description="Unique input variable key name")
    label: Optional[str] = Field(None, description="Human-readable label for UI rendering")
    type: str = Field(default="string", description="UI control type: string, number, select, boolean, table")
    default: Optional[Any] = Field(None, description="Default initial value")
    options: Optional[List[Any]] = Field(default=None, description="Options list if input type is select")
    columns: Optional[List[ColumnConfig]] = Field(default=None, description="Column definitions if input type is table")
    description: Optional[str] = Field(None, description="Tooltip or contextual help text")


class VariableConfig(BaseModel):
    """Configuration for mapping execution context variables with support for datasets and aliasing."""
    source: Optional[str] = Field(None, description="Dot-notation or JSONPath source path")
    jsonpath: Optional[str] = Field(None, description="Legacy JSONPath query expression")
    type: Optional[str] = Field(default="parameter", description="Variable type: parameter or dataset")
    default: Optional[Any] = Field(None, description="Fallback static default value if evaluation is null")
    columns: Optional[List[ColumnConfig]] = Field(default=None, description="Column mappings for datasets")


class FilterCondition(BaseModel):
    """Schema definition for pre-call or post-fetch row filtering logic."""
    field: str = Field(..., description="Target dataset column name")
    operator: str = Field(..., description="Filter comparison operator (e.g., eq, in, gt, contains)")
    value: Any = Field(..., description="Expected value to compare against")


class TransformRule(BaseModel):
    """Schema definition for DuckDB pipeline transformation operators."""
    operator: str = Field(..., description="Transformation operator name (e.g., handle_nulls, deduplicate, group_by)")
    params: Dict[str, Any] = Field(default_factory=dict, description="Operator execution parameters")


class OutputConfig(BaseModel):
    """Schema definition for custom UI table output rendering."""
    display_title: Optional[str] = Field(None, description="Human-readable table title for Streamlit UI")
    columns: List[ColumnConfig] = Field(default_factory=list, description="Column visibility and label mapping")


class StepConfig(BaseModel):
    """Schema definition for an individual pipeline step execution stage."""
    step_id: str = Field(..., description="Unique step identifier")
    driver: str = Field(..., description="Protocol driver identifier (e.g., nexacro, rest, passthrough)")
    mode: str = Field(default="batch", description="Execution mode: batch or chained_loop")
    method: str = Field(default="POST", description="HTTP/RPC protocol method (e.g., GET, POST, PUT, DELETE)")
    endpoint: str = Field(default="", description="Target HTTP or RPC API endpoint URL")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Variable resolution rules")
    filters: List[FilterCondition] = Field(default_factory=list, description="List of dataset row filters")
    transformations: List[TransformRule] = Field(default_factory=list, description="Ordered list of DuckDB transformation rules")
    output_dataset: str = Field(..., description="Target DuckDB table name to store step results")
    output_config: Optional[OutputConfig] = Field(None, description="Custom UI rendering configuration")
    loop_source: Optional[str] = Field(None, description="Source table name for chained_loop execution mode")


class WorkflowConfig(BaseModel):
    """Declarative workflow execution pipeline schema definition."""
    workflow_id: str = Field(..., description="Unique workflow catalog identifier")
    description: Optional[str] = Field(None, description="Detailed pipeline summary and execution flow overview")
    inputs: List[WorkflowInput] = Field(default_factory=list, description="Declarative input parameter schemas")
    steps: List[StepConfig] = Field(..., description="Sequential list of execution steps")


=== FILE: ./core/common/logger.py ===
import sys
from pathlib import Path
from loguru import logger
from config.settings import settings


def setup_logger():
    """Configures system-wide logging formatting, log levels, and sink file rotation."""
    logger.remove()  # Clear default handlers

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    # Console Handler
    logger.add(
        sys.stdout,
        format=log_format,
        level="DEBUG" if settings.DEBUG else "INFO",
        colorize=True
    )

    # Rotating File Handler (Production Debugging)
    log_dir = settings.LOGS_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logger.add(
        log_dir / "omni_etl.log",
        format=log_format,
        level="INFO",
        rotation="10 MB",
        retention="7 days",
        enqueue=True
    )

    return logger


log = setup_logger()


=== FILE: ./core/common/exceptions.py ===
class OmniETLException(Exception):
    """Base exception class for all errors in omni-etl-studio."""
    pass


class WorkflowValidationError(OmniETLException):
    """Raised when JSON workflow schemas or catalog definitions fail validation."""
    pass


class EvaluatorError(OmniETLException):
    """Raised when variable resolution or JsonPath extraction fails."""
    pass


class FilterError(OmniETLException):
    """Raised during pre-call record filtering execution."""
    pass


class TransformationError(OmniETLException):
    """Raised when data transformation operators (DuckDB or Python) fail."""
    pass


class DriverError(OmniETLException):
    """Raised during protocol payload construction, network transport, or parsing."""
    pass


class StorageError(OmniETLException):
    """Raised during DuckDB schema creation, table registration, or SQL execution."""
    pass


=== FILE: ./core/storage/context.py ===
import re
import duckdb
import pandas as pd
from typing import Optional
from core.common.exceptions import StorageError
from core.common.logger import log


class PipelineContext:
    """Manages DuckDB storage with a global persistent schema for cross-session data accumulation."""

    DB_FILE = "omni_etl_studio.duckdb"
    SHARED_SCHEMA = "shared_storage"

    def __init__(self, pipeline_id: Optional[str] = None):
        self.pipeline_id = pipeline_id or "default_session"
        clean_id = re.sub(r'[^a-zA-Z0-9_]', '_', self.pipeline_id)
        self.schema_name = f"ns_{clean_id}"
        self.shared_schema = self.SHARED_SCHEMA
        
        try:
            # Mở kết nối vĩnh viễn tới file DuckDB vật lý trên đĩa
            self.conn = duckdb.connect(database=self.DB_FILE)
            self._init_schema()
        except Exception as e:
            raise StorageError(f"Failed to initialize DuckDB storage context: {str(e)}")

    def _init_schema(self):
        """Initializes runtime execution schema and the persistent shared storage schema."""
        self.conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema_name};")
        self.conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self.shared_schema};")

    def save_dataframe(self, table_name: str, df: pd.DataFrame, if_exists: str = "replace"):
        full_table = f"{self.schema_name}.{table_name}"
        try:
            self.conn.register("temp_df", df)
            try:
                if if_exists == "replace":
                    self.conn.execute(f"CREATE OR REPLACE TABLE {full_table} AS SELECT * FROM temp_df;")
                elif if_exists == "append":
                    self.conn.execute(f"INSERT INTO {full_table} SELECT * FROM temp_df;")
            finally:
                self.conn.unregister("temp_df")
        except Exception as e:
            raise StorageError(f"Failed to save DataFrame into table {full_table}: {str(e)}")

    def get_dataframe(self, table_name: str) -> pd.DataFrame:
        """Searches active execution schema first, then falls back to persistent shared_storage."""
        full_table = f"{self.schema_name}.{table_name}"
        shared_table = f"{self.shared_schema}.{table_name}"
        try:
            check_exec = self.conn.execute(f"""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = '{self.schema_name}' AND table_name = '{table_name}';
            """).df()
            if not check_exec.empty:
                return self.conn.execute(f"SELECT * FROM {full_table};").df()

            check_shared = self.conn.execute(f"""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = '{self.shared_schema}' AND table_name = '{table_name}';
            """).df()
            if not check_shared.empty:
                return self.conn.execute(f"SELECT * FROM {shared_table};").df()

            return pd.DataFrame()
        except Exception as e:
            raise StorageError(f"Failed to fetch table {table_name}: {str(e)}")

    def execute_sql(self, query: str) -> pd.DataFrame:
        try:
            return self.conn.execute(query).df()
        except Exception as e:
            raise StorageError(f"SQL execution error [{query}]: {str(e)}")

    def clean_temporary_schemas(self):
        """Safely cleans old temporary run schemas while preserving shared_storage."""
        try:
            schemas_df = self.conn.execute("""
                SELECT schema_name FROM information_schema.schemata 
                WHERE schema_name LIKE 'ns_run_%';
            """).df()
            if not schemas_df.empty:
                for s_name in schemas_df["schema_name"].tolist():
                    self.conn.execute(f"DROP SCHEMA IF EXISTS {s_name} CASCADE;")
                log.info("Cleaned up temporary execution schemas.")
        except Exception as e:
            log.warning(f"Error cleaning temporary schemas: {str(e)}")

    def close(self):
        """Closes connection without deleting persistent historical data."""
        try:
            self.conn.close()
        except Exception:
            pass


=== FILE: ./core/engine/runner.py ===
from typing import Any, Dict, Optional
from uuid import uuid4
import pandas as pd

from core.common.exceptions import OmniETLException
from core.common.logger import log
from core.common.schemas import StepConfig, WorkflowConfig
from core.engine.filter import FilterEngine
from core.engine.resolver import VariableResolver
from core.engine.transformer import DataTransformer
from core.storage.context import PipelineContext
from drivers.base import DriverRegistry


class PipelineRunner:
    """Executes a validated WorkflowConfig pipeline step-by-step."""

    def __init__(self, workflow: WorkflowConfig, pipeline_id: Optional[str] = None):
        self.workflow = workflow
        self.pipeline_id = pipeline_id or f"run_{uuid4().hex[:8]}"
        self.context = PipelineContext(pipeline_id=self.pipeline_id)

    def run(self, global_input: Optional[Dict[str, Any]] = None, session: Optional[Dict[str, Any]] = None) -> PipelineContext:
        """Executes the pipeline workflow across all configured steps."""
        
        # Binds global inputs directly into context storage for downstream Operators
        self.context.inputs = global_input or {}
        
        global_context = {
            "global_input": global_input or {},
            "session": session or {}
        }

        log.info(f"Starting execution of pipeline '{self.workflow.workflow_id}' (Run ID: {self.pipeline_id})")

        try:
            for step in self.workflow.steps:
                self.execute_step(step, global_context)
            return self.context
        except Exception as e:
            self.context.close()
            raise OmniETLException(f"Pipeline execution failure: {str(e)}")

    def _apply_output_config_projection(self, step: StepConfig) -> None:
        """Projects, filters, and reorders DuckDB table columns according to step.output_config strictly."""
        # 1. Ép kiểu output_config về dict an toàn kể cả khi là Pydantic Model
        output_config = step.output_config
        if hasattr(output_config, "model_dump"):
            output_config = output_config.model_dump()
        elif not isinstance(output_config, dict):
            output_config = {}

        columns_config = output_config.get("columns", [])

        if not columns_config:
            log.info(f"[SQL PROJECT SKIPPED] No columns_config defined for step [{step.step_id}]")
            return

        full_table = f"{self.context.schema_name}.{step.output_dataset}"
        
        # 2. Lấy danh sách cột hiện có trong bảng DuckDB
        try:
            check_df = self.context.execute_sql(f"SELECT * FROM {full_table} LIMIT 0;")
            existing_cols = check_df.columns.tolist()
        except Exception as e:
            log.warning(f"[SQL PROJECT SKIPPED] Table '{full_table}' does not exist: {str(e)}")
            return

        # 3. Lọc & Sắp xếp các cột hiển thị theo đúng thứ tự khai báo trong JSON
        select_exprs = []
        for c in columns_config:
            field = c.get("field")
            is_visible = c.get("visible", True)
            
            # Chỉ lấy các cột visible và có tồn tại trong bảng DuckDB
            if is_visible and field in existing_cols:
                select_exprs.append(f'"{field}"')

        if select_exprs:
            sql = f"CREATE OR REPLACE TABLE {full_table} AS SELECT {', '.join(select_exprs)} FROM {full_table};"
            log.info(f"[SQL PROJECT COLUMNS EXECUTE] {sql}")
            self.context.execute_sql(sql)

    def execute_step(self, step: StepConfig, global_context: Dict[str, Any]) -> None:
        """Executes a single pipeline step based on driver type and execution mode."""
        log.info(f"Executing step [{step.step_id}] in mode '{step.mode}' via driver '{step.driver}'")

        # CASE 1: PURE TRANSFORM STEP (PASSTHROUGH / NO API CALL)
        if step.driver in ["passthrough", "none", ""] or not step.endpoint:
            log.info(f"Step [{step.step_id}] is a Pure Transform Step. Skipping API invocation.")
            
            prev_table = step.loop_source or (
                self.workflow.steps[self.workflow.steps.index(step) - 1].output_dataset 
                if self.workflow.steps.index(step) > 0 else ""
            )
            
            if prev_table:
                self.context.execute_sql(
                    f"CREATE OR REPLACE TABLE {self.context.schema_name}.{step.output_dataset} AS "
                    f"SELECT * FROM {self.context.schema_name}.{prev_table};"
                )
                
                if step.transformations:
                    DataTransformer.transform(step.output_dataset, step.transformations, self.context)

            # Áp dụng chuẩn hóa cột trong DuckDB theo output_config
            self._apply_output_config_projection(step)
            return

        # CASE 2: API INVOCATION STEP (BATCH OR CHAINED LOOP)
        driver_cls = DriverRegistry.get(step.driver)
        driver = driver_cls()

        if step.mode == "batch":
            self._execute_batch_step(step, driver, global_context)
        elif step.mode == "chained_loop":
            self._execute_chained_loop_step(step, driver, global_context)
        else:
            raise OmniETLException(f"Unsupported execution mode: {step.mode}")

        # Áp dụng chuẩn hóa cột trong DuckDB theo output_config
        self._apply_output_config_projection(step)

    def _execute_batch_step(self, step: StepConfig, driver: Any, global_context: Dict[str, Any]) -> None:
        resolved_vars = VariableResolver.resolve(step.variables or {}, self.context, global_context)
        raw_df = driver.execute(endpoint=step.endpoint, variables=resolved_vars, method=step.method)

        if step.filters and not raw_df.empty:
            raw_df = FilterEngine.apply_filters(raw_df, step.filters)

        if raw_df.empty or len(raw_df.columns) == 0:
            raw_df = pd.DataFrame(columns=["status_msg"])

        raw_table_name = f"{step.step_id}_raw"
        self.context.save_dataframe(raw_table_name, raw_df)

        final_table = DataTransformer.transform(raw_table_name, step.transformations or [], self.context)

        if final_table != step.output_dataset:
            self.context.execute_sql(
                f"CREATE OR REPLACE TABLE {self.context.schema_name}.{step.output_dataset} AS "
                f"SELECT * FROM {self.context.schema_name}.{final_table};"
            )

    def _execute_chained_loop_step(self, step: StepConfig, driver: Any, global_context: Dict[str, Any]) -> None:
        if not step.loop_source:
            raise OmniETLException(f"Chained loop step [{step.step_id}] requires 'loop_source'.")

        source_df = self.context.get_dataframe(step.loop_source)
        loop_records = source_df.to_dict(orient="records") if not source_df.empty else []

        accumulated_dfs = []
        for row in loop_records:
            resolved_vars = VariableResolver.resolve(
                step.variables or {}, self.context, global_context, current_loop_row=row
            )

            res_df = driver.execute(endpoint=step.endpoint, variables=resolved_vars, method=step.method)
            if step.filters and not res_df.empty:
                res_df = FilterEngine.apply_filters(res_df, step.filters)

            if not res_df.empty:
                accumulated_dfs.append(res_df)

        if accumulated_dfs:
            merged_df = pd.concat(accumulated_dfs, ignore_index=True)
        else:
            merged_df = pd.DataFrame(columns=source_df.columns if not source_df.empty else ["status_msg"])

        if len(merged_df.columns) == 0:
            merged_df["status_msg"] = None

        raw_table_name = f"{step.step_id}_raw"
        self.context.save_dataframe(raw_table_name, merged_df)

        final_table = DataTransformer.transform(raw_table_name, step.transformations or [], self.context)

        if final_table != step.output_dataset:
            self.context.execute_sql(
                f"CREATE OR REPLACE TABLE {self.context.schema_name}.{step.output_dataset} AS "
                f"SELECT * FROM {self.context.schema_name}.{final_table};"
            )


=== FILE: ./core/engine/evaluator.py ===
from typing import Any, Dict, Union
from jsonpath_ng.ext import parse
from core.common.schemas import VariableConfig, VariableRule
from core.common.exceptions import EvaluatorError
from core.common.logger import log


class VariableEvaluator:
    """Evaluates dynamic variable substitution maps using JSONPath syntax or static fallbacks."""

    @staticmethod
    def evaluate(rule: Union[VariableConfig, VariableRule], context_data: Dict[str, Any]) -> Any:
        """Resolves a single variable rule against context data with default fallback."""
        if not rule:
            return None

        # 1. Attempt JSONPath extraction first if defined
        if rule.jsonpath:
            try:
                jsonpath_expr = parse(rule.jsonpath)
                matches = jsonpath_expr.find(context_data)
                if matches and matches[0].value is not None:
                    return matches[0].value
                else:
                    log.debug(f"JSONPath '{rule.jsonpath}' found no matches in context. Falling back to default.")
            except Exception as e:
                raise EvaluatorError(f"Failed to evaluate JSONPath [{rule.jsonpath}]: {str(e)}")

        # 2. Fall back to static default value
        return rule.default

    @classmethod
    def evaluate_all(
        cls, 
        var_map: Dict[str, Union[VariableConfig, VariableRule]], 
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluates a dictionary of variable rules against context data."""
        resolved: Dict[str, Any] = {}

        if not var_map:
            return resolved

        for var_name, rule in var_map.items():
            resolved[var_name] = cls.evaluate(rule, context_data)

        return resolved


=== FILE: ./core/engine/resolver.py ===
import re
from typing import Any, Dict, List, Optional
import pandas as pd
from core.storage.context import PipelineContext


class VariableResolver:
    """Resolves variable specifications into parameters and dataset structures for Drivers."""

    @staticmethod
    def resolve(
        var_config: Dict[str, Any], 
        context: PipelineContext, 
        global_context: Optional[Dict[str, Any]] = None,
        current_loop_row: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        resolved_params: Dict[str, Any] = {}
        resolved_datasets: Dict[str, List[Dict[str, Any]]] = {}

        for var_name, config in var_config.items():
            # Convert Pydantic object to dict if necessary
            cfg = config.dict() if hasattr(config, "dict") else config
            is_dataset = cfg.get("type") == "dataset"

            if is_dataset:
                resolved_datasets[var_name] = VariableResolver._resolve_dataset(
                    cfg, context, global_context or {}, current_loop_row
                )
            else:
                source_path = cfg.get("source") or cfg.get("jsonpath", "")
                resolved_params[var_name] = VariableResolver._resolve_scalar(
                    source_path, context, global_context or {}, current_loop_row
                )

        return {"parameters": resolved_params, "datasets": resolved_datasets}

    @staticmethod
    def _resolve_scalar(
        path: str, 
        context: PipelineContext, 
        global_context: Dict[str, Any], 
        current_loop_row: Optional[Dict[str, Any]]
    ) -> Any:
        raw_val = VariableResolver._extract_by_path(path, context, global_context, current_loop_row)
        if isinstance(raw_val, list) and len(raw_val) > 0:
            return raw_val[0]
        return raw_val

    @staticmethod
    def _resolve_dataset(
        config: Dict[str, Any], 
        context: PipelineContext, 
        global_context: Dict[str, Any], 
        current_loop_row: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        columns_def = config.get("columns", [])
        if not columns_def:
            return []

        extracted_cols: Dict[str, List[Any]] = {}
        max_rows = 1

        for col_def in columns_def:
            c_cfg = col_def.dict() if hasattr(col_def, "dict") else col_def
            field_path = c_cfg.get("field") or c_cfg.get("name", "")
            alias = c_cfg.get("alias") or VariableResolver._clean_alias(field_path)

            val = VariableResolver._extract_by_path(field_path, context, global_context, current_loop_row)

            if isinstance(val, (list, pd.Series)):
                col_values = list(val)
                max_rows = max(max_rows, len(col_values))
            elif isinstance(val, pd.DataFrame):
                col_values = val.iloc[:, 0].tolist() if not val.empty else []
                max_rows = max(max_rows, len(col_values))
            else:
                col_values = [val] if val is not None else []

            extracted_cols[alias] = col_values

        if not extracted_cols:
            return []

        result_rows: List[Dict[str, Any]] = []
        for i in range(max_rows):
            row_dict = {}
            for col_name, val_list in extracted_cols.items():
                if i < len(val_list):
                    row_dict[col_name] = val_list[i]
                elif len(val_list) == 1:
                    row_dict[col_name] = val_list[0]
                else:
                    row_dict[col_name] = None
            result_rows.append(row_dict)

        return result_rows

    @staticmethod
    def _extract_by_path(
        path: str, 
        context: PipelineContext, 
        global_context: Dict[str, Any], 
        current_loop_row: Optional[Dict[str, Any]]
    ) -> Any:
        if not path:
            return None

        # 1. Namespace loop_row
        if path.startswith("loop_row"):
            sub_path = path.replace("loop_row.", "").replace("loop_row", "")
            return VariableResolver._get_nested_value(current_loop_row or {}, sub_path)

        # 2. Namespace global_input
        if path.startswith("global_input"):
            sub_path = path.replace("global_input.", "").replace("global_input", "")
            input_data = global_context.get("global_input", {})
            return VariableResolver._get_nested_value(input_data, sub_path)

        # 3. Namespace session
        if path.startswith("session"):
            sub_path = path.replace("session.", "").replace("session", "")
            session_data = global_context.get("session", {})
            return VariableResolver._get_nested_value(session_data, sub_path)

        # 4. Namespace stepX (Truy vấn từ DuckDB Context)
        parts = path.split(".", 1)
        step_id = parts[0]
        field_attr = parts[1] if len(parts) > 1 else ""

        # Bỏ chữ '.output' nếu người dùng gõ step1.output.product_id
        if field_attr.startswith("output."):
            field_attr = field_attr.replace("output.", "", 1)

        table_data = context.get_dataframe(step_id)
        if table_data is not None and isinstance(table_data, pd.DataFrame):
            clean_field, idx = VariableResolver._parse_array_idx(field_attr)
            if clean_field in table_data.columns:
                series_vals = table_data[clean_field].tolist()
                if idx is not None:
                    return series_vals[idx] if 0 <= idx < len(series_vals) else None
                return series_vals

        return None

    @staticmethod
    def _get_nested_value(data: Any, path: str) -> Any:
        if not path:
            return data
        
        clean_path, idx = VariableResolver._parse_array_idx(path)
        parts = clean_path.split(".")
        curr = data

        for p in parts:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            elif isinstance(curr, list):
                if p.isdigit():
                    idx_p = int(p)
                    curr = curr[idx_p] if 0 <= idx_p < len(curr) else None
                else:
                    curr = [item.get(p) for item in curr if isinstance(item, dict) and p in item]
            else:
                return None

        if idx is not None and isinstance(curr, list):
            return curr[idx] if 0 <= idx < len(curr) else None

        return curr

    @staticmethod
    def _parse_array_idx(path: str):
        match = re.search(r"^(.*)\[(\d+)\]$", path)
        if match:
            return match.group(1), int(match.group(2))
        return path, None

    @staticmethod
    def _clean_alias(field_path: str) -> str:
        clean_path, _ = VariableResolver._parse_array_idx(field_path)
        return clean_path.split(".")[-1]


=== FILE: ./core/engine/operators/registry.py ===
from typing import Dict, Type
from core.engine.operators.base import BaseOperator
from core.common.exceptions import TransformationError

class OperatorRegistry:
    """Central registry mapping operator identifiers to concrete operator instances."""
    _registry: Dict[str, Type[BaseOperator]] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(operator_cls: Type[BaseOperator]):
            cls._registry[name.lower()] = operator_cls
            return operator_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> BaseOperator:
        operator_cls = cls._registry.get(name.lower())
        if not operator_cls:
            raise TransformationError(f"Operator '{name}' is not registered.")
        return operator_cls()


=== FILE: ./core/engine/operators/python/custom_script.py ===
from typing import Any, Dict, Callable
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("python_transform")
class PythonCustomTransformOperator(BaseOperator):
    """Executes arbitrary Python function transformations using Pandas DataFrames."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        transform_func: Callable = params.get("function")
        
        if not transform_func or not callable(transform_func):
            raise ValueError("PythonCustomTransformOperator requires a callable 'function' in params.")

        # Extract DataFrame from DuckDB
        df = context.get_dataframe(table_name)

        # Apply custom Python function
        transformed_df = transform_func(df)

        # Save back to DuckDB table
        context.save_dataframe(table_name, transformed_df)
        return table_name


=== FILE: ./core/engine/operators/python/__init__.py ===



=== FILE: ./core/engine/operators/base.py ===
from abc import ABC, abstractmethod
from typing import Any, Dict
from core.storage.context import PipelineContext

class BaseOperator(ABC):
    """Abstract Base Class for all DuckDB and Python Data Operators."""

    @abstractmethod
    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        """Executes transformation on a table inside PipelineContext.
        
        Returns the resulting table name.
        """
        pass


=== FILE: ./core/engine/operators/duckdb/reshape.py ===
from typing import Any, Dict
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("pivot")
class DuckDBPivotOperator(BaseOperator):
    """Executes SQL PIVOT operations in DuckDB."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        on_col = params.get("on")
        using_col = params.get("using")
        group_by = params.get("group_by", [])

        full_table = f"{context.schema_name}.{table_name}"
        group_clause = f"GROUP BY {', '.join([f'\"{col}\"' for col in group_by])}" if group_by else ""

        query = f"""
            CREATE OR REPLACE TABLE {full_table} AS
            PIVOT {full_table}
            ON "{on_col}"
            USING SUM("{using_col}")
            {group_clause};
        """
        context.execute_sql(query)
        return table_name


@OperatorRegistry.register("unpivot")
class DuckDBUnpivotOperator(BaseOperator):
    """Executes SQL UNPIVOT (Melt) operations in DuckDB."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        on_cols = params.get("on", [])
        full_table = f"{context.schema_name}.{table_name}"
        cols_str = ", ".join([f'"{col}"' for col in on_cols])

        query = f"""
            CREATE OR REPLACE TABLE {full_table} AS
            UNPIVOT {full_table}
            ON {cols_str};
        """
        context.execute_sql(query)
        return table_name


=== FILE: ./core/engine/operators/duckdb/aggregate.py ===
from typing import Any, Dict
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("group_by")
class DuckDBGroupByOperator(BaseOperator):
    """Executes SQL GROUP BY aggregations dynamically in DuckDB with automatic type casting for numeric operations."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        by_cols = params.get("by", [])
        agg_map = params.get("agg", {})  # e.g., {"quantity": "SUM", "score": "AVG"}

        full_table = f"{context.schema_name}.{table_name}"
        by_clause = ", ".join([f'"{col}"' for col in by_cols]) if by_cols else ""

        agg_exprs = []
        for col, func in agg_map.items():
            func_upper = func.upper()
            # Áp dụng TRY_CAST cho các hàm toán học để tránh lỗi sum(VARCHAR)
            if func_upper in ["SUM", "AVG", "MEAN", "MEDIAN", "STDDEV"]:
                agg_exprs.append(f'{func_upper}(TRY_CAST("{col}" AS DOUBLE)) AS "{col}_{func.lower()}"')
            else:
                agg_exprs.append(f'{func_upper}("{col}") AS "{col}_{func.lower()}"')

        if by_cols:
            select_clause = f"{by_clause}, " + ", ".join(agg_exprs) if agg_exprs else by_clause
            group_clause = f"GROUP BY {by_clause}"
        else:
            select_clause = ", ".join(agg_exprs)
            group_clause = ""

        query = f"CREATE OR REPLACE TABLE {full_table} AS SELECT {select_clause} FROM {full_table} {group_clause};"
        context.execute_sql(query)
        return table_name


=== FILE: ./core/engine/operators/duckdb/enrichment.py ===
import re
import streamlit as st
from core.common.logger import log
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext

@OperatorRegistry.register("add_date_column")
class AddDateColumnOperator(BaseOperator):
    """Adds a computed date/timestamp column to the active DuckDB table."""

    def execute(self, table_name: str, params: dict, context: PipelineContext) -> str:
        target_column = params.get("target_column", "created_date")
        sql_expr = "CURRENT_TIMESTAMP" if params.get("date_source") == "current_timestamp" else "CURRENT_DATE"
        full_table = f"{context.schema_name}.{table_name}" if getattr(context, "schema_name", None) else table_name

        check_df = context.execute_sql(f"SELECT * FROM {full_table} LIMIT 0;")
        if target_column not in check_df.columns:
            query = f"CREATE OR REPLACE TABLE {full_table} AS SELECT *, {sql_expr} AS {target_column} FROM {full_table};"
            log.info(f"[SQL EXECUTE] {query}")
            context.execute_sql(query)

        return table_name


@OperatorRegistry.register("accumulate_data")
class AccumulateDataOperator(BaseOperator):
    """Accumulates new records, deduplicates, and replaces old records directly in persistent storage."""

    def execute(self, table_name: str, params: dict, context: PipelineContext) -> str:
        target_history_table = params.get("target_history_table", "ds_historical_data")
        dedup_keys = params.get("dedup_keys", ["product_id"])
        order_by = params.get("order_by", "created_date DESC")
        
        current_table = f"{context.schema_name}.{table_name}"
        shared_schema = getattr(context, "shared_schema", "shared_storage")
        persistent_table = f"{shared_schema}.{target_history_table}"

        init_sql = f"CREATE TABLE IF NOT EXISTS {persistent_table} AS SELECT * FROM {current_table} WHERE 1=0;"
        context.execute_sql(init_sql)

        try:
            context.execute_sql(f"ALTER TABLE {persistent_table} ADD COLUMNS FROM {current_table};")
        except Exception:
            pass

        insert_sql = f"INSERT INTO {persistent_table} BY NAME SELECT * FROM {current_table};"
        context.execute_sql(insert_sql)

        if dedup_keys:
            partition_str = ", ".join(dedup_keys)
            dedup_sql = f"""
                CREATE OR REPLACE TABLE {persistent_table} AS 
                SELECT * EXCLUDE (row_num) FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY {partition_str} ORDER BY {order_by}) as row_num
                    FROM {persistent_table}
                ) WHERE row_num = 1;
            """
            context.execute_sql(dedup_sql)

        sync_sql = f"CREATE OR REPLACE TABLE {current_table} AS SELECT * FROM {persistent_table};"
        context.execute_sql(sync_sql)

        return table_name


@OperatorRegistry.register("sql_transform")
class SqlTransformOperator(BaseOperator):
    """Executes SQL transform by extracting search_table.product_id directly from context.inputs."""

    def execute(self, table_name: str, params: dict, context: PipelineContext) -> str:
        full_table = f"{context.schema_name}.{table_name}" if getattr(context, "schema_name", None) else table_name
        
        # 1. Lấy dữ liệu global_input chuẩn từ context.inputs vừa được gán ở runner.py
        global_input = getattr(context, "inputs", {}) or st.session_state.get("last_global_input", {})

        log.info(f"[FILTER DEBUG] Global Inputs available keys: {list(global_input.keys()) if isinstance(global_input, dict) else 'Not a dict'}")
        log.info(f"[FILTER DEBUG] Full Global Inputs Content: {global_input}")

        product_ids = []

        # 2. Đọc trực tiếp đường dẫn global_input.search_table.product_id
        if isinstance(global_input, dict) and "search_table" in global_input:
            search_table = global_input.get("search_table")
            if isinstance(search_table, list):
                product_ids = [
                    str(row.get("product_id")).strip() 
                    for row in search_table 
                    if isinstance(row, dict) and row.get("product_id") is not None
                ]
                log.info(f"[FILTER DEBUG] Resolved 'search_table.product_id' -> Extracted IDs: {product_ids}")

        # 3. Thực thi SQL WHERE CAST(product_id AS VARCHAR) IN ('SP-001', 'SP-002')
        if "where_clause" in params and product_ids:
            formatted_ids = ", ".join([f"'{pid}'" for pid in product_ids])
            sql = f"CREATE OR REPLACE TABLE {full_table} AS SELECT * FROM {full_table} WHERE CAST(product_id AS VARCHAR) IN ({formatted_ids});"
        elif "query" in params:
            sql = f"CREATE OR REPLACE TABLE {full_table} AS {params['query'].replace(table_name, full_table)};"
        else:
            log.warning("[SQL TRANSFORM WARNING] Product IDs empty. Retaining full accumulated step output.")
            sql = f"CREATE OR REPLACE TABLE {full_table} AS SELECT * FROM {full_table};"

        log.info(f"[SQL EXECUTE STEP] {sql}")
        context.execute_sql(sql)

        return table_name


=== FILE: ./core/engine/operators/duckdb/cleaning.py ===
from typing import Any, Dict
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("deduplicate")
class DuckDBDeduplicateOperator(BaseOperator):
    """Executes row deduplication using DuckDB QUALIFY & ROW_NUMBER()."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        subset = params.get("subset", [])
        order_by = params.get("order_by", "")
        full_table = f"{context.schema_name}.{table_name}" if getattr(context, "schema_name", None) else table_name

        if subset:
            cols_str = ", ".join([f'"{col}"' for col in subset])
            order_clause = f"ORDER BY {order_by}" if order_by else ""
            query = f"""
                CREATE OR REPLACE TABLE {full_table} AS
                SELECT * FROM {full_table}
                QUALIFY ROW_NUMBER() OVER (PARTITION BY {cols_str} {order_clause}) = 1;
            """
        else:
            query = f"CREATE OR REPLACE TABLE {full_table} AS SELECT DISTINCT * FROM {full_table};"

        context.execute_sql(query)
        return table_name


@OperatorRegistry.register("handle_nulls")
class DuckDBHandleNullsOperator(BaseOperator):
    """Handles NULL values in DuckDB tables by dropping incomplete rows or filling default values."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        # Chuẩn hóa: Dùng duy nhất 'strategy' (drop / fill)
        strategy = params.get("strategy", "drop")
        full_table = f"{context.schema_name}.{table_name}" if getattr(context, "schema_name", None) else table_name

        if strategy == "drop":
            subset = params.get("subset", [])
            if subset:
                where_clause = " AND ".join([f'"{col}" IS NOT NULL' for col in subset])
            else:
                cols_df = context.execute_sql(f"DESCRIBE SELECT * FROM {full_table};")
                cols = cols_df["column_name"].tolist() if hasattr(cols_df, "columns") else []
                where_clause = " AND ".join([f'"{col}" IS NOT NULL' for col in cols]) if cols else "1=1"

            query = f"CREATE OR REPLACE TABLE {full_table} AS SELECT * FROM {full_table} WHERE {where_clause};"
            context.execute_sql(query)

        elif strategy == "fill":
            fill_map = params.get("fill_value", {})
            if fill_map:
                set_clauses = [f'"{col}" = COALESCE("{col}", \'{val}\')' for col, val in fill_map.items()]
                query = f"UPDATE {full_table} SET {', '.join(set_clauses)};"
                context.execute_sql(query)

        return table_name


@OperatorRegistry.register("select_rename")
class DuckDBSelectRenameOperator(BaseOperator):
    """Selects specific columns, renames fields, and casts column data types in DuckDB."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        columns_map = params.get("columns", {})  # e.g., {"old_name": "new_name"}
        casts_map = params.get("casts", {})      # e.g., {"price": "DOUBLE", "age": "INTEGER"}
        keep_cols = params.get("keep", [])

        full_table = f"{context.schema_name}.{table_name}" if getattr(context, "schema_name", None) else table_name

        if keep_cols:
            select_exprs = []
            for col in keep_cols:
                target_name = columns_map.get(col, col)
                if col in casts_map:
                    select_exprs.append(f'TRY_CAST("{col}" AS {casts_map[col]}) AS "{target_name}"')
                else:
                    select_exprs.append(f'"{col}" AS "{target_name}"')
            select_str = ", ".join(select_exprs)
            query = f"CREATE OR REPLACE TABLE {full_table} AS SELECT {select_str} FROM {full_table};"
            context.execute_sql(query)
        else:
            for old_col, new_col in columns_map.items():
                context.execute_sql(f'ALTER TABLE {full_table} RENAME COLUMN "{old_col}" TO "{new_col}";')

        return table_name


=== FILE: ./core/engine/operators/duckdb/__init__.py ===
from core.engine.operators.duckdb import aggregate, cleaning, enrichment, join, reshape

__all__ = ["aggregate", "cleaning", "enrichment", "join", "reshape"]


=== FILE: ./core/engine/operators/duckdb/join.py ===
from typing import Any, Dict
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext


@OperatorRegistry.register("join")
class DuckDBJoinOperator(BaseOperator):
    """Executes SQL JOIN operations (INNER, LEFT, RIGHT, FULL) between two DuckDB tables."""

    def execute(self, table_name: str, params: Dict[str, Any], context: PipelineContext) -> str:
        right_table = params.get("right_table")
        join_type = params.get("how", "LEFT").upper()  # INNER, LEFT, RIGHT, FULL
        on_keys = params.get("on", [])  # e.g., ["product_id"] or {"left_key": "right_key"}
        select_cols = params.get("select", "*")  # e.g., "t1.*, t2.price"

        if not right_table:
            raise ValueError("DuckDBJoinOperator requires 'right_table' parameter.")

        left_full = f"{context.schema_name}.{table_name}"
        right_full = f"{context.schema_name}.{right_table}"

        # Build ON condition
        if isinstance(on_keys, list):
            on_clause = " AND ".join([f't1."{k}" = t2."{k}"' for k in on_keys])
        elif isinstance(on_keys, dict):
            on_clause = " AND ".join([f't1."{lk}" = t2."{rk}"' for lk, rk in on_keys.items()])
        else:
            raise ValueError("Parameter 'on' must be a list of column names or a key-mapping dictionary.")

        query = f"""
            CREATE OR REPLACE TABLE {left_full} AS
            SELECT {select_cols}
            FROM {left_full} t1
            {join_type} JOIN {right_full} t2
            ON {on_clause};
        """
        context.execute_sql(query)
        return table_name


=== FILE: ./core/engine/operators/__init__.py ===
from core.engine.operators.base import BaseOperator
from core.engine.operators.registry import OperatorRegistry

__all__ = ["BaseOperator", "OperatorRegistry"]


=== FILE: ./core/engine/filter.py ===
from typing import List
import pandas as pd

from core.common.exceptions import FilterError
from core.common.logger import log
from core.common.schemas import FilterCondition


class FilterEngine:
    """Engine for pre-call or post-fetch record filtering supporting multiple evaluation operators."""

    @staticmethod
    def apply_filters(df: pd.DataFrame, conditions: List[FilterCondition]) -> pd.DataFrame:
        """Applies a sequence of filter conditions on a Pandas DataFrame."""
        if df.empty or not conditions:
            return df

        filtered_df = df.copy()

        try:
            for cond in conditions:
                field = cond.field
                op = cond.operator.upper()
                val = cond.value

                if field not in filtered_df.columns:
                    log.warning(f"Filter field '{field}' not found in DataFrame columns. Skipping rule.")
                    continue

                col_series = filtered_df[field]

                # Automatic numeric casting for arithmetic comparison operators
                if op in [">", "<", ">=", "<="]:
                    try:
                        col_series = pd.to_numeric(col_series)
                        val = float(val) if not isinstance(val, (int, float)) else val
                    except (ValueError, TypeError):
                        pass

                if op in ["==", "="]:
                    filtered_df = filtered_df[col_series.astype(str) == str(val)]
                elif op in ["!=", "<>"]:
                    filtered_df = filtered_df[col_series.astype(str) != str(val)]
                elif op == ">":
                    filtered_df = filtered_df[col_series > val]
                elif op == "<":
                    filtered_df = filtered_df[col_series < val]
                elif op == ">=":
                    filtered_df = filtered_df[col_series >= val]
                elif op == "<=":
                    filtered_df = filtered_df[col_series <= val]
                elif op == "IN":
                    val_list = val if isinstance(val, list) else [val]
                    val_str_list = [str(v) for v in val_list]
                    filtered_df = filtered_df[col_series.astype(str).isin(val_str_list)]
                elif op == "NOT IN":
                    val_list = val if isinstance(val, list) else [val]
                    val_str_list = [str(v) for v in val_list]
                    filtered_df = filtered_df[~col_series.astype(str).isin(val_str_list)]
                elif op == "CONTAINS":
                    filtered_df = filtered_df[
                        col_series.astype(str).str.contains(str(val), na=False)
                    ]
                else:
                    raise FilterError(f"Unsupported filter operator: {op}")

            return filtered_df

        except Exception as e:
            raise FilterError(f"FilterEngine execution error: {str(e)}")


=== FILE: ./core/engine/transformer.py ===
from typing import List  # <--- Bổ sung dòng này để định nghĩa kiểu List
from core.common.logger import log
from core.common.schemas import TransformRule
from core.engine.operators.registry import OperatorRegistry
from core.storage.context import PipelineContext

# Import all operator modules to register decorators automatically
import core.engine.operators.duckdb.aggregate
import core.engine.operators.duckdb.cleaning
import core.engine.operators.duckdb.enrichment
import core.engine.operators.duckdb.join
import core.engine.operators.duckdb.reshape
import core.engine.operators.python.custom_script


class DataTransformer:
    """Dispatches and executes sequential data transformation operators against PipelineContext."""

    @staticmethod
    def transform(table_name: str, rules: List[TransformRule], context: PipelineContext) -> str:
        if not rules:
            return table_name

        current_table = table_name

        for rule in rules:
            log.info(f"Applying transformation operator [{rule.operator}] on table '{current_table}'")
            operator_inst = OperatorRegistry.get(rule.operator)
            current_table = operator_inst.execute(
                table_name=current_table,
                params=rule.params,
                context=context
            )

        return current_table


=== FILE: ./core/registry/workflow_registry.py ===
from pathlib import Path
from typing import Dict, List, Optional
from config.settings import settings
from core.common.exceptions import WorkflowValidationError
from core.common.logger import log
from core.common.schemas import WorkflowConfig
from core.registry.validator import WorkflowValidator


class WorkflowRegistry:
    """Registry managing workflow definitions by dynamically scanning JSON files in workflows directory."""

    def __init__(self, workflows_dir: Optional[Path] = None):
        self.workflows_dir = workflows_dir or settings.WORKFLOWS_DIR
        self._registry: Dict[str, WorkflowConfig] = {}
        self._category_map: Dict[str, List[str]] = {}
        self._scan_and_load_workflows()

    def _scan_and_load_workflows(self) -> None:
        """Recursively scans the workflows directory for any *.json files and validates them."""
        self._registry.clear()
        self._category_map.clear()
        
        if not self.workflows_dir.exists():
            log.warning(f"Workflows directory does not exist: {self.workflows_dir}")
            return

        json_files = list(self.workflows_dir.glob("**/*.json"))
        
        for file_path in json_files:
            if file_path.name == "catalog.json":
                continue
                
            try:
                wf_config = WorkflowValidator.validate_file(str(file_path))
                
                # Categorize based on relative folder path
                relative_path = file_path.relative_to(self.workflows_dir)
                category = relative_path.parent.as_posix()
                if category == ".":
                    category = "General / Root"

                if category not in self._category_map:
                    self._category_map[category] = []
                self._category_map[category].append(wf_config.workflow_id)

                self._registry[wf_config.workflow_id] = wf_config
                log.debug(f"Loaded workflow [{wf_config.workflow_id}] from {file_path}")

            except WorkflowValidationError as e:
                log.error(f"Skipping invalid workflow file {file_path}: {str(e)}")

        log.info(f"Successfully loaded {len(self._registry)} workflows directly from JSON files.")

    def get_workflow(self, workflow_id: str) -> WorkflowConfig:
        """Retrieves a validated WorkflowConfig by workflow_id."""
        if workflow_id not in self._registry:
            self._scan_and_load_workflows()
            
        if workflow_id not in self._registry:
            raise WorkflowValidationError(f"Workflow [{workflow_id}] not found in workflows directory.")
        
        return self._registry[workflow_id]

    def list_workflows(self) -> List[str]:
        """Returns a flat list of all registered workflow IDs."""
        self._scan_and_load_workflows()
        return list(self._registry.keys())

    def list_workflows_grouped(self) -> Dict[str, List[str]]:
        """Returns registered workflows grouped by their relative folder paths."""
        self._scan_and_load_workflows()
        return self._category_map


=== FILE: ./core/registry/validator.py ===
import json
from typing import Any, Dict
from core.common.exceptions import WorkflowValidationError
from core.common.logger import log
from core.common.schemas import WorkflowConfig


class WorkflowValidator:
    """Validates pipeline JSON dictionaries or files against Pydantic schema contracts."""

    @staticmethod
    def validate_dict(config_dict: Dict[str, Any]) -> WorkflowConfig:
        """Validates a raw dictionary and parses it into a typed WorkflowConfig model."""
        try:
            workflow_config = WorkflowConfig(**config_dict)
            
            # Semantic checks: ensure step_ids are unique within the workflow
            step_ids = [step.step_id for step in workflow_config.steps]
            if len(step_ids) != len(set(step_ids)):
                raise WorkflowValidationError("Duplicate step_id values detected in workflow steps.")

            log.debug(f"Workflow '{workflow_config.workflow_id}' successfully validated.")
            return workflow_config

        except WorkflowValidationError:
            raise
        except Exception as e:
            raise WorkflowValidationError(f"Workflow validation failure: {str(e)}")

    @classmethod
    def validate_file(cls, file_path: str) -> WorkflowConfig:
        """Loads a JSON file and validates its contents."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.validate_dict(data)
        except json.JSONDecodeError as jde:
            raise WorkflowValidationError(f"Invalid JSON format in workflow file [{file_path}]: {str(jde)}")
        except Exception as e:
            raise WorkflowValidationError(f"Failed to load workflow file [{file_path}]: {str(e)}")


=== FILE: ./core/__init__.py ===



=== FILE: ./app.py ===
import streamlit as st

from core.engine.runner import PipelineRunner
from core.registry.workflow_registry import WorkflowRegistry
from ui.components import (
    render_converter_widget,
    render_dynamic_inputs,
    render_duckdb_explorer_widget,
    render_step_outputs_and_audit,
    render_workflow_editor_widget,
    render_workflow_flow,
)

# Streamlit Page Setup
st.set_page_config(page_title="OmniETL Studio", page_icon="🚀", layout="wide")


@st.cache_resource
def get_registry():
    return WorkflowRegistry()


registry = get_registry()

# ==========================================
# 🛠️ SIDEBAR: WORKFLOW MANAGEMENT
# ==========================================
st.sidebar.title("🚀 OmniETL Studio")
st.sidebar.caption("Declarative Multi-Protocol Engine")
st.sidebar.markdown("---")

col_sb_ref, col_sb_cnt = st.sidebar.columns([0.4, 0.6])
with col_sb_ref:
    if st.button("🔄 Refresh", use_container_width=True):
        registry._scan_and_load_workflows()
        st.session_state.pop("last_context", None)
        st.rerun()

all_grouped_wf = registry.list_workflows_grouped()
total_wf_count = sum(len(v) for v in all_grouped_wf.values())

with col_sb_cnt:
    st.markdown(
        f"<div style='text-align: right; padding-top: 5px;'><b>{total_wf_count}</b> Workflows</div>", 
        unsafe_allow_html=True
    )

search_term = st.sidebar.text_input("🔍 Search Workflow:", placeholder="Type ID or keyword...").strip().lower()

filtered_grouped_wf = {}
for cat, wf_list in all_grouped_wf.items():
    matched = [wf_id for wf_id in wf_list if search_term in wf_id.lower()]
    if matched:
        filtered_grouped_wf[cat] = matched

if not filtered_grouped_wf:
    st.sidebar.warning("No matching workflows found.")
    st.stop()

categories = list(filtered_grouped_wf.keys())
selected_category = st.sidebar.selectbox("📁 Select Category / Folder:", options=categories)

available_wf_in_cat = filtered_grouped_wf[selected_category]
selected_wf_id = st.sidebar.selectbox("📄 Select Workflow Pipeline:", options=available_wf_in_cat)

workflow_config = registry.get_workflow(selected_wf_id)

st.sidebar.markdown("---")
st.sidebar.caption(f"**Active ID:** `{workflow_config.workflow_id}`")
st.sidebar.caption(f"**Steps Count:** {len(workflow_config.steps)}")

# ==========================================
# 📋 MAIN APPLICATION NAVIGATION TABS
# ==========================================
tab_pipeline, tab_editor, tab_duckdb, tab_converter = st.tabs([
    "📋 Pipeline Execution", 
    "🛠️ Workflow Studio (JSON Editor)", 
    "🦆 DuckDB Data Explorer", 
    "🔄 Nexacro XML Utility"
])

# ------------------------------------------
# TAB 1: PIPELINE EXECUTION CONSOLE
# ------------------------------------------
with tab_pipeline:
    top_col1, top_col2 = st.columns([0.7, 0.3])

    with top_col1:
        st.title("⚡ Execution Console")
        st.caption(f"Category: `{selected_category}` | Active Pipeline: **{workflow_config.workflow_id}**")

    with top_col2:
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        run_btn = st.button("▶ EXECUTE FULL PIPELINE", type="primary", use_container_width=True)

    st.markdown("---")

    render_workflow_flow(workflow_config)
    global_input = render_dynamic_inputs(workflow_config.inputs)

    if run_btn:
        with st.spinner(f"Executing pipeline '{selected_wf_id}'..."):
            try:
                runner = PipelineRunner(workflow=workflow_config)
                context = runner.run(global_input=global_input)

                st.success("🎉 Pipeline execution completed successfully!")

                st.session_state["last_context"] = context
                st.session_state["last_wf_config"] = workflow_config
                st.session_state["last_global_input"] = global_input

            except Exception as e:
                st.error(f"❌ Pipeline Execution Failure: {str(e)}")

    if "last_context" in st.session_state and st.session_state.get("last_wf_config") == workflow_config:
        render_step_outputs_and_audit(st.session_state["last_context"], workflow_config)

# ------------------------------------------
# TAB 2: WORKFLOW JSON EDITOR & VALIDATOR
# ------------------------------------------
with tab_editor:
    render_workflow_editor_widget(registry)

# ------------------------------------------
# TAB 3: DUCKDB DATA EXPLORER & SQL LAB
# ------------------------------------------
with tab_duckdb:
    render_duckdb_explorer_widget()

# ------------------------------------------
# TAB 4: NEXACRO XML CONVERTER TOOL
# ------------------------------------------
with tab_converter:
    render_converter_widget()


=== FILE: ./ui/components/converter_widget.py ===
import streamlit as st
from drivers.nexacro import NexacroDriver


def render_converter_widget():
    """Renders the utility tab for converting and inspecting Nexacro XML payloads."""
    st.subheader("🔄 Nexacro XML Payload Converter & Inspector")
    
    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Root xmlns="http://tobesoft.com">
    <Dataset id="ds_sample">
        <ColumnInfo>
            <Column id="code" type="STRING"/>
            <Column id="score" type="INT"/>
        </ColumnInfo>
        <Rows>
            <Row><Col id="code">STU_01</Col><Col id="score">90</Col></Row>
            <Row><Col id="code">STU_02</Col><Col id="score">85</Col></Row>
        </Rows>
    </Dataset>
</Root>"""

    xml_input = st.text_area("Paste Raw Nexacro XML Payload:", value=sample_xml, height=220)

    if st.button("Parse XML Payload", type="secondary"):
        try:
            df = NexacroDriver.parse_xml_response(xml_input)
            st.success(f"Successfully parsed {len(df)} records!")
            
            tab_df, tab_json = st.tabs(["📊 DataFrame View", "📜 JSON View"])
            with tab_df:
                st.dataframe(df, use_container_width=True)
            with tab_json:
                st.json(df.to_dict(orient="records"))

        except Exception as e:
            st.error(f"Failed to parse XML payload: {str(e)}")


=== FILE: ./ui/components/input_builder.py ===
from typing import Any, Dict, List
import pandas as pd
import streamlit as st
from core.common.schemas import WorkflowInput


def render_dynamic_inputs(inputs_config: List[WorkflowInput]) -> Dict[str, Any]:
    """Renders dynamic user input controls on the main body page based on WorkflowInput definitions."""
    user_inputs: Dict[str, Any] = {}

    if not inputs_config:
        st.info("ℹ️ Kịch bản này không yêu cầu tham số đầu vào.")
        return user_inputs

    st.markdown("### ⚙️ Workflow Input Parameters")
    cols = st.columns(min(len(inputs_config), 2))

    for idx, inp in enumerate(inputs_config):
        col = cols[idx % len(cols)]
        label = inp.label or inp.name
        help_text = inp.description
        input_type = (inp.type or "string").lower()

        with col:
            if input_type in ["table", "grid", "array"]:
                st.markdown(f"**{label}**")
                if help_text:
                    st.caption(help_text)

                default_data = inp.default if isinstance(inp.default, list) else []
                df_init = pd.DataFrame(default_data)

                if df_init.empty and inp.columns:
                    col_names = [c.name or c.field for c in inp.columns if c.name or c.field]
                    df_init = pd.DataFrame(columns=col_names)

                edited_df = st.data_editor(
                    df_init,
                    num_rows="dynamic",
                    use_container_width=True,
                    key=f"input_table_{inp.name}"
                )
                user_inputs[inp.name] = edited_df.to_dict(orient="records")

            elif input_type in ["string", "text"]:
                val = st.text_input(
                    label=label,
                    value=str(inp.default if inp.default is not None else ""),
                    help=help_text,
                    key=f"input_{inp.name}"
                )
                user_inputs[inp.name] = val

            elif input_type in ["number", "int", "float"]:
                default_val = float(inp.default) if inp.default is not None else 0.0
                val = st.number_input(
                    label=label,
                    value=default_val,
                    help=help_text,
                    key=f"input_{inp.name}"
                )
                user_inputs[inp.name] = val

            elif input_type in ["select", "dropdown"] and inp.options:
                default_idx = 0
                if inp.default in inp.options:
                    default_idx = inp.options.index(inp.default)
                val = st.selectbox(
                    label=label,
                    options=inp.options,
                    index=default_idx,
                    help=help_text,
                    key=f"input_{inp.name}"
                )
                user_inputs[inp.name] = val

            else:
                val = st.text_input(
                    label=label,
                    value=str(inp.default or ""),
                    help=help_text,
                    key=f"input_{inp.name}"
                )
                user_inputs[inp.name] = val

    return user_inputs


=== FILE: ./ui/components/xml_converter.py ===
import streamlit as st
from drivers.nexacro import NexacroDriver


def render_converter_widget():
    """Renders the utility tab for converting and inspecting Nexacro XML payloads."""
    st.subheader("🔄 Nexacro XML Payload Converter & Inspector")
    
    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Root xmlns="http://tobesoft.com">
    <Dataset id="ds_sample">
        <ColumnInfo>
            <Column id="code" type="STRING"/>
            <Column id="score" type="INT"/>
        </ColumnInfo>
        <Rows>
            <Row><Col id="code">STU_01</Col><Col id="score">90</Col></Row>
            <Row><Col id="code">STU_02</Col><Col id="score">85</Col></Row>
        </Rows>
    </Dataset>
</Root>"""

    xml_input = st.text_area("Paste Raw Nexacro XML Payload:", value=sample_xml, height=220)

    if st.button("Parse XML Payload", type="secondary"):
        try:
            df = NexacroDriver.parse_xml_response(xml_input)
            st.success(f"Successfully parsed {len(df)} records!")
            
            tab_df, tab_json = st.tabs(["📊 DataFrame View", "📜 JSON View"])
            with tab_df:
                st.dataframe(df, use_container_width=True)
            with tab_json:
                st.json(df.to_dict(orient="records"))

        except Exception as e:
            st.error(f"Failed to parse XML payload: {str(e)}")


=== FILE: ./ui/components/workflow_editor.py ===
import json
from pathlib import Path
import streamlit as st

from config.settings import settings
from core.common.exceptions import WorkflowValidationError
from core.registry.validator import WorkflowValidator


def render_workflow_editor_widget(registry):
    """Visual Workflow Studio & Sample Configurator Widget (Placeholder for Future Canvas Editor)."""
    st.subheader("🛠️ Visual Workflow Studio (Sample)")
    st.caption("Mẫu giao diện cấu hình và tạo mới kịch bản Pipeline ETL trực quan.")

    sample_template = {
        "workflow_id": "sample_inventory_pipeline",
        "description": "Pipeline mẫu tra cứu và tổng hợp tồn kho",
        "inputs": [
            {"name": "category", "label": "Danh Mục Sản Phẩm", "type": "string", "default": "Thời trang"},
            {"name": "status", "label": "Trạng Thái Kho", "type": "string", "default": "IN_STOCK"}
        ],
        "steps": [
            {
                "step_id": "step1_search_products",
                "driver": "nexacro",
                "mode": "batch",
                "method": "POST",
                "endpoint": "http://127.0.0.1:8000/api/nexacro/xml/products/search-list",
                "variables": {
                    "ds_search": {
                        "type": "dataset",
                        "columns": [
                            {"field": "global_input.category", "alias": "category"},
                            {"field": "global_input.status", "alias": "status"}
                        ]
                    }
                },
                "transformations": [],
                "output_dataset": "ds_step1_raw_search",
                "output_config": {
                    "display_title": "Bảng Kết Quả Tìm Kiếm",
                    "columns": [
                        {"field": "product_id", "title": "Mã Sản Phẩm", "visible": True}
                    ]
                }
            }
        ]
    }

    st.markdown("---")

    col_id, col_desc = st.columns([0.4, 0.6])
    with col_id:
        wf_id = st.text_input("Workflow ID:", value=sample_template["workflow_id"], key="editor_wf_id")
    with col_desc:
        wf_desc = st.text_input("Description:", value=sample_template["description"], key="editor_wf_desc")

    st.markdown("##### 📜 Cấu hình Workflow JSON (Schema Inspector)")
    
    json_text = st.text_area(
        "Workflow Configuration JSON:", 
        value=json.dumps(sample_template, indent=2, ensure_ascii=False),
        height=320,
        key="editor_json_area"
    )

    col_val, col_save = st.columns(2)

    with col_val:
        if st.button("🔍 Validate JSON Schema", use_container_width=True):
            try:
                parsed_dict = json.loads(json_text)
                WorkflowValidator.validate_dict(parsed_dict)
                st.success("✅ Workflow Schema hoàn toàn hợp lệ (100% Valid)!")
            except Exception as e:
                st.error(f"❌ Lỗi Validate Schema: {str(e)}")

    with col_save:
        if st.button("💾 Save Workflow JSON", type="primary", use_container_width=True):
            try:
                parsed_dict = json.loads(json_text)
                validated_config = WorkflowValidator.validate_dict(parsed_dict)
                
                target_file = Path(settings.WORKFLOWS_DIR) / f"{wf_id}.json"
                target_file.parent.mkdir(parents=True, exist_ok=True)

                with open(target_file, "w", encoding="utf-8") as f:
                    json.dump(parsed_dict, f, indent=2, ensure_ascii=False)

                st.success(f"🎉 Đã lưu kịch bản `{validated_config.workflow_id}` thành công vào `{target_file}`!")
                if hasattr(registry, "_scan_and_load_workflows"):
                    registry._scan_and_load_workflows()
            except Exception as e:
                st.error(f"❌ Lỗi khi lưu kịch bản: {str(e)}")


=== FILE: ./ui/components/duckdb_explorer.py ===
import streamlit as st
from core.storage.context import PipelineContext


def render_duckdb_explorer_widget():
    """Renders the DuckDB Inspector with structured table categories and SQL Query Lab."""
    st.subheader("🦆 DuckDB Data Explorer & SQL Query Lab")
    st.caption("Inspect persistent historical storage and step execution outputs.")

    # 1. Connect to DuckDB storage
    context = st.session_state.get("last_context") or PipelineContext(pipeline_id="explorer_session")

    col_info, col_clean = st.columns([0.7, 0.3])
    with col_info:
        st.markdown(f"**Persistent Storage Schema:** `{context.shared_schema}`")
        if context.schema_name and context.schema_name != "ns_explorer_session":
            st.caption(f"Active Execution Schema: `{context.schema_name}`")

    with col_clean:
        if st.button("🧹 Clean Temp Schemas", use_container_width=True):
            context.clean_temporary_schemas()
            st.success("Successfully cleaned temporary execution schemas!")
            st.rerun()

    # 2. Query and categorize tables (Exclude internal _raw tables)
    try:
        tables_df = context.execute_sql(f"""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_schema IN ('{context.shared_schema}', '{context.schema_name}')
              AND table_name NOT LIKE '%_raw'
            ORDER BY table_schema DESC, table_name ASC;
        """)
        
        shared_tables = []
        step_tables = []
        table_mapping = {}

        if not tables_df.empty:
            for _, r in tables_df.iterrows():
                full_name = f"{r['table_schema']}.{r['table_name']}"
                if r['table_schema'] == context.shared_schema:
                    display_label = f"📁 [PERSISTENT HISTORY] {r['table_name']}"
                    shared_tables.append(display_label)
                else:
                    display_label = f"⚡ [STEP OUTPUT] {r['table_name']}"
                    step_tables.append(display_label)
                
                table_mapping[display_label] = full_name

        all_options = shared_tables + step_tables
    except Exception:
        all_options = []
        table_mapping = {}

    tab_tables, tab_sql = st.tabs(["📋 Registered Tables Viewer", "💻 SQL Console Lab"])

    # TAB 1: BROWSE TABLES
    with tab_tables:
        if all_options:
            selected_label = st.selectbox("Select DuckDB Table to View:", options=all_options)
            selected_full_table = table_mapping.get(selected_label)
            
            if selected_full_table:
                count_df = context.execute_sql(f"SELECT COUNT(*) AS total_rows FROM {selected_full_table};")
                total_rows = count_df["total_rows"].iloc[0] if not count_df.empty else 0

                c_m1, c_m2 = st.columns(2)
                c_m1.metric("Total Rows", f"{total_rows:,}")
                
                df_preview = context.execute_sql(f"SELECT * FROM {selected_full_table} LIMIT 100;")
                c_m2.metric("Total Columns", len(df_preview.columns))

                st.dataframe(df_preview, use_container_width=True)
                if total_rows > 100:
                    st.caption("*(Displaying top 100 rows)*")

                st.download_button(
                    label=f"📥 Download Full CSV [{selected_full_table}.csv]",
                    data=context.execute_sql(f"SELECT * FROM {selected_full_table};").to_csv(index=False),
                    file_name=f"{selected_full_table.replace('.', '_')}.csv",
                    mime="text/csv",
                    key=f"dl_duckdb_{selected_full_table}"
                )
        else:
            st.info("No tables currently present in DuckDB storage.")

    # TAB 2: SQL CONSOLE LAB
    with tab_sql:
        st.markdown("##### Run Ad-hoc SQL Query against DuckDB Engine")
        first_table = list(table_mapping.values())[0] if table_mapping else "shared_storage.ds_historical_products_v2"
        sample_sql = f"SELECT * FROM {first_table} LIMIT 10;"
        
        sql_input = st.text_area("SQL Query Statement:", value=sample_sql, height=120)

        if st.button("▶ Run SQL Query", type="primary"):
            try:
                res_df = context.execute_sql(sql_input)
                st.success(f"Execution successful! Returned {len(res_df)} rows.")
                st.dataframe(res_df, use_container_width=True)
            except Exception as e:
                st.error(f"❌ SQL Execution Error: {str(e)}")


=== FILE: ./ui/components/execution_runner.py ===
from typing import Any, Dict
import pandas as pd
import streamlit as st

from core.common.schemas import WorkflowConfig
from core.engine.resolver import VariableResolver
from core.storage.context import PipelineContext
from drivers.nexacro import NexacroDriver


def render_step_output(step_config: Dict[str, Any], df_result: pd.DataFrame):
    """Renders DataFrame results based on step output_config."""
    output_config = step_config.get("output_config", {})
    display_title = output_config.get("display_title", f"Output: {step_config.get('step_id')}")
    columns_config = output_config.get("columns", [])

    st.subheader(display_title)

    if df_result is None or df_result.empty:
        st.warning("Không có dữ liệu trả về.")
        return

    display_df = df_result.copy()

    if columns_config:
        visible_cols = [
            c["field"] for c in columns_config 
            if c.get("visible", True) and c.get("field") in display_df.columns
        ]
        if visible_cols:
            display_df = display_df[visible_cols]

        rename_map = {
            c["field"]: c["title"] 
            for c in columns_config 
            if "title" in c and c.get("field") in display_df.columns
        }
        display_df = display_df.rename(columns=rename_map)

    st.dataframe(display_df, use_container_width=True)


def render_step_outputs_and_audit(context: PipelineContext, workflow_config: WorkflowConfig):
    """Render output tables and dynamic audit payload logs (XML & Structured JSON) separately for EVERY step."""
    st.markdown("---")
    st.subheader("📊 EXECUTION RESULTS BY STEP")

    global_input = st.session_state.get("last_global_input", {})
    global_context = {"global_input": global_input}

    for idx, step in enumerate(workflow_config.steps, 1):
        with st.container(border=True):
            c_title, c_dl = st.columns([0.75, 0.25])
            
            with c_title:
                st.markdown(
                    f"#### Step {idx}: `{step.step_id}` "
                    f"&nbsp;<span style='font-size:12px; color:gray;'>({step.driver.upper()} | {step.method} | {step.mode})</span>",
                    unsafe_allow_html=True
                )
            
            try:
                df_step = context.get_dataframe(step.output_dataset)
                rows_cnt = len(df_step)
            except Exception:
                df_step = pd.DataFrame()
                rows_cnt = 0

            with c_dl:
                if not df_step.empty:
                    st.download_button(
                        label=f"📥 Export CSV ({rows_cnt} rows)",
                        data=df_step.to_csv(index=False),
                        file_name=f"{step.step_id}_{step.output_dataset}.csv",
                        mime="text/csv",
                        key=f"btn_dl_step_{step.step_id}_{idx}",
                        use_container_width=True
                    )

            tab_data, tab_audit_xml, tab_audit_json = st.tabs([
                "📋 Data Table Output", 
                "📜 XML Payload Sent", 
                "🔗 JSON Payload Representation"
            ])

            # Resolve variables dynamically against context
            try:
                resolved_vars = VariableResolver.resolve(step.variables or {}, context, global_context)
            except Exception:
                resolved_vars = {"parameters": {}, "datasets": {}}

            # 1. TAB OUTPUT DATA TABLE
            with tab_data:
                render_step_output(step.model_dump(), df_step)

            # 2. TAB AUDIT XML PAYLOAD
            with tab_audit_xml:
                st.caption("**Nexacro XML Protocol Payload (Sent to Endpoint):**")
                if step.driver == "nexacro":
                    try:
                        actual_xml = NexacroDriver.build_xml_payload(resolved_vars)
                        st.code(actual_xml, language="xml")
                    except Exception as e:
                        st.error(f"Failed to build XML payload: {str(e)}")
                else:
                    st.info(f"Driver `{step.driver}` does not generate XML payloads.")

            # 3. TAB AUDIT STRUCTURED JSON PAYLOAD
            with tab_audit_json:
                st.caption("**Structured Variable Resolution:**")
                st.json({
                    "step_id": step.step_id,
                    "driver": step.driver,
                    "method": step.method,
                    "endpoint": step.endpoint or "N/A (Pure Transformation)",
                    "resolved_variables": resolved_vars
                })


=== FILE: ./ui/components/workflow_flow.py ===
import streamlit as st
from core.common.schemas import WorkflowConfig


def render_workflow_flow(workflow_config: WorkflowConfig):
    """Renders a clean and compact step-by-step pipeline execution visual flow structure."""
    with st.expander(f"📌 Pipeline Steps Diagram ({len(workflow_config.steps)} Steps Configured)", expanded=False):
        st.caption(f"**Catalog ID:** `{workflow_config.workflow_id}` | **Description:** {workflow_config.description or 'N/A'}")
        
        cols = st.columns(min(len(workflow_config.steps), 3))
        for idx, step in enumerate(workflow_config.steps):
            col = cols[idx % len(cols)]
            with col:
                with st.container(border=True):
                    st.markdown(f"**Step {idx+1}:** `{step.step_id}`")
                    st.caption(f"**Method/Driver:** `{step.method}` / `{step.driver}`")
                    st.caption(f"**Output Table:** `{step.output_dataset}`")
                    if step.transformations:
                        ops = ", ".join([f"`{t.operator}`" for t in step.transformations])
                        st.caption(f"**Transforms:** {ops}")


=== FILE: ./ui/components/__init__.py ===
from ui.components.converter_widget import render_converter_widget
from ui.components.duckdb_explorer import render_duckdb_explorer_widget
from ui.components.execution_runner import (
    render_step_output,
    render_step_outputs_and_audit,
)
from ui.components.input_builder import render_dynamic_inputs
from ui.components.workflow_editor import render_workflow_editor_widget
from ui.components.workflow_flow import render_workflow_flow

__all__ = [
    "render_step_outputs_and_audit",
    "render_step_output",
    "render_dynamic_inputs",
    "render_workflow_flow",
    "render_duckdb_explorer_widget",
    "render_converter_widget",
    "render_workflow_editor_widget",
]


=== FILE: ./ui/__init__.py ===



=== FILE: ./all_code.py ===



=== FILE: ./mock-server/test_xml_api.py ===
import time
from multiprocessing import Process
import pytest
import requests
import uvicorn

# Đồng bộ cổng port giữa BASE_URL và uvicorn runner
PORT = 8001
BASE_URL = f"http://127.0.0.1:{PORT}"


def run_server():
    """Hàm khởi chạy server Uvicorn thực tế trên cổng 8001"""
    uvicorn.run("main:app", host="127.0.0.1", port=PORT, log_level="error")


@pytest.fixture(scope="module", autouse=True)
def setup_server():
    """Fixture tự động bật server trước khi test và tắt server sau khi test xong"""
    server_process = Process(target=run_server, daemon=True)
    server_process.start()

    # Chờ server khởi động
    for _ in range(10):
        try:
            res = requests.get(f"{BASE_URL}/docs")
            if res.status_code == 200:
                break
        except requests.exceptions.ConnectionError:
            time.sleep(0.5)

    yield

    # Tắt server ngầm sau khi hoàn thành test
    server_process.terminate()
    server_process.join()


# ==========================================
# TEST CASES GỌI HTTP API TRỰC TIẾP
# ==========================================

def test_search_by_product_id_list_xml():
    """
    Test API Tra cứu danh sách theo Dataset 2 (ds_id_list chứa nhiều product_id)
    """
    xml_payload = """<?xml version="1.0" encoding="UTF-8"?>
    <Root>
      <Dataset id="ds_search">
        <ColumnInfo><Column id="category" type="STRING" size="255"/></ColumnInfo>
        <Rows><Row><Col id="category"></Col></Row></Rows>
      </Dataset>
      <Dataset id="ds_id_list">
        <ColumnInfo><Column id="product_id" type="STRING" size="255"/></ColumnInfo>
        <Rows>
          <Row><Col id="product_id">SP-001</Col></Row>
          <Row><Col id="product_id">SP-003</Col></Row>
        </Rows>
      </Dataset>
    </Root>"""

    headers = {"Content-Type": "application/xml"}
    response = requests.post(f"{BASE_URL}/api/nexacro/xml/products/search-list", data=xml_payload, headers=headers)

    assert response.status_code == 200
    assert 'id="ErrorCode">0</Parameter>' in response.text
    assert '<Col id="product_id">SP-001</Col>' in response.text
    assert '<Col id="product_id">SP-003</Col>' in response.text
    assert '<Col id="product_id">SP-002</Col>' not in response.text


def test_get_product_detail_xml_http():
    """
    Test HTTP API lấy chi tiết sản phẩm -> Trả về 3 Datasets
    """
    xml_payload = """<?xml version="1.0" encoding="UTF-8"?>
    <Root>
      <Dataset id="ds_condition">
        <ColumnInfo><Column id="product_id" type="STRING" size="255"/></ColumnInfo>
        <Rows><Row><Col id="product_id">SP-001</Col></Row></Rows>
      </Dataset>
    </Root>"""

    headers = {"Content-Type": "application/xml"}
    response = requests.post(f"{BASE_URL}/api/nexacro/xml/products/detail", data=xml_payload, headers=headers)

    assert response.status_code == 200
    assert 'id="ErrorCode">0</Parameter>' in response.text
    assert '<Dataset id="ds_master">' in response.text
    assert '<Dataset id="ds_inventory">' in response.text
    assert '<Dataset id="ds_pricing">' in response.text


def test_get_product_detail_not_found_http():
    """
    Test HTTP API với sản phẩm không tồn tại (-404)
    """
    xml_payload = """<?xml version="1.0" encoding="UTF-8"?>
    <Root>
      <Dataset id="ds_condition">
        <ColumnInfo><Column id="product_id" type="STRING" size="255"/></ColumnInfo>
        <Rows><Row><Col id="product_id">SP-NOT-EXIST</Col></Row></Rows>
      </Dataset>
    </Root>"""

    headers = {"Content-Type": "application/xml"}
    response = requests.post(f"{BASE_URL}/api/nexacro/xml/products/detail", data=xml_payload, headers=headers)

    assert response.status_code == 200
    assert 'id="ErrorCode">-404</Parameter>' in response.text


if __name__ == "__main__":
    pytest.main(["-v", __file__])


=== FILE: ./mock-server/main.py ===
import json
import xmltodict
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

app = FastAPI(
    title="Nexacro Multi-Format API Simulation",
    description="Backend mô phỏng các giao tiếp Dataset (JSON & XML) cho Nexacro",
    version="2.0.0"
)

def load_json_data() -> List[Dict[str, Any]]:
    try:
        with open("products_db.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def build_nexacro_xml_response(error_code: int, error_msg: str, datasets: Dict[str, List[Dict[str, Any]]]) -> str:
    xml_out = '<?xml version="1.0" encoding="UTF-8"?>\n<Root>\n'
    xml_out += f'  <Parameters>\n    <Parameter id="ErrorCode">{error_code}</Parameter>\n    <Parameter id="ErrorMsg">{error_msg}</Parameter>\n  </Parameters>\n'
    
    for ds_name, rows in datasets.items():
        xml_out += f'  <Dataset id="{ds_name}">\n'
        if rows:
            xml_out += '    <ColumnInfo>\n'
            for key in rows[0].keys():
                xml_out += f'      <Column id="{key}" type="STRING" size="255"/>\n'
            xml_out += '    </ColumnInfo>\n'
            xml_out += '    <Rows>\n'
            for row in rows:
                xml_out += '      <Row>\n'
                for k, v in row.items():
                    val_str = "" if v is None else str(v)
                    xml_out += f'        <Col id="{k}">{val_str}</Col>\n'
                xml_out += '      </Row>\n'
            xml_out += '    </Rows>\n'
        xml_out += '  </Dataset>\n'
    
    xml_out += '</Root>'
    return xml_out


# ==========================================
# XML ENDPOINTS
# ==========================================

@app.post("/api/nexacro/xml/products/search-list")
async def search_product_list_xml(request: Request):
    """
    [XML] Tra danh sách sản phẩm:
    - Dataset 1 (ds_search): Điều kiện lọc chung (category, status)
    - Dataset 2 (ds_id_list): Danh sách các product_id cần tra cứu
    """
    body_bytes = await request.body()
    category_filter = ""
    status_filter = ""
    target_product_ids = []
    
    try:
        parsed_xml = xmltodict.parse(body_bytes)
        root = parsed_xml.get('Root', {})
        datasets = root.get('Dataset', [])
        
        if isinstance(datasets, dict):
            datasets = [datasets]
            
        for ds in datasets:
            ds_id = ds.get('@id')
            
            # 1. Xử lý Dataset 1: Điều kiện lọc chung
            if ds_id == 'ds_search':
                rows = ds.get('Rows', {}).get('Row', [])
                if isinstance(rows, dict): rows = [rows]
                for row in rows:
                    cols = row.get('Col', [])
                    if isinstance(cols, dict): cols = [cols]
                    for col in cols:
                        if col.get('@id') == 'category': category_filter = col.get('#text', '')
                        if col.get('@id') == 'status': status_filter = col.get('#text', '')
            
            # 2. Xử lý Dataset 2: Danh sách product_id (Đã sửa ép kiểu list cho Row)
            elif ds_id == 'ds_id_list':
                rows = ds.get('Rows', {}).get('Row', [])
                if isinstance(rows, dict): rows = [rows]  # Đảm bảo luôn là danh sách các Row
                
                for row in rows:
                    cols = row.get('Col', [])
                    if isinstance(cols, dict): cols = [cols]  # Đảm bảo luôn là danh sách các Col
                    
                    for col in cols:
                        if col.get('@id') == 'product_id' and col.get('#text'):
                            target_product_ids.append(col.get('#text'))
                            
    except Exception as e:
        pass

    raw_data = load_json_data()
    filtered = []
    for item in raw_data:
        match_cat = not category_filter or item.get("category") == category_filter
        match_status = not status_filter or item.get("inventory", {}).get("status") == status_filter
        
        # Kiểm tra điều kiện danh sách product_id
        match_ids = not target_product_ids or item.get("product_id") in target_product_ids
        
        if match_cat and match_status and match_ids:
            filtered.append({
                "product_id": item["product_id"],
                "product_name": item["product_name"],
                "sku": item["sku"],
                "category": item["category"],
                "stock_quantity": item["inventory"]["stock_quantity"],
                "sale_price": item["pricing"]["sale_price"]
            })

    xml_response = build_nexacro_xml_response(0, "SUCCESS", {"ds_result_list": filtered})
    return Response(content=xml_response, media_type="application/xml")

@app.post("/api/nexacro/xml/products/detail")
async def get_product_detail_xml(request: Request):
    """[XML] Tra chi tiết: Input Payload XML 1 Dataset -> Output XML 3 Datasets"""
    body_bytes = await request.body()
    product_id_search = ""
    
    try:
        parsed_xml = xmltodict.parse(body_bytes)
        root = parsed_xml.get('Root', {})
        datasets = root.get('Dataset', {})
        
        if isinstance(datasets, list):
            ds_target = next((ds for ds in datasets if ds.get('@id') == 'ds_condition'), {})
        else:
            ds_target = datasets if datasets.get('@id') == 'ds_condition' else {}

        cols = ds_target.get('Rows', {}).get('Row', {}).get('Col', [])
        if isinstance(cols, list):
            for col in cols:
                if col.get('@id') == 'product_id':
                    product_id_search = col.get('#text', '')
        elif isinstance(cols, dict) and cols.get('@id') == 'product_id':
            product_id_search = cols.get('#text', '')
    except Exception:
        xml_err = build_nexacro_xml_response(-1, "Invalid XML Payload", {})
        return Response(content=xml_err, media_type="application/xml")

    raw_data = load_json_data()
    found = next((item for item in raw_data if item["product_id"] == product_id_search), None)

    if not found:
        xml_err = build_nexacro_xml_response(-404, f"Product {product_id_search} Not Found", {
            "ds_master": [], "ds_inventory": [], "ds_pricing": []
        })
        return Response(content=xml_err, media_type="application/xml")

    ds_master = [{
        "product_id": found["product_id"],
        "product_name": found["product_name"],
        "sku": found["sku"],
        "category": found["category"],
        "brand": found.get("brand", "")
    }]
    ds_inventory = [{
        "product_id": found["product_id"],
        "stock_quantity": found["inventory"]["stock_quantity"],
        "reserved_quantity": found["inventory"]["reserved_quantity"],
        "available_quantity": found["inventory"]["available_quantity"],
        "status": found["inventory"]["status"]
    }]
    ds_pricing = [{
        "product_id": found["product_id"],
        "cost_price": found["pricing"]["cost_price"],
        "original_price": found["pricing"]["original_price"],
        "sale_price": found["pricing"]["sale_price"],
        "price_status": found["pricing"]["price_status"]
    }]

    xml_response = build_nexacro_xml_response(0, "SUCCESS", {
        "ds_master": ds_master,
        "ds_inventory": ds_inventory,
        "ds_pricing": ds_pricing
    })
    return Response(content=xml_response, media_type="application/xml")


=== FILE: ./drivers/base.py ===
from abc import ABC, abstractmethod
from typing import Any, Dict, Type
import pandas as pd
from core.common.exceptions import DriverError


class BaseDriver(ABC):
    """Abstract Base Class for all protocol drivers (e.g., Nexacro, REST, SQL)."""

    @abstractmethod
    def execute(self, endpoint: str, variables: Dict[str, Any], method: str = "POST") -> pd.DataFrame:
        """Executes a protocol request and returns the resulting dataset as a Pandas DataFrame."""
        pass


class DriverRegistry:
    """Central registry managing protocol driver instances."""

    _registry: Dict[str, Type[BaseDriver]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a concrete BaseDriver subclass."""
        def decorator(subclass: Type[BaseDriver]):
            cls._registry[name.lower()] = subclass
            return subclass
        return decorator

    @classmethod
    def get(cls, name: str) -> Type[BaseDriver]:
        """Retrieves a registered driver class by protocol name."""
        driver_name = name.lower()
        if driver_name not in cls._registry:
            raise DriverError(f"Driver protocol '{name}' is not registered. Available: {list(cls._registry.keys())}")
        return cls._registry[driver_name]


@DriverRegistry.register("passthrough")
@DriverRegistry.register("none")
class PassthroughDriver(BaseDriver):
    """Fallback driver for pure transformation steps requiring no network/API calls."""

    def execute(self, endpoint: str, variables: Dict[str, Any], method: str = "POST") -> pd.DataFrame:
        return pd.DataFrame()


=== FILE: ./drivers/nexacro.py ===
import xml.etree.ElementTree as ET
from typing import Any, Dict
import pandas as pd
import requests
from core.common.logger import log
from drivers.base import BaseDriver, DriverRegistry


@DriverRegistry.register("nexacro")
class NexacroDriver(BaseDriver):
    """Packs resolved variables into Nexacro XML Payload, sends HTTP request, and parses multi-dataset XML Responses."""

    @staticmethod
    def build_xml_payload(resolved_vars: Dict[str, Any]) -> str:
        root = ET.Element("Root", {"xmlns": "http://tobesoft.com"})
        
        # 1. Build Parameters
        params = resolved_vars.get("parameters", {})
        if params:
            params_node = ET.SubElement(root, "Parameters")
            for param_id, val in params.items():
                p_node = ET.SubElement(params_node, "Parameter", {"id": param_id})
                p_node.text = "" if val is None else str(val)

        # 2. Build Datasets
        datasets = resolved_vars.get("datasets", {})
        for ds_id, rows in datasets.items():
            ds_node = ET.SubElement(root, "Dataset", {"id": ds_id})
            
            if rows and isinstance(rows, list) and len(rows) > 0:
                col_info_node = ET.SubElement(ds_node, "ColumnInfo")
                sample_row = rows[0]
                for col_name in sample_row.keys():
                    ET.SubElement(col_info_node, "Column", {
                        "id": col_name,
                        "type": "STRING",
                        "size": "256"
                    })
                
                rows_node = ET.SubElement(ds_node, "Rows")
                for row_data in rows:
                    row_node = ET.SubElement(rows_node, "Row")
                    for col_id, col_val in row_data.items():
                        col_node = ET.SubElement(row_node, "Col", {"id": col_id})
                        col_node.text = "" if col_val is None else str(col_val)

        return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="utf-8").decode("utf-8")

    @staticmethod
    def parse_xml_response(xml_string: str) -> pd.DataFrame:
        if not xml_string or not xml_string.strip():
            return pd.DataFrame()

        try:
            root = ET.fromstring(xml_string)
        except Exception as e:
            log.error(f"Failed to parse Nexacro XML response: {str(e)}")
            return pd.DataFrame()

        parsed_datasets: Dict[str, pd.DataFrame] = {}

        for ds_node in root.findall("Dataset"):
            ds_id = ds_node.get("id", "ds_default")
            rows_data = []

            rows_node = ds_node.find("Rows")
            if rows_node is not None:
                for row_node in rows_node.findall("Row"):
                    row_dict = {}
                    for col_node in row_node.findall("Col"):
                        col_id = col_node.get("id")
                        if col_id:
                            row_dict[col_id] = col_node.text
                    rows_data.append(row_dict)

            parsed_datasets[ds_id] = pd.DataFrame(rows_data)

        if not parsed_datasets:
            return pd.DataFrame()

        if len(parsed_datasets) == 1:
            return list(parsed_datasets.values())[0]

        # Merge đa Dataset (ds_master, ds_inventory, ds_pricing)
        merged_df = None
        for ds_id, df in parsed_datasets.items():
            if df.empty:
                continue
            if merged_df is None:
                merged_df = df
            else:
                join_keys = [col for col in ["product_id", "id"] if col in merged_df.columns and col in df.columns]
                if join_keys:
                    merged_df = pd.merge(merged_df, df, on=join_keys, how="outer", suffixes=("", f"_{ds_id}"))
                else:
                    merged_df = pd.concat([merged_df, df], axis=1)

        return merged_df if merged_df is not None else pd.DataFrame()

    def execute(self, endpoint: str, variables: Dict[str, Any], method: str = "POST") -> pd.DataFrame:
        xml_payload = self.build_xml_payload(variables)
        headers = {
            "Content-Type": "application/xml",
            "Accept": "application/xml"
        }

        try:
            response = requests.request(
                method=method,
                url=endpoint,
                data=xml_payload.encode("utf-8"),
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return self.parse_xml_response(response.text)
        except Exception as e:
            log.error(f"Error executing Nexacro HTTP request to [{endpoint}]: {str(e)}")
            return pd.DataFrame()


=== FILE: ./drivers/__init__.py ===
from drivers.base import BaseDriver, DriverRegistry, PassthroughDriver
from drivers.nexacro import NexacroDriver

__all__ = [
    "BaseDriver", 
    "DriverRegistry", 
    "PassthroughDriver", 
    "NexacroDriver"
]


