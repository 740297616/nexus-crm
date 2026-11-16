from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time
from io import BytesIO
from re import sub
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException

EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

CUSTOMER_EXCEL_FIELDS: tuple[tuple[str, str, bool, str], ...] = (
    ("customer_no", "客户编号", True, "全局唯一，字母、数字、下划线和连字符"),
    ("name", "客户名称", True, "客户名称，重复名称只产生提醒"),
    ("owner_username", "负责人账号", False, "可填写负责人用户名或邮箱，由服务端校验数据范围"),
    ("source", "来源", False, "客户来源"),
    ("industry", "行业", False, "所属行业"),
    ("level", "等级", False, "A、B、C 或 D，默认 C"),
    ("status", "状态", False, "active 或 inactive，默认 active"),
    ("phone", "联系电话", False, "联系电话"),
    ("email", "联系邮箱", False, "邮箱地址"),
    ("address", "地址", False, "客户地址"),
    ("description", "客户描述", False, "客户备注或描述"),
)


def _normalize_header(value: object) -> str:
    return sub(r"[\s_\-]+", "", str(value).strip().casefold())


_FIELD_ALIASES: dict[str, set[str]] = {
    "customer_no": {"customer_no", "customerno", "客户编号", "客户编码", "编号"},
    "name": {"name", "customername", "客户名称", "名称"},
    "owner_username": {
        "owner",
        "ownerusername",
        "负责人",
        "负责人账号",
        "负责人用户名",
        "负责人邮箱",
    },
    "source": {"source", "来源"},
    "industry": {"industry", "行业"},
    "level": {"level", "等级", "客户等级"},
    "status": {"status", "状态", "客户状态"},
    "phone": {"phone", "mobile", "telephone", "联系电话", "手机", "手机号"},
    "email": {"email", "邮箱", "联系邮箱"},
    "address": {"address", "地址"},
    "description": {"description", "备注", "客户描述", "说明"},
}
_NORMALIZED_ALIASES = {
    _normalize_header(alias): field
    for field, aliases in _FIELD_ALIASES.items()
    for alias in aliases
}
_FORBIDDEN_HEADERS = {
    "ownerid",
    "负责人id",
    "负责人编号",
    "用户id",
    "用户编号",
    "departmentid",
    "部门id",
    "部门编号",
    "department",
    "role",
    "roleid",
    "permission",
    "permissions",
    "permissionid",
}


def _is_forbidden_header(normalized: str) -> bool:
    if normalized in _FORBIDDEN_HEADERS:
        return True
    return (
        ("owner" in normalized and "id" in normalized)
        or ("负责人" in normalized and "id" in normalized)
        or ("department" in normalized and "id" in normalized)
        or ("部门" in normalized and "id" in normalized)
        or "权限" in normalized
        or "角色" in normalized
    )


class ExcelParseError(ValueError):
    def __init__(self, message: str, *, code: str = "VALIDATION_ERROR", details: Any = None):
        super().__init__(message)
        self.code = code
        self.details = details


@dataclass(frozen=True)
class ParsedCustomerRow:
    row_number: int
    values: dict[str, object]
    formula_fields: tuple[str, ...]


@dataclass(frozen=True)
class ParsedCustomerWorkbook:
    rows: list[ParsedCustomerRow]
    headers: dict[str, str]
    ignored_headers: tuple[str, ...]


