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