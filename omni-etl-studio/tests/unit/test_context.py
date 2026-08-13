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