def parse_customer_workbook(content: bytes, *, max_rows: int) -> ParsedCustomerWorkbook:
    try:
        workbook = load_workbook(
            BytesIO(content),
            read_only=True,
            data_only=False,
            keep_links=False,
        )
    except (InvalidFileException, OSError, ValueError, KeyError) as exc:
        raise ExcelParseError("无法读取 Excel 文件，请上传有效的 .xlsx 文件") from exc

    try:
        if not workbook.worksheets:
            raise ExcelParseError("Excel 文件没有可导入的工作表")
        worksheet = workbook.worksheets[0]
        if worksheet.max_row is not None and worksheet.max_row > max_rows + 1:
            raise ExcelParseError(
                f"导入行数超过上限（最多 {max_rows} 行）",
                code="FILE_TOO_LARGE",
            )
        rows = worksheet.iter_rows(values_only=False)
        try:
            header_cells = next(rows)
        except StopIteration as exc:
            raise ExcelParseError("Excel 文件为空") from exc
        if not any(cell.value is not None and str(cell.value).strip() for cell in header_cells):
            raise ExcelParseError("Excel 首行必须包含字段标题")

        headers: dict[str, str] = {}
        ignored_headers: list[str] = []
        for cell in header_cells:
            if cell.value is None or not str(cell.value).strip():
                continue
            original = str(cell.value).strip()
            normalized = _normalize_header(original)
            if _is_forbidden_header(normalized):
                raise ExcelParseError(
                    f"不允许导入字段：{original}",
                    details={"field": original},
                )
            field = _NORMALIZED_ALIASES.get(normalized)
            if field is None:
                ignored_headers.append(original)
                continue
            if field in headers:
                raise ExcelParseError(
                    f"字段重复映射：{original}",
                    details={"field": field},
                )
            headers[field] = original

        missing_fields = [
            display_name
            for field, display_name, required, _description in CUSTOMER_EXCEL_FIELDS
            if required and field not in headers
        ]
        if missing_fields:
            raise ExcelParseError(
                "Excel 缺少必填字段",
                details={"missing_fields": missing_fields},
            )

        header_index = {
            field: index
            for index, cell in enumerate(header_cells)
            if cell.value is not None
            for field in [_NORMALIZED_ALIASES.get(_normalize_header(cell.value))]
            if field is not None
        }
        parsed_rows: list[ParsedCustomerRow] = []
        for row_number, cells in enumerate(rows, start=2):
            if all(_cell_is_empty(cell) for cell in cells):
                continue
            if len(parsed_rows) >= max_rows:
                raise ExcelParseError(
                    f"导入行数超过上限（最多 {max_rows} 行）",
                    code="FILE_TOO_LARGE",
                )
            formula_fields: list[str] = []
            for index, cell in enumerate(cells):
                if _is_formula(cell.value):
                    header = (
                        str(header_cells[index].value).strip() if index < len(header_cells) else ""
                    )
                    formula_fields.append(
                        _NORMALIZED_ALIASES.get(
                            _normalize_header(header), header or f"列{index + 1}"
                        )
                    )
            values = {
                field: _cell_value(cells[index].value if index < len(cells) else None)
                for field, index in header_index.items()
            }
            parsed_rows.append(
                ParsedCustomerRow(
                    row_number=row_number,
                    values=values,
                    formula_fields=tuple(dict.fromkeys(formula_fields)),
                )
            )
        if not parsed_rows:
            raise ExcelParseError("Excel 工作表没有客户数据")
        return ParsedCustomerWorkbook(
            rows=parsed_rows,
            headers=headers,
            ignored_headers=tuple(ignored_headers),
        )
    finally:
        workbook.close()


def build_customer_template() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "customers"
    headers = [
        display_name for _field, display_name, _required, _description in CUSTOMER_EXCEL_FIELDS
    ]
    worksheet.append(headers)
    _style_header(worksheet, len(headers))
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    for index, (_field, display_name, _required, _description) in enumerate(
        CUSTOMER_EXCEL_FIELDS, start=1
    ):
        worksheet.column_dimensions[get_column_letter(index)].width = max(14, len(display_name) + 4)

    instructions = workbook.create_sheet("字段说明")
    instructions.append(["字段", "模板列名", "必填", "说明"])
    _style_header(instructions, 4)
    for field, display_name, required, description in CUSTOMER_EXCEL_FIELDS:
        instructions.append([field, display_name, "是" if required else "否", description])
    instructions.column_dimensions["A"].width = 22
    instructions.column_dimensions["B"].width = 18
    instructions.column_dimensions["C"].width = 10
    instructions.column_dimensions["D"].width = 58
    instructions.freeze_panes = "A2"

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def build_customer_export(customers: Iterable[Any]) -> bytes:
    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet("customers")
    headers = [
        display_name for _field, display_name, _required, _description in CUSTOMER_EXCEL_FIELDS
    ]
    worksheet.append(headers)
    for customer in customers:
        worksheet.append(
            [
                _safe_excel_value(customer.customer_no),
                _safe_excel_value(customer.name),
                _safe_excel_value(customer.owner.username),
                _safe_excel_value(customer.source),
                _safe_excel_value(customer.industry),
                _safe_excel_value(customer.level),
                _safe_excel_value(customer.status),
                _safe_excel_value(customer.phone),
                _safe_excel_value(customer.email),
                _safe_excel_value(customer.address),
                _safe_excel_value(customer.description),
            ]
        )
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _style_header(worksheet: Any, column_count: int) -> None:
    fill = PatternFill(fill_type="solid", fgColor="1F6D62")
    font = Font(color="FFFFFF", bold=True)
    alignment = Alignment(horizontal="center", vertical="center")
    for column in range(1, column_count + 1):
        cell = worksheet.cell(row=1, column=column)
        cell.fill = fill
        cell.font = font
        cell.alignment = alignment


def _cell_is_empty(cell: Cell) -> bool:
    value = cell.value
    return value is None or (isinstance(value, str) and not value.strip())


def _is_formula(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value[0] in "=+-@"


def _cell_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _safe_excel_value(value: object) -> object:
    if isinstance(value, str) and value and value[0] in "=+-@":
        return f"'{value}"
    return value
