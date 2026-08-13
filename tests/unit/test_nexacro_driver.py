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