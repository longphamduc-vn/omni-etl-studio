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