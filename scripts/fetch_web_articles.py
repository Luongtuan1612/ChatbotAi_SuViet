import os
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

# =========================================================
# Xác định thư mục gốc project
# File này nằm trong: suviet_ai/scripts/fetch_web_articles.py
# PROJECT_ROOT sẽ là: suviet_ai/
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SOURCE_URLS_DIR = PROJECT_ROOT / "data" / "source_urls"
PERIODS_DIR = PROJECT_ROOT / "data" / "periods"
ADMIN_SOURCES_DIR = PROJECT_ROOT / "data" / "manual_documents" / "admin_sources"


# =========================================================
# Cấu hình fetch
# =========================================================

REQUEST_TIMEOUT = 25
SLEEP_SECONDS = 1

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# =========================================================
# Danh sách các thời kỳ lịch sử
# Key phải trùng với tên file trong data/source_urls/
# Ví dụ:
# 05_nha_ly -> data/source_urls/05_nha_ly.txt
# =========================================================

PERIODS = {
    "01_thoi_tien_su": {"period_name": "Thời tiền sử"},
    "02_thoi_dung_nuoc": {"period_name": "Thời dựng nước"},
    "03_bac_thuoc_va_chong_bac_thuoc": {"period_name": "Bắc thuộc và chống Bắc thuộc"},
    "04_ngo_dinh_tien_le": {"period_name": "Nhà Ngô, Đinh, Tiền Lê"},
    "05_nha_ly": {"period_name": "Nhà Lý"},
    "06_nha_tran": {"period_name": "Nhà Trần"},
    "07_nha_ho": {"period_name": "Nhà Hồ"},
    "08_nha_le_so": {"period_name": "Nhà Lê sơ"},
    "09_nam_bac_trieu_trinh_nguyen": {
        "period_name": "Nam - Bắc triều và Trịnh - Nguyễn phân tranh"
    },
    "10_tay_son": {"period_name": "Phong trào Tây Sơn"},
    "11_nha_nguyen": {"period_name": "Nhà Nguyễn"},
    "12_viet_nam_1858_1945": {"period_name": "Việt Nam từ năm 1858 đến năm 1945"},
    "13_viet_nam_1945_1975": {"period_name": "Việt Nam từ năm 1945 đến năm 1975"},
    "14_viet_nam_1975_den_nay": {"period_name": "Việt Nam từ năm 1975 đến nay"},
    "15_nhan_vat_lich_su": {"period_name": "Nhân vật lịch sử"},
}


# =========================================================
# Menu rác hay bị lấy nhầm từ baotanglichsu.vn
# Đây chính là phần menu bên trái của trang:
# https://baotanglichsu.vn/vi/Articles/4043/nha-nuoc-van-lang-au-lac
# =========================================================

