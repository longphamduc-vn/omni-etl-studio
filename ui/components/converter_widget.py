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