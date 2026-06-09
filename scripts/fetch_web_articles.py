import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


# =========================================================
# Xác định thư mục gốc project
# File này nằm trong: suviet_ai/scripts/fetch_web_articles.py
# PROJECT_ROOT sẽ là: suviet_ai/
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SOURCE_URLS_DIR = PROJECT_ROOT / "data" / "source_urls"
PERIODS_DIR = PROJECT_ROOT / "data" / "periods"


# =========================================================
# Danh sách các thời kỳ lịch sử
# Key phải trùng với tên file trong data/source_urls/
# Ví dụ:
# 05_nha_ly -> data/source_urls/05_nha_ly.txt
# =========================================================

PERIODS = {
    "01_thoi_tien_su": {
        "period_name": "Thời tiền sử"
    },
    "02_thoi_dung_nuoc": {
        "period_name": "Thời dựng nước"
    },
    "03_bac_thuoc_va_chong_bac_thuoc": {
        "period_name": "Bắc thuộc và chống Bắc thuộc"
    },
    "04_ngo_dinh_tien_le": {
        "period_name": "Nhà Ngô, Đinh, Tiền Lê"
    },
    "05_nha_ly": {
        "period_name": "Nhà Lý"
    },
    "06_nha_tran": {
        "period_name": "Nhà Trần"
    },
    "07_nha_ho": {
        "period_name": "Nhà Hồ"
    },
    "08_nha_le_so": {
        "period_name": "Nhà Lê sơ"
    },
    "09_nam_bac_trieu_trinh_nguyen": {
        "period_name": "Nam - Bắc triều và Trịnh - Nguyễn phân tranh"
    },
    "10_tay_son": {
        "period_name": "Phong trào Tây Sơn"
    },
    "11_nha_nguyen": {
        "period_name": "Nhà Nguyễn"
    },
    "12_viet_nam_1858_1945": {
        "period_name": "Việt Nam từ năm 1858 đến năm 1945"
    },
    "13_viet_nam_1945_1975": {
        "period_name": "Việt Nam từ năm 1945 đến năm 1975"
    },
    "14_viet_nam_1975_den_nay": {
        "period_name": "Việt Nam từ năm 1975 đến nay"
    },
    "15_nhan_vat_lich_su": {
        "period_name": "Nhân vật lịch sử"
    }
}


# =========================================================
# Nhận diện tên nguồn theo domain URL
# =========================================================

def detect_source_name(url: str) -> str:
    domain = urlparse(url).netloc.lower()

    if "baotanglichsu.vn" in domain:
        return "Bảo tàng Lịch sử Quốc gia"

    if "hochiminh.vn" in domain:
        return "Trang thông tin về Chủ tịch Hồ Chí Minh"

    if "nlv.gov.vn" in domain:
        return "Thư viện Quốc gia Việt Nam"

    if "moet.gov.vn" in domain:
        return "Bộ Giáo dục và Đào tạo"

    if "dangcongsan.vn" in domain:
        return "Báo điện tử Đảng Cộng sản Việt Nam"

    if "tulieuvankien.dangcongsan.vn" in domain:
        return "Tư liệu Văn kiện Đảng"

    if "qdnd.vn" in domain:
        return "Báo Quân đội nhân dân"

    if "vietnam.vn" in domain:
        return "Cổng thông tin Việt Nam"

    return domain


# =========================================================
# Xử lý tên file
# =========================================================

def slugify(text: str) -> str:
    text = text.lower()
    text = text.strip()

    vietnamese_map = {
        "à": "a", "á": "a", "ạ": "a", "ả": "a", "ã": "a",
        "â": "a", "ầ": "a", "ấ": "a", "ậ": "a", "ẩ": "a", "ẫ": "a",
        "ă": "a", "ằ": "a", "ắ": "a", "ặ": "a", "ẳ": "a", "ẵ": "a",
        "è": "e", "é": "e", "ẹ": "e", "ẻ": "e", "ẽ": "e",
        "ê": "e", "ề": "e", "ế": "e", "ệ": "e", "ể": "e", "ễ": "e",
        "ì": "i", "í": "i", "ị": "i", "ỉ": "i", "ĩ": "i",
        "ò": "o", "ó": "o", "ọ": "o", "ỏ": "o", "õ": "o",
        "ô": "o", "ồ": "o", "ố": "o", "ộ": "o", "ổ": "o", "ỗ": "o",
        "ơ": "o", "ờ": "o", "ớ": "o", "ợ": "o", "ở": "o", "ỡ": "o",
        "ù": "u", "ú": "u", "ụ": "u", "ủ": "u", "ũ": "u",
        "ư": "u", "ừ": "u", "ứ": "u", "ự": "u", "ử": "u", "ữ": "u",
        "ỳ": "y", "ý": "y", "ỵ": "y", "ỷ": "y", "ỹ": "y",
        "đ": "d"
    }

    for vietnamese_char, latin_char in vietnamese_map.items():
        text = text.replace(vietnamese_char, latin_char)

    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")

    if not text:
        return "article"

    return text[:120]