BAOTANG_MENU_LINES = {
    "lịch sử việt nam từ thời tiền sử đến hết triều nguyễn (1945)",
    "các văn hóa tiền đông sơn: phùng nguyên, đồng đậu, gò mun, khoảng 4.000 - 2.500 năm cách ngày nay",
    "các văn hóa tiền đông sơn: phùng nguyên, đồng đậu, gò mun, khoảng 4.000 - 2.500 năm cách ngày nay",
    "văn hóa đông sơn, khoảng 2.500 - 2.000 năm cách ngày nay",
    "văn hóa đông sơn, khoảng 2.500 - 2.000 năm cách ngày nay",
    "văn hóa sa huỳnh, khoảng 2.500 - 2.000 năm cách ngày nay",
    "văn hóa sa huỳnh, khoảng 2.500 - 2.000 năm cách ngày nay",
    "văn hóa đồng nai, khoảng 2.500 - 2.000 năm cách ngày nay",
    "văn hóa đồng nai, khoảng 2.500 - 2.000 năm cách ngày nay",
    "cuộc đấu tranh bảo tồn và tiếp thu, phát triển nền văn hóa dân tộc, thế kỷ 1-10",
    "cuộc đấu tranh bảo tồn và tiếp thu, phát triển nền văn hóa dân tộc, thế kỷ 1-10",
    "cuộc đấu tranh giành độc lập dân tộc, thế kỷ 1-10",
    "cuộc đấu tranh giành độc lập dân tộc, thế kỷ 1-10",
    "việt nam từ thế kỷ 10 đến giữa thế kỷ 20",
    "triều ngô - đinh - tiền lê (939 - 1009)",
    "triều ngô - đinh - tiền lê (939 - 1009)",
    "triều lê - mạc - lê trung hưng (1428 - 1788)",
    "triều lê - mạc - lê trung hưng (1428 - 1788)",
    "văn hóa óc eo - phù nam (từ thế kỷ 1 đến thế kỷ 7)",
    "sưu tập nghệ thuật champa (từ thế kỷ 7 đến thế kỷ 16)",
    "sưu tập hiện vật nghệ thuật đầu thế kỷ 20",
    "sưu tập hiện vật thời lý - nguyễn (từ thế kỷ 11 đến giữa thế kỷ 20)",
    "lịch sử việt nam từ giữa thế kỷ 19 tới nay",
    "cuộc đấu tranh giành độc lập của dân tộc việt nam (1858-1945)",
    "nhóm báo chí cách mạng thời kỳ 1936 – 1939",
    "nhóm báo chí cách mạng thời kỳ 1936 - 1939",
    "sưu tập vũ khí dùng trong cách mạng tháng tám năm 1945",
    "cuộc kháng chiến chống thực dân pháp (1946-1954)",
    "một số hiện vật về văn hóa - xã hội việt nam thời kỳ kháng chiến chống pháp",
    "một số hiện vật về chiến thắng điện biên phủ, tháng 5-1954",
    "cuộc kháng chiến chống đế quốc mỹ, giải phóng miền nam, thống nhất đất nước (1955-1975)",
    "một số vũ khí tự tạo nhân dân bến tre dùng trong phong trào đồng khởi, năm 1960.",
    "một số đồ dùng sinh hoạt và lao động được nhân dân việt nam làm từ xác máy bay mỹ",
    "nhóm hiện vật về nhân dân thế giới ủng hộ việt nam chống đế quốc mỹ",
    "việt nam trên con đường xây dựng dân giàu, nước mạnh, dân chủ, công bằng, văn minh (1976 đến nay)",
    "sưu tập tặng phẩm của nhân dân việt nam, nhân dân thế giới tặng chủ tịch hcm và đảng cộng sản việt nam",
}


# =========================================================
# Chuẩn hóa text để so sánh
# =========================================================


def normalize_for_compare(text: str) -> str:
    """
    Chuẩn hóa text để so sánh dòng:
    - Chuẩn hóa Unicode
    - Đưa về chữ thường
    - Gộp khoảng trắng
    - Chuẩn hóa dấu gạch ngang
    """
    if not text:
        return ""

    text = unicodedata.normalize("NFC", text)
    text = text.replace("\xa0", " ")
    text = text.replace("–", "-").replace("—", "-")
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)

    return text


NORMALIZED_BAOTANG_MENU_LINES = {
    normalize_for_compare(line) for line in BAOTANG_MENU_LINES
}


# =========================================================
# Nhận diện tên nguồn theo domain URL
# =========================================================


def detect_source_name(url: str) -> str:
    domain = urlparse(url).netloc.lower()

    # Chú ý: check subdomain cụ thể trước domain lớn
    if "tulieuvankien.dangcongsan.vn" in domain:
        return "Tư liệu Văn kiện Đảng"

    if "dangcongsan.vn" in domain:
        return "Báo điện tử Đảng Cộng sản Việt Nam"

    if "sknc.qdnd.vn" in domain:
        return "Báo Quân đội nhân dân"

    if "qdnd.vn" in domain:
        return "Báo Quân đội nhân dân"

    if "baochinhphu.vn" in domain:
        return "Cổng thông tin điện tử Chính phủ"

    if "xaydungchinhsach.chinhphu.vn" in domain:
        return "Cổng thông tin điện tử Chính phủ"

    if "tphcm.chinhphu.vn" in domain:
        return "Cổng thông tin điện tử Chính phủ"

    if "baotanglichsu.vn" in domain:
        return "Bảo tàng Lịch sử Quốc gia"

    if "baotanglichsuquocgia.vn" in domain:
        return "Bảo tàng Lịch sử Quốc gia"

    if "hochiminh.vn" in domain:
        return "Trang thông tin về Chủ tịch Hồ Chí Minh"

    if "nlv.gov.vn" in domain:
        return "Thư viện Quốc gia Việt Nam"

    if "moet.gov.vn" in domain:
        return "Bộ Giáo dục và Đào tạo"

    if "vietnam.vn" in domain:
        return "Cổng thông tin Việt Nam"

    if "vanmieu.gov.vn" in domain:
        return "Văn Miếu - Quốc Tử Giám"

    return domain


