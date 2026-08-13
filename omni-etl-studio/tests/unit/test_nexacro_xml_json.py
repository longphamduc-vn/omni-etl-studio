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