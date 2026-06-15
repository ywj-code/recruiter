"""
文件解析工具
支持 PDF（文字型/图片型/混合型）、Word (.docx)、TXT 的文本提取。

核心能力：
- 文字型 PDF → PyMuPDF 直接提取文本层
- 图片型/扫描型 PDF → EasyOCR 光学字符识别
- 混合型 PDF → 逐页自动判断，文字页直提，图片页 OCR
- DOCX → python-docx 段落提取
- TXT → UTF-8/GBK 自动解码
"""

import io
import logging
import fitz  # PyMuPDF
import easyocr
import numpy as np

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────
# 配置区
# ────────────────────────────────────────────────
EASYOCR_MODEL_DIR = "models/easyocr"  # 本地 EasyOCR 模型目录
LANGS = ['ch_sim', 'en']
OCR_DPI = 200
CONFIDENCE_THRESHOLD = 0.5
MIN_TEXT_CHARS = 20  # 最低有效字符数
# ────────────────────────────────────────────────

# EasyOCR Reader 单例，避免每次调用都重新加载模型
_reader: easyocr.Reader | None = None


def _get_reader() -> easyocr.Reader:
    """获取 EasyOCR Reader 单例（延迟加载）"""
    global _reader
    if _reader is None:
        logger.info(f"正在加载 EasyOCR 模型 (语言: {LANGS})...")
        _reader = easyocr.Reader(
            LANGS,
            gpu=True,
            model_storage_directory=EASYOCR_MODEL_DIR,
            download_enabled=False,
        )
        logger.info("EasyOCR 模型加载完成")
    return _reader


def _is_scanned_page(page: fitz.Page) -> bool:
    """
    判断页面是否为扫描件（图片型无文字层）。

    Args:
        page: PyMuPDF 页面对象

    Returns:
        True 表示该页是图片型需要 OCR
    """
    return len(page.get_text().strip()) == 0


def _extract_normal_page(page: fitz.Page) -> str:
    """从文字型页面直接提取文本"""
    return page.get_text().strip()


def _extract_scanned_page(page: fitz.Page) -> str:
    """
    对图片型页面执行 OCR 识别。

    Args:
        page: PyMuPDF 页面对象

    Returns:
        OCR 识别后的文本
    """
    reader = _get_reader()
    mat = fitz.Matrix(OCR_DPI / 72, OCR_DPI / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, 3
    )
    results = reader.readtext(img, detail=1, paragraph=False)
    lines = [text for (_, text, conf) in results if conf >= CONFIDENCE_THRESHOLD]
    return "\n".join(lines)