# =========================================================
# Xử lý tên file
# =========================================================


def remove_vietnamese_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text)

    text = "".join(char for char in text if unicodedata.category(char) != "Mn")

    text = text.replace("đ", "d").replace("Đ", "D")

    return text


def slugify(text: str) -> str:
    text = remove_vietnamese_accents(text)
    text = text.lower()
    text = text.strip()

    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")

    if not text:
        return "article"

    return text[:120].strip("-")


def make_unique_file_path(folder: Path, file_name: str) -> Path:
    """
    Hàm này dùng để tránh trùng tên file.
    """
    file_path = folder / file_name

    if not file_path.exists():
        return file_path

    name = Path(file_name).stem
    suffix = Path(file_name).suffix

    counter = 2

    while True:
        new_file_name = f"{name}-{counter}{suffix}"
        new_file_path = folder / new_file_name

        if not new_file_path.exists():
            return new_file_path

        counter += 1


# =========================================================
# Kiểm tra URL đã tải chưa
# =========================================================


def url_already_fetched(period_key: str, url: str) -> bool:
    """
    Kiểm tra URL đã được tải trong thư mục raw của thời kỳ chưa.

    Nếu trong file .txt đã có dòng:
    NGUỒN: <url>

    thì coi như URL đó đã được tải rồi và sẽ bỏ qua.
    """
    raw_folder = PERIODS_DIR / period_key / "raw"

    if not raw_folder.exists():
        return False

    normalized_url = url.strip()

    for file_path in raw_folder.glob("*.txt"):
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()

            if f"NGUỒN: {normalized_url}" in content:
                return True

        except Exception:
            continue

    return False


