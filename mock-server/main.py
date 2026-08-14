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