def _parse_pdf(file_bytes: bytes) -> tuple[str, str, str]:
    """
    解析 PDF 文件，自动区分文字型 / 图片型 / 混合型。

    Args:
        file_bytes: PDF 文件字节数据

    Returns:
        (提取文本, 引擎信息, 错误信息)
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        return "", "PyMuPDF(打开失败)", f"PDF 打开失败：{e}"

    total = len(doc)
    scanned_count = 0
    text_parts: list[str] = []

    for page in doc:
        if _is_scanned_page(page):
            scanned_count += 1
            text_parts.append(_extract_scanned_page(page))
        else:
            text_parts.append(_extract_normal_page(page))

    doc.close()

    full_text = "\n".join(text_parts).strip()
    char_count = len(full_text)

    # 构造引擎信息
    if scanned_count == 0:
        mode = "文字型"
    elif scanned_count == total:
        mode = "图片型(OCR)"
    else:
        mode = f"混合型({scanned_count}页OCR)"

    info = f"PyMuPDF({mode},{total}p,{char_count}ch)"

    # 判断是否提取不足
    if char_count < MIN_TEXT_CHARS and scanned_count > 0:
        error = f"PDF 解析不足：仅 {char_count} 字符，OCR 可能识别率较低"
        return full_text, info, error

    if char_count < MIN_TEXT_CHARS:
        error = f"PDF 解析不足：仅 {char_count} 字符"
        return full_text, info, error

    return full_text, info, ""


def _parse_docx(file_bytes: bytes) -> tuple[str, str, str]:
    """
    解析 DOCX 文件。

    Args:
        file_bytes: DOCX 文件字节数据

    Returns:
        (提取文本, 引擎信息, 错误信息)
    """
    try:
        from docx import Document
    except ImportError:
        return "", "python-docx(未安装)", "缺少依赖：pip install python-docx"

    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as e:
        return "", "python-docx(打开失败)", f"DOCX 打开失败：{e}"

    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs)
    char_count = len(full_text)
    info = f"python-docx({char_count}ch)"

    if char_count < MIN_TEXT_CHARS:
        return full_text, info, f"DOCX 解析不足：仅 {char_count} 字符"

    return full_text, info, ""


def parse_pdf(file_bytes: bytes, filename: str = "") -> str:
    """
    解析 PDF 文件，提取纯文本（前向兼容接口）。

    自动识别页面类型：文字型页面直接提取，图片型页面 OCR 识别。

    Args:
        file_bytes: PDF 文件字节数据
        filename: 文件名（用于日志）

    Returns:
        提取的文本内容

    Raises:
        ValueError: 解析失败时抛出
    """
    txt, info, err = _parse_pdf(file_bytes)

    if err and not txt:
        logger.error(f"PDF 解析失败 {filename}: {err}")
        raise ValueError(f"无法解析 PDF 文件 {filename}: {err}")

    if err:
        logger.warning(f"PDF 解析警告 {filename}: {err}")

    logger.info(f"{info} - {filename}" if filename else info)
    return txt


def parse_docx(file_bytes: bytes, filename: str = "") -> str:
    """
    解析 Word (.docx) 文件，提取纯文本。

    Args:
        file_bytes: DOCX 文件字节数据
        filename: 文件名

    Returns:
        提取的文本内容
    """
    txt, info, err = _parse_docx(file_bytes)

    if err and not txt:
        logger.error(f"DOCX 解析失败 {filename}: {err}")
        raise ValueError(f"无法解析 DOCX 文件 {filename}: {err}")

    if err:
        logger.warning(f"DOCX 解析警告 {filename}: {err}")

    logger.info(f"{info} - {filename}" if filename else info)
    return txt


def parse_txt(file_bytes: bytes, filename: str = "") -> str:
    """
    解析纯文本文件。

    Args:
        file_bytes: 文件字节数据
        filename: 文件名

    Returns:
        文本内容
    """
    try:
        text = file_bytes.decode("utf-8")
        logger.info(f"UTF-8 解码成功 {filename}: {len(text)} 字符")
        return text
    except UnicodeDecodeError:
        try:
            text = file_bytes.decode("gbk")
            logger.info(f"GBK 解码成功 {filename}: {len(text)} 字符")
            return text
        except Exception as e:
            logger.error(f"文本解码失败 {filename}: {e}")
            raise ValueError(f"无法解码文本文件 {filename}: {e}")


def parse_file(file_bytes: bytes, filename: str) -> str:
    """
    根据文件扩展名自动选择解析器。

    支持格式：
    - PDF: 文字型直接提取；图片型/扫描型自动 OCR
    - DOCX: 段落文本提取
    - TXT: UTF-8 / GBK 自动解码

    Args:
        file_bytes: 文件字节数据
        filename: 文件名（含扩展名）

    Returns:
        提取的文本内容

    Raises:
        ValueError: 文件格式不支持或解析失败
    """
    filename_lower = filename.lower()

    if filename_lower.endswith(".pdf"):
        return parse_pdf(file_bytes, filename)
    elif filename_lower.endswith(".docx"):
        return parse_docx(file_bytes, filename)
    elif filename_lower.endswith(".txt"):
        return parse_txt(file_bytes, filename)
    else:
        raise ValueError(
            f"不支持的文件格式: {filename}。支持的格式: PDF, DOCX, TXT"
        )


# ────────────────────────────────────────────────
# 本地测试入口（直接运行此文件时生效）
# ────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    TEST_FILE = "D:\\pythonea\\test-date\\小黄_深度实战版_.pdf"

    if len(sys.argv) >= 2:
        TEST_FILE = sys.argv[1]

    print(f"[测试] 文件：{TEST_FILE}\n")

    with open(TEST_FILE, "rb") as f:
        file_bytes = f.read()

    filename = TEST_FILE.split("/")[-1].split("\\")[-1]

    txt, info, err = _parse_pdf(file_bytes)
    print(f"[info]  {info}")
    print(f"[error] {err if err else '（无）'}")
    print(f"[text]  共 {len(txt)} 字符")
    print("-" * 40)
    print(txt[:500] if txt else "（无内容）")
    if len(txt) > 500:
        print(f"... （已截断，共 {len(txt)} 字符）")