def make_unique_file_path(folder: Path, file_name: str) -> Path:
    """
    Hàm này chỉ dùng khi thật sự cần tránh trùng tên file.
    Nhưng do đã có kiểm tra URL trước khi tải, bình thường sẽ ít khi sinh -2, -3.
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
# Làm sạch text
# =========================================================

def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    return text.strip()


def is_bad_line(line: str) -> bool:
    lowered = line.lower().strip()

    bad_keywords = [
        "toggle navigation",
        "trang chủ",
        "tin tức",
        "nghiên cứu",
        "hỗ trợ",
        "dịch vụ bảo tàng",
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
        "facebook",
        "youtube",
        "zalo",
        "chia sẻ",
        "in bài viết",
        "print",
        "back",
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
        "tag:",
        "tags:"
    ]

    return any(keyword in lowered for keyword in bad_keywords)


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
        "Báo điện tử Đảng Cộng sản Việt Nam",
        "Báo Quân đội nhân dân",
        "Tư liệu Văn kiện Đảng"
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

        if len(title) >= 10:
            return title

    return extract_title_from_url(url)


# =========================================================
# Trích xuất nội dung bài viết
# =========================================================

def get_all_text_lines(soup: BeautifulSoup) -> list:
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()

    full_text = soup.get_text("\n", strip=True)

    lines = []

    for line in full_text.splitlines():
        line = line.strip()

        if not line:
            continue

        lines.append(line)

    return lines


def extract_from_article_tags(soup: BeautifulSoup) -> str:
    selectors = [
        "article",
        ".article-content",
        ".content-detail",
        ".news-detail",
        ".detail-content",
        ".post-content",
        ".entry-content",
        ".body-content",
        ".main-content",
        ".article-detail",
        ".detail",
        ".content",
        "#content"
    ]

    for selector in selectors:
        tag = soup.select_one(selector)

        if not tag:
            continue

        text = tag.get_text("\n", strip=True)
        lines = []

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            if is_bad_line(line):
                continue

            if len(line) >= 40:
                lines.append(line)

        content = clean_text("\n\n".join(lines))

        if len(content) >= 150:
            return content

    return ""


def extract_after_title(lines: list, title: str) -> str:
    useful_lines = []
    start_collect = False
    title_normalized = title.lower().strip()

    for line in lines:
        normalized = line.lower().strip()

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
                "địa chỉ:",
                "tel/fax",
                "email:",
                "bài viết liên quan",
                "các tin khác",
                "tin mới hơn",
                "tin cũ hơn",
                "tag:",
                "tags:"
            ]

            if any(keyword in normalized for keyword in stop_keywords):
                break

            if is_bad_line(line):
                continue

            if len(line) >= 40:
                useful_lines.append(line)

    return clean_text("\n\n".join(useful_lines))


def extract_from_meta_description(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", attrs={"name": "description"})

    if meta and meta.get("content"):
        return clean_text(meta.get("content"))

    meta = soup.find("meta", attrs={"property": "og:description"})

    if meta and meta.get("content"):
        return clean_text(meta.get("content"))

    return ""


def extract_general_content(lines: list) -> str:
    useful_lines = []

    for line in lines:
        if is_bad_line(line):
            continue

        if len(line) >= 60:
            useful_lines.append(line)

    return clean_text("\n\n".join(useful_lines))


def extract_article(url: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 SuVietAcademicBot/1.0"
    }

    response = requests.get(url, headers=headers, timeout=25)
    response.raise_for_status()

    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"

    soup = BeautifulSoup(response.text, "lxml")

    title = extract_title(soup, url)

    content = extract_from_article_tags(soup)

    if len(content) < 150:
        lines = get_all_text_lines(soup)
        content = extract_after_title(lines, title)

    if len(content) < 150:
        content = extract_from_meta_description(soup)

    if len(content) < 150:
        lines = get_all_text_lines(soup)
        content = extract_general_content(lines)

    return {
        "title": clean_text(title),
        "url": url,
        "source_name": detect_source_name(url),
        "content": clean_text(content)
    }


# =========================================================
# Đọc URL và lưu bài viết
# =========================================================

def load_urls(urls_file: Path) -> list:
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

            time.sleep(1)

        except Exception as e:
            print(f"Lỗi khi tải {url}: {e}")


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


if __name__ == "__main__":
    main()