# =========================================================
# Làm sạch text cơ bản
# =========================================================


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = unicodedata.normalize("NFC", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    return text.strip()


def is_valid_tag(tag) -> bool:
    """
    Kiểm tra một đối tượng BeautifulSoup còn là Tag hợp lệ hay không.

    Một số website có HTML phức tạp; trong lúc crawler xóa tag bằng decompose(),
    BeautifulSoup có thể để lại object Tag đã bị hủy attrs. Nếu tiếp tục gọi
    tag.get(...) sẽ phát sinh lỗi: 'NoneType' object has no attribute 'get'.
    """
    return isinstance(tag, Tag) and getattr(tag, "attrs", None) is not None


def safe_decompose(tag) -> None:
    """Xóa một tag HTML an toàn, không làm dừng crawler nếu tag đã bị hủy."""
    try:
        if is_valid_tag(tag):
            tag.decompose()
    except Exception:
        pass


def get_attr_text(tag, attr_name: str) -> str:
    """Lấy attribute HTML an toàn dưới dạng chuỗi."""
    if not is_valid_tag(tag):
        return ""

    try:
        value = tag.get(attr_name, "")
    except Exception:
        return ""

    if isinstance(value, list):
        return " ".join(str(item) for item in value if item)

    if value is None:
        return ""

    return str(value)


# =========================================================
# Lọc dòng rác
# =========================================================


def is_bad_line(line: str) -> bool:
    """
    Kiểm tra một dòng có phải dòng rác/menu/sidebar/footer hay không.

    Lưu ý:
    Không xóa mọi dòng có chữ 'sưu tập' hoặc 'nghiên cứu',
    vì trong bài thật cũng có thể có các chữ này.
    Chỉ xóa khi dòng đó khớp menu hoặc có dấu hiệu điều hướng.
    """
    if not line:
        return True

    normalized = normalize_for_compare(line)

    if not normalized:
        return True

    # Bỏ dòng quá ngắn
    if len(normalized) <= 2:
        return True

    # Bỏ chính xác các dòng menu trái của baotanglichsu.vn
    if normalized in NORMALIZED_BAOTANG_MENU_LINES:
        return True

    # Các dòng điều hướng chính xác
    bad_exact_lines = {
        "toggle navigation",
        "trang chủ",
        "tin tức",
        "nghiên cứu",
        "trưng bày",
        "sưu tập",
        "hỗ trợ",
        "dịch vụ",
        "dịch vụ bảo tàng",
        "hòm thư góp ý",
        "theo dõi chúng tôi",
        "sitemap",
        "menu",
        "search",
        "tìm kiếm",
        "liên hệ",
        "đọc tiếp",
        "xem thêm",
        "bài viết liên quan",
        "các tin khác",
        "tin mới hơn",
        "tin cũ hơn",
        "facebook",
        "youtube",
        "zalo",
        "email",
        "print",
        "back",
    }

    if normalized in bad_exact_lines:
        return True

    # Các dòng ngắn chứa từ khóa rác.
    # Chỉ áp dụng cho dòng ngắn để tránh xóa nhầm nội dung bài viết.
    bad_keywords_for_short_lines = [
        "toggle navigation",
        "hòm thư góp ý",
        "theo dõi chúng tôi",
        "cơ quan chủ quản",
        "đơn vị quản lý",
        "địa chỉ:",
        "tel/fax",
        "email:",
        "đang online",
        "tổng truy cập",
        "sitemap",
        "bản quyền",
        "copyright",
        "chia sẻ",
        "in bài viết",
        "bài viết liên quan",
        "các tin khác",
        "tin mới hơn",
        "tin cũ hơn",
        "tag:",
        "tags:",
    ]

    if len(normalized) < 120:
        if any(keyword in normalized for keyword in bad_keywords_for_short_lines):
            return True

    # Các prefix menu hay gặp bên trái của baotanglichsu.vn
    bad_prefixes = [
        "các văn hóa tiền đông sơn",
        "các văn hóa tiền đông sơn",
        "văn hóa đông sơn, khoảng",
        "văn hóa đông sơn, khoảng",
        "văn hóa sa huỳnh",
        "văn hóa sa huỳnh",
        "văn hóa đồng nai",
        "văn hóa đồng nai",
        "sưu tập nghệ thuật champa",
        "sưu tập hiện vật nghệ thuật",
        "sưu tập hiện vật thời lý",
        "nhóm báo chí cách mạng",
        "nhóm hiện vật về nhân dân thế giới",
        "một số hiện vật về văn hóa",
        "một số hiện vật về chiến thắng",
        "một số vũ khí tự tạo",
        "một số đồ dùng sinh hoạt",
    ]

    if any(normalized.startswith(prefix) for prefix in bad_prefixes):
        return True

    return False


def clean_article_lines(lines: list[str]) -> str:
    """
    Làm sạch danh sách dòng:
    - Bỏ dòng rỗng
    - Bỏ dòng menu rác
    - Bỏ dòng trùng
    - Gộp thành đoạn văn
    """
    cleaned_lines = []
    seen = set()

    for line in lines:
        line = clean_text(line)

        if not line:
            continue

        if is_bad_line(line):
            continue

        normalized = normalize_for_compare(line)

        if normalized in seen:
            continue

        seen.add(normalized)
        cleaned_lines.append(line)

    return clean_text("\n\n".join(cleaned_lines))


# =========================================================
# Xóa block HTML không phải nội dung
# =========================================================


def remove_unwanted_html_blocks(soup: BeautifulSoup) -> None:
    """
    Xóa các block chắc chắn không phải nội dung bài viết.

    Bản này xử lý an toàn hơn bản cũ:
    - Không gọi tag.get(...) trên tag đã bị decompose().
    - Dùng list(...) để cố định danh sách tag trước khi xóa.
    - Nếu một selector lỗi thì bỏ qua selector đó, không làm dừng crawler.
    """
    if soup is None:
        return

    # Xóa các tag kỹ thuật không chứa nội dung chính
    for tag in list(
        soup(
            [
                "script",
                "style",
                "noscript",
                "iframe",
                "form",
                "button",
                "input",
                "select",
                "option",
                "svg",
            ]
        )
    ):
        safe_decompose(tag)

    # Xóa theo tag semantic
    for tag_name in ["header", "footer", "nav", "aside"]:
        try:
            for tag in list(soup.find_all(tag_name)):
                safe_decompose(tag)
        except Exception:
            continue

    # Xóa theo class/id phổ biến
    remove_selectors = [
        ".menu",
        ".nav",
        ".navbar",
        ".sidebar",
        ".side-bar",
        ".leftbar",
        ".left-bar",
        ".rightbar",
        ".right-bar",
        ".left-menu",
        ".right-menu",
        ".leftmenu",
        ".rightmenu",
        ".breadcrumb",
        ".breadcrumbs",
        ".footer",
        ".header",
        ".social",
        ".share",
        ".sharing",
        ".related",
        ".related-news",
        ".other-news",
        ".comment",
        ".comments",
        ".advertisement",
        ".ads",
        ".banner",
        ".box-search",
        ".search",
        ".pagination",
        ".pager",
        "#menu",
        "#nav",
        "#sidebar",
        "#left",
        "#right",
        "#footer",
        "#header",
        "#search",
    ]

    for selector in remove_selectors:
        try:
            for tag in list(soup.select(selector)):
                safe_decompose(tag)
        except Exception:
            continue

    # Xóa các tag có class/id chứa từ khóa menu/sidebar/footer
    bad_attr_keywords = [
        "menu",
        "sidebar",
        "side-bar",
        "left-menu",
        "right-menu",
        "breadcrumb",
        "footer",
        "header",
        "share",
        "social",
        "related",
        "comment",
        "advert",
        "banner",
        "search",
    ]

    try:
        all_tags = list(soup.find_all(True))
    except Exception:
        return

    for tag in all_tags:
        if not is_valid_tag(tag):
            continue

        class_text = get_attr_text(tag, "class")
        id_text = get_attr_text(tag, "id")
        attr_text = normalize_for_compare(f"{class_text} {id_text}")

        if any(keyword in attr_text for keyword in bad_attr_keywords):
            safe_decompose(tag)


# =========================================================
# Trích xuất tiêu đề
# =========================================================


def extract_title_from_url(url: str) -> str:
    path = urlparse(url).path
    last_part = path.rstrip("/").split("/")[-1]

    last_part = last_part.replace(".html", "")
    last_part = last_part.replace(".htm", "")
    last_part = last_part.replace("-", " ")
    last_part = last_part.replace("_", " ")

    return last_part.strip().title() or "Bài viết lịch sử"


def normalize_title(title: str) -> str:
    title = clean_text(title)

    remove_phrases = [
        "Bảo tàng Lịch sử Quốc gia",
        "Trang thông tin về Chủ tịch Hồ Chí Minh",
        "Cổng Thông tin điện tử Chính phủ",
        "Cổng thông tin điện tử Chính phủ",
        "Báo điện tử Đảng Cộng sản Việt Nam",
        "Báo Quân đội nhân dân",
        "Tư liệu Văn kiện Đảng",
        "Thư viện Quốc gia Việt Nam",
        "Bộ Giáo dục và Đào tạo",
        "Cổng thông tin Việt Nam",
        "Văn Miếu - Quốc Tử Giám",
    ]

    for phrase in remove_phrases:
        title = title.replace(phrase, "")

    title = title.strip(" -|–—")

    return title


def extract_title(soup: BeautifulSoup, url: str) -> str:
    candidates = []

    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        candidates.append(og_title.get("content"))

    twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
    if twitter_title and twitter_title.get("content"):
        candidates.append(twitter_title.get("content"))

    meta_title = soup.find("meta", attrs={"name": "title"})
    if meta_title and meta_title.get("content"):
        candidates.append(meta_title.get("content"))

    for tag_name in ["h1", "h2", "h3"]:
        for tag in soup.find_all(tag_name):
            text = tag.get_text(" ", strip=True)
            if text:
                candidates.append(text)

    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        candidates.append(title_tag.get_text(" ", strip=True))

    for text in candidates:
        title = normalize_title(text)

        if len(title) >= 8 and not is_bad_line(title):
            return title

    return extract_title_from_url(url)


# =========================================================
# Trích xuất nội dung bài viết
# =========================================================


def get_all_text_lines(soup: BeautifulSoup) -> list[str]:
    """
    Lấy toàn bộ text sau khi đã xóa block rác.
    """
    remove_unwanted_html_blocks(soup)

    full_text = soup.get_text("\n", strip=True)

    lines = []

    for line in full_text.splitlines():
        line = clean_text(line)

        if not line:
            continue

        lines.append(line)

    return lines


def extract_from_article_tags(soup: BeautifulSoup) -> str:
    """
    Ưu tiên lấy nội dung từ các thẻ/class thường chứa bài viết.
    """
    remove_unwanted_html_blocks(soup)

    selectors = [
        "article",
        "main",
        ".article-content",
        ".article-body",
        ".content-detail",
        ".news-detail",
        ".news-content",
        ".detail-content",
        ".post-content",
        ".entry-content",
        ".body-content",
        ".main-content",
        ".article-detail",
        ".detail",
        ".content",
        "#content",
        "#main",
    ]

    candidates = []

    for selector in selectors:
        try:
            tags = soup.select(selector)
        except Exception:
            continue

        for tag in tags:
            if not is_valid_tag(tag):
                continue

            text = tag.get_text("\n", strip=True)

            lines = []

            for line in text.splitlines():
                line = clean_text(line)

                if not line:
                    continue

                if is_bad_line(line):
                    continue

                # Dòng bài viết thường dài hơn 30 ký tự.
                # Nhưng vẫn giữ một số dòng tiêu đề phụ ngắn nếu cần.
                if len(line) >= 30:
                    lines.append(line)

            content = clean_article_lines(lines)

            if len(content) >= 150:
                candidates.append(content)

    if not candidates:
        return ""

    # Lấy candidate dài nhất sau lọc.
    return max(candidates, key=len)


def extract_after_title(lines: list[str], title: str) -> str:
    """
    Fallback:
    Nếu không bắt được article tag, bắt đầu lấy nội dung sau tiêu đề.
    """
    useful_lines = []
    start_collect = False

    title_normalized = normalize_for_compare(title)

    for line in lines:
        normalized = normalize_for_compare(line)

        if not start_collect:
            if normalized == title_normalized or title_normalized in normalized:
                start_collect = True
                continue

        if start_collect:
            stop_keywords = [
                "sơ đồ tham quan",
                "dịch vụ bảo tàng",
                "hòm thư góp ý",
                "theo dõi chúng tôi",
                "cơ quan chủ quản",
                "đơn vị quản lý",
                "địa chỉ:",
                "tel/fax",
                "email:",
                "bài viết liên quan",
                "các tin khác",
                "tin mới hơn",
                "tin cũ hơn",
                "tag:",
                "tags:",
            ]

            if any(keyword in normalized for keyword in stop_keywords):
                break

            if is_bad_line(line):
                continue

            if len(line) >= 30:
                useful_lines.append(line)

    return clean_article_lines(useful_lines)


def extract_from_meta_description(soup: BeautifulSoup) -> str:
    """
    Fallback rất yếu: lấy description nếu không lấy được nội dung.
    """
    meta = soup.find("meta", attrs={"name": "description"})

    if meta and meta.get("content"):
        return clean_text(meta.get("content"))

    meta = soup.find("meta", attrs={"property": "og:description"})

    if meta and meta.get("content"):
        return clean_text(meta.get("content"))

    return ""


def extract_general_content(lines: list[str]) -> str:
    """
    Fallback cuối:
    Lấy các dòng dài, bỏ dòng menu/rác.
    """
    useful_lines = []

    for line in lines:
        if is_bad_line(line):
            continue

        if len(line) >= 50:
            useful_lines.append(line)

    return clean_article_lines(useful_lines)


def parse_html_safely(html: str) -> BeautifulSoup:
    """
    Ưu tiên lxml, nếu lỗi thì dùng html.parser.
    """
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def is_baotanglichsu_url(url: str) -> bool:
    domain = urlparse(url).netloc.lower()
    return "baotanglichsu.vn" in domain or "baotanglichsuquocgia.vn" in domain


def get_plain_lines_without_aggressive_remove(html: str) -> list[str]:
    """
    Lấy text toàn trang nhưng KHÔNG xóa mạnh các block HTML.
    Chỉ bỏ script/style/noscript/iframe.
    Dùng cho baotanglichsu.vn vì trang này hay đặt nội dung chung với menu.
    """
    soup = parse_html_safely(html)

    for tag in list(soup(["script", "style", "noscript", "iframe"])):
        safe_decompose(tag)

    text = soup.get_text("\n", strip=True)

    lines = []

    for line in text.splitlines():
        line = clean_text(line)

        if not line:
            continue

        lines.append(line)

    return lines


def extract_baotanglichsu_content(html: str, title: str) -> str:
    """
    Bộ lấy nội dung riêng cho baotanglichsu.vn.
    Mục tiêu:
    - Không xóa nhầm content
    - Bỏ menu trái bằng is_bad_line()
    - Giữ lại đoạn văn thật
    """
    lines = get_plain_lines_without_aggressive_remove(html)

    cleaned_lines = []
    seen = set()

    title_normalized = normalize_for_compare(title)

    for line in lines:
        normalized = normalize_for_compare(line)

        if not normalized:
            continue

        # Bỏ title nếu lặp trong body
        if normalized == title_normalized:
            continue

        # Bỏ các dòng menu/sidebar/footer
        if is_bad_line(line):
            continue

        # Bỏ dòng trùng
        if normalized in seen:
            continue

        seen.add(normalized)

        # Với baotanglichsu.vn, menu thường là các dòng ngắn.
        # Nội dung thật thường là đoạn văn dài.
        if len(line) >= 80:
            cleaned_lines.append(line)

    content = clean_article_lines(cleaned_lines)

    # Trường hợp trang chỉ có 1 đoạn ngắn khoảng 250-500 ký tự vẫn giữ được
    if len(content) >= 120:
        return content

    return ""


def extract_article(url: str) -> dict:
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"

    html = response.text

    soup_for_title = parse_html_safely(html)
    title = extract_title(soup_for_title, url)

    content = ""

    # Cách riêng cho baotanglichsu.vn:
    # Không xóa HTML quá mạnh, tránh mất luôn nội dung bài viết.
    if is_baotanglichsu_url(url):
        content = extract_baotanglichsu_content(html, title)

    # Cách chung cho các website khác
    if len(content) < 150:
        soup_for_article = parse_html_safely(html)
        content = extract_from_article_tags(soup_for_article)

    if len(content) < 150:
        soup_for_lines = parse_html_safely(html)
        lines = get_all_text_lines(soup_for_lines)
        content = extract_after_title(lines, title)

    if len(content) < 150:
        soup_for_meta = parse_html_safely(html)
        content = extract_from_meta_description(soup_for_meta)

    if len(content) < 150:
        soup_for_general = parse_html_safely(html)
        lines = get_all_text_lines(soup_for_general)
        content = extract_general_content(lines)

    content = clean_text(content)

    return {
        "title": clean_text(title),
        "url": url,
        "source_name": detect_source_name(url),
        "content": content,
    }


# =========================================================
# Đọc URL và lưu bài viết
# =========================================================


def load_urls(urls_file: Path) -> list[str]:
    if not urls_file.exists():
        print(f"Không tìm thấy file URL: {urls_file}")
        return []

    urls = []

    with open(urls_file, "r", encoding="utf-8") as file:
        for line in file:
            url = line.strip()

            if not url:
                continue

            if url.startswith("#"):
                continue

            if not url.startswith("http://") and not url.startswith("https://"):
                continue

            urls.append(url)

    # Loại bỏ URL trùng trong cùng một file source_urls
    unique_urls = []
    seen = set()

    for url in urls:
        if url in seen:
            continue

        seen.add(url)
        unique_urls.append(url)

    return unique_urls


def save_article(article: dict, period_key: str, period_name: str):
    output_folder = PERIODS_DIR / period_key / "raw"
    output_folder.mkdir(parents=True, exist_ok=True)

    title = article["title"]
    file_name = slugify(title) + ".txt"
    file_path = make_unique_file_path(output_folder, file_name)

    final_text = f"""TIÊU ĐỀ: {article['title']}
NGUỒN: {article['url']}
TÊN NGUỒN: {article['source_name']}
GIAI ĐOẠN: {period_name}

NỘI DUNG:
{article['content']}
"""

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(final_text)

    print(f"Đã lưu: {file_path}")


def fetch_single_url_to_txt(
    url: str,
    title: str | None = None,
    period: str | None = None,
    category: str | None = None,
) -> dict:
    """
    Hàm phục vụ Admin:
    - Nhận 1 URL từ giao diện quản trị
    - Dùng lại hàm extract_article(url) hiện có để lấy nội dung
    - Lưu nội dung thành file .txt riêng
    - Trả về thông tin file để FastAPI/Spring Boot quản lý
    """

    cleaned_url = clean_text(url)

    if not cleaned_url.startswith("http://") and not cleaned_url.startswith("https://"):
        raise ValueError(
            "URL không hợp lệ. URL phải bắt đầu bằng http:// hoặc https://"
        )

    article = extract_article(cleaned_url)

    article_title = clean_text(title or article.get("title") or "Nguồn tri thức AI")
    article_content = clean_text(article.get("content") or "")

    if len(article_content) < 150:
        raise ValueError("Không lấy được nội dung đủ dài từ URL này.")

    ADMIN_SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    file_name = slugify(article_title) + ".txt"
    file_path = make_unique_file_path(ADMIN_SOURCES_DIR, file_name)

    final_text = f"""TIÊU ĐỀ: {article_title}
NGUỒN: {cleaned_url}
TÊN NGUỒN: {article.get("source_name") or detect_source_name(cleaned_url)}
GIAI ĐOẠN: {clean_text(period or "Nguồn do quản trị viên bổ sung")}
DANH MỤC: {clean_text(category or "")}

NỘI DUNG:
{article_content}
"""

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(final_text)

    return {
        "success": True,
        "title": article_title,
        "url": cleaned_url,
        "file_path": str(file_path),
        "content_preview": final_text[:15000],
        "content_length": len(final_text),
    }


def fetch_period(period_key: str, period_config: dict):
    period_name = period_config["period_name"]
    urls_file = SOURCE_URLS_DIR / f"{period_key}.txt"

    urls = load_urls(urls_file)

    if not urls:
        print(f"\nGiai đoạn '{period_name}' chưa có URL nào, bỏ qua.")
        return

    print("\n======================================")
    print(f"Đang tải dữ liệu cho giai đoạn: {period_name}")
    print(f"File URL: {urls_file}")
    print(f"Số URL: {len(urls)}")
    print("======================================")

    for index, url in enumerate(urls, start=1):
        try:
            if url_already_fetched(period_key, url):
                print(f"\n[{index}/{len(urls)}] Bỏ qua vì URL đã tải rồi: {url}")
                continue

            print(f"\n[{index}/{len(urls)}] Đang tải: {url}")

            article = extract_article(url)

            print(f"Tiêu đề: {article['title']}")
            print(f"Nguồn: {article['source_name']}")
            print(f"Số ký tự nội dung lấy được: {len(article['content'])}")

            if len(article["content"]) < 150:
                print("Bỏ qua vì nội dung quá ngắn hoặc không lấy được nội dung chính.")
                print("Nội dung lấy được:")
                print(article["content"])
                continue

            save_article(article, period_key, period_name)

            time.sleep(SLEEP_SECONDS)

        except Exception as e:
            print(f"Lỗi khi tải {url}: {type(e).__name__}: {e}")
            continue


def ensure_data_folders():
    SOURCE_URLS_DIR.mkdir(parents=True, exist_ok=True)
    PERIODS_DIR.mkdir(parents=True, exist_ok=True)

    for period_key in PERIODS.keys():
        (PERIODS_DIR / period_key / "raw").mkdir(parents=True, exist_ok=True)
        (PERIODS_DIR / period_key / "processed").mkdir(parents=True, exist_ok=True)

        urls_file = SOURCE_URLS_DIR / f"{period_key}.txt"

        if not urls_file.exists():
            urls_file.touch(encoding="utf-8")


def main():
    ensure_data_folders()

    print("PROJECT_ROOT:", PROJECT_ROOT)
    print("SOURCE_URLS_DIR:", SOURCE_URLS_DIR)
    print("PERIODS_DIR:", PERIODS_DIR)

    for period_key, period_config in PERIODS.items():
        fetch_period(period_key, period_config)

    print("\nHoàn tất tải dữ liệu web.")


if __name__ == "__main__":
    main()
