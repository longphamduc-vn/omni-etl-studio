# ==============================================================================
# Filepath: mock_api.py
# Updated_at: 2026-08-17 06:56:00
# Description: FastAPI Nexacro XML simulation server (Token via Dataset)
# ==============================================================================

import json
from typing import Any, Dict, List
import xmltodict
from fastapi import FastAPI, Header, Request, Response

app = FastAPI(
    title="Nexacro XML-Only API Simulation with Auth",
    description="Backend simulation for Nexacro Dataset XML transport and Token Authentication",
    version="2.3.0"
)

# Secret token simulation for EMS domain
VALID_EMS_TOKEN = "ems_bearer_token_secret_xyz123"


def load_json_data() -> List[Dict[str, Any]]:
    """Loads product mock database records from local JSON file."""
    try:
        with open("products_db.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def build_nexacro_xml_response(error_code: int, error_msg: str, datasets: Dict[str, List[Dict[str, Any]]] = None) -> str:
    """Constructs valid Nexacro XML response document with Parameters and Datasets."""
    if datasets is None:
        datasets = {}

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


# ==============================================================================
# AUTHENTICATION ENDPOINT (TOKEN IN DATASET)
# ==============================================================================

@app.post("/api/auth/login")
async def auth_login(request: Request):
    """Endpoint cấp Token xác thực - Trả thông tin token trong Dataset ds_token."""
    body_bytes = await request.body()
    client_id = ""
    
    try:
        if body_bytes:
            parsed_xml = xmltodict.parse(body_bytes)
            root = parsed_xml.get('Root', {})
            ds = root.get('Dataset', {})
            if isinstance(ds, list):
                ds = ds[0] if ds else {}
            
            rows = ds.get('Rows', {}).get('Row', [])
            if isinstance(rows, dict):
                rows = [rows]
            for row in rows:
                cols = row.get('Col', [])
                if isinstance(cols, dict):
                    cols = [cols]
                for col in cols:
                    if col.get('@id') == 'client_id':
                        client_id = col.get('#text', '')
    except Exception:
        pass

    ds_token = [{
        "access_token": VALID_EMS_TOKEN,
        "token_type": "Bearer",
        "expires_in": 3600
    }]

    # Trả thông tin token dưới dạng Dataset "ds_token"
    xml_res = build_nexacro_xml_response(0, "Authentication successful", {"ds_token": ds_token})
    return Response(content=xml_res, media_type="application/xml")


# ==============================================================================
# NEXACRO XML BUSINESS ENDPOINTS (TOKEN VERIFIED)
# ==============================================================================

@app.post("/api/nexacro/xml/products/search-list")
async def search_product_list_xml(request: Request, authorization: str = Header(None)):
    """[XML] Tra cứu danh sách sản phẩm (Yêu cầu Header Authorization)."""
    if not authorization or authorization != f"Bearer {VALID_EMS_TOKEN}":
        xml_auth_err = build_nexacro_xml_response(-401, "Unauthorized: Invalid or Missing Auth Token")
        return Response(content=xml_auth_err, media_type="application/xml")

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
            
            if ds_id == 'ds_search':
                rows = ds.get('Rows', {}).get('Row', [])
                if isinstance(rows, dict):
                    rows = [rows]
                for row in rows:
                    cols = row.get('Col', [])
                    if isinstance(cols, dict):
                        cols = [cols]
                    for col in cols:
                        if col.get('@id') == 'category':
                            category_filter = col.get('#text', '')
                        if col.get('@id') == 'status':
                            status_filter = col.get('#text', '')
            
            elif ds_id == 'ds_id_list':
                rows = ds.get('Rows', {}).get('Row', [])
                if isinstance(rows, dict):
                    rows = [rows]
                for row in rows:
                    cols = row.get('Col', [])
                    if isinstance(cols, dict):
                        cols = [cols]
                    for col in cols:
                        if col.get('@id') == 'product_id' and col.get('#text'):
                            target_product_ids.append(col.get('#text'))
                            
    except Exception:
        pass

    raw_data = load_json_data()
    filtered = []
    for item in raw_data:
        match_cat = not category_filter or item.get("category") == category_filter
        match_status = not status_filter or item.get("inventory", {}).get("status") == status_filter
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

    xml_response = build_nexacro_xml_response(0, "SUCCESS", {"ds_step1_raw_search": filtered})
    return Response(content=xml_response, media_type="application/xml")


@app.post("/api/nexacro/xml/products/detail")
async def get_product_detail_xml(request: Request, authorization: str = Header(None)):
    """[XML] Tra chi tiết sản phẩm - Trả về 3 Datasets: ds_master, ds_inventory, ds_pricing."""
    if not authorization or authorization != f"Bearer {VALID_EMS_TOKEN}":
        xml_auth_err = build_nexacro_xml_response(-401, "Unauthorized: Invalid or Missing Auth Token")
        return Response(content=xml_auth_err, media_type="application/xml")

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
        xml_err = build_nexacro_xml_response(-1, "Invalid XML Payload")
        return Response(content=xml_err, media_type="application/xml")

    raw_data = load_json_data()
    found = next((item for item in raw_data if item["product_id"] == product_id_search), None)

    if not found:
        xml_err = build_nexacro_xml_response(-404, f"Product {product_id_search} Not Found", {
            "ds_master": [],
            "ds_inventory": [],
            "ds_pricing": []
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
        "available_quantity": found["inventory"]["available_quantity"],
        "status": found["inventory"].get("status", "")
    }]

    ds_pricing = [{
        "product_id": found["product_id"],
        "cost_price": found["pricing"]["cost_price"],
        "sale_price": found["pricing"]["sale_price"],
        "price_status": found["pricing"]["price_status"]
    }]

    xml_response = build_nexacro_xml_response(0, "SUCCESS", {
        "ds_master": ds_master,
        "ds_inventory": ds_inventory,
        "ds_pricing": ds_pricing
    })
    return Response(content=xml_response, media_type="application/xml")