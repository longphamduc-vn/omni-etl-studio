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