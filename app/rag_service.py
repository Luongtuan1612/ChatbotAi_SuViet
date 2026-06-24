import re
import unicodedata
from typing import List, Dict, Any, Tuple

from app.config import settings
from app.gemini_service import GeminiService
from app.embedding_service import EmbeddingService
from app.vector_store import VectorStore
from app.prompt_template import RAG_PROMPT_TEMPLATE


AI_ERROR_MESSAGES = [
    "dịch vụ AI đang quá tải",
    "vượt giới hạn sử dụng",
    "tạm thời không phản hồi",
    "chưa tạo được câu trả lời",
]


NO_DATA_ANSWER = "Hiện tại hệ thống chưa có đủ dữ liệu để trả lời chính xác câu hỏi này."


# =========================
# Chuẩn hóa văn bản
# =========================

def normalize_text(text: str) -> str:
    """
    Chuẩn hóa tiếng Việt để so khớp keyword tốt hơn:
    - lowercase
    - bỏ dấu tiếng Việt
    - đổi _, -, / thành khoảng trắng
    - gom nhiều khoảng trắng
    """
    if not text:
        return ""

    text = str(text).lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d")
    text = text.replace("-", " ").replace("_", " ").replace("/", " ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def contains_any(text: str, keywords: List[str]) -> bool:
    text_norm = normalize_text(text)

    return any(normalize_text(keyword) in text_norm for keyword in keywords)


def is_ai_error_answer(answer: str) -> bool:
    if not answer:
        return True

    answer_lower = answer.lower()

    return any(message.lower() in answer_lower for message in AI_ERROR_MESSAGES)


# =========================
# Nhận diện giai đoạn theo câu hỏi
# =========================

def detect_preferred_periods(question: str) -> List[str]:
    """
    Dự đoán giai đoạn ưu tiên theo câu hỏi.
    Mục tiêu: tránh lấy nhầm nguồn ở giai đoạn xa.
    """
    q = normalize_text(question)

    rules: List[Tuple[List[str], List[str]]] = [
        (
            [
                "thoi tien su",
                "tien su",
                "do da cu",
                "do da moi",
                "van hoa hoa binh",
                "son vi",
                "than sa",
                "con moong",
            ],
            ["thoi tien su"],
        ),
        (
            [
                "van lang",
                "au lac",
                "vua hung",
                "hung vuong",
                "an duong vuong",
                "co loa",
                "cao lo",
                "dong son",
                "trong dong",
            ],
            ["thoi dung nuoc", "nhan vat lich su"],
        ),
        (
            [
                "hai ba trung",
                "ha ba trung",
                "trung trac",
                "trung nhi",
                "ba trieu",
                "trieu thi trinh",
                "ly bi",
                "ly nam de",
                "van xuan",
                "mai thuc loan",
                "mai hac de",
                "phung hung",
                "bo cai dai vuong",
                "khuc thua du",
                "ho khuc",
                "duong dinh nghe",
                "bac thuoc",
                "chong bac thuoc",
            ],
            ["bac thuoc", "nhan vat lich su"],
        ),
        (
            [
                "ngo quyen",
                "bach dang 938",
                "nam han",
                "kieu cong tien",
            ],
            ["bac thuoc", "ngo dinh tien le", "nhan vat lich su"],
        ),
        (
            [
                "ngo dinh tien le",
                "trieu ngo",
                "nha ngo",
                "nha dinh",
                "tien le",
                "dinh bo linh",
                "dinh tien hoang",
                "le hoan",
                "le dai hanh",
                "dai co viet",
                "hoa lu",
                "loan 12 su quan",
                "chong tong 981",
                "nam 981",
                "939 1009",
            ],
            ["ngo dinh tien le", "nhan vat lich su"],
        ),
        (
            [
                "nha ly",
                "ly cong uan",
                "ly thai to",
                "ly thuong kiet",
                "chieu doi do",
                "thang long",
                "nam quoc son ha",
                "song nhu nguyet",
            ],
            ["nha ly", "nhan vat lich su"],
        ),
        (
            [
                "nha tran",
                "tran hung dao",
                "tran quoc tuan",
                "tran nhan tong",
                "tran quang khai",
                "tran khanh du",
                "pham ngu lao",
                "mong nguyen",
                "bach dang 1288",
                "hich tuong si",
                "dong a",
            ],
            ["nha tran", "nhan vat lich su"],
        ),
        (
            [
                "nha ho",
                "ho quy ly",
                "ho nguyen trung",
                "dai ngu",
                "thanh nha ho",
                "tien giay",
                "cai cach ho quy ly",
            ],
            ["nha ho", "nhan vat lich su"],
        ),
        (
            [
                "le so",
                "nha le so",
                "le loi",
                "le thai to",
                "nguyen trai",
                "lam son",
                "binh ngo dai cao",
                "le thanh tong",
                "luat hong duc",
                "chi lang",
                "xuong giang",
            ],
            ["nha le so", "nhan vat lich su"],
        ),
        (
            [
                "nam bac trieu",
                "le trung hung",
                "trinh nguyen",
                "mac dang dung",
                "nha mac",
                "chua trinh",
                "chua nguyen",
                "nguyen hoang",
                "dao duy tu",
                "nguyen huu canh",
                "mo coi",
                "hoi an",
                "dang trong",
                "dang ngoai",
            ],
            ["nam bac trieu", "trinh nguyen", "nhan vat lich su"],
        ),
        (
            [
                "tay son",
                "quang trung",
                "nguyen hue",
                "nguyen nhac",
                "nguyen lu",
                "ngoc hoi",
                "dong da",
                "rach gam",
                "xoai mut",
                "quan thanh",
            ],
            ["tay son", "nhan vat lich su"],
        ),
        (
            [
                "nha nguyen",
                "trieu nguyen",
                "gia long",
                "minh mang",
                "minh menh",
                "bao dai",
                "hue",
                "kinh do hue",
                "chau ban",
                "moc ban",
                "cuu dinh",
                "cuu vi than cong",
                "hoang sa",
                "truong sa",
            ],
            ["nha nguyen", "nhan vat lich su"],
        ),
        (
            [
                "phap xam luoc",
                "nguyen trung truc",
                "nguyen tri phuong",
                "can vuong",
                "huong khe",
                "dong du",
                "duy tan",
                "phan boi chau",
                "phan chau trinh",
                "nguyen thai hoc",
                "yen bai",
                "viet nam 1858 1945",
                "cach mang thang tam",
                "tuyen ngon doc lap",
                "viet minh",
                "chinh phu lam thoi",
                "2 9 1945",
            ],
            ["1858 1945", "nhan vat lich su"],
        ),
        (
            [
                "toan quoc khang chien",
                "khang chien chong phap",
                "thuc dan phap 1946 1954",
                "1946 1954",
                "viet bac 1947",
                "bien gioi 1950",
                "dien bien phu",
                "geneve",
                "gionevo",
                "gieng ne vo",
                "hiep dinh geneve",
                "hiep dinh gionevo",
            ],
            ["1945 1975"],
        ),
        (
            [
                "khang chien chong my",
                "chien tranh dac biet",
                "chien tranh cuc bo",
                "viet nam hoa chien tranh",
                "ap bac",
                "van tuong",
                "mau than 1968",
                "dien bien phu tren khong",
                "hiep dinh paris",
                "chien dich ho chi minh",
                "dai thang mua xuan 1975",
                "30 4 1975",
                "giai phong mien nam",
                "thong nhat dat nuoc",
                "van tien dung",
            ],
            ["1945 1975", "nhan vat lich su"],
        ),
        (
            [
                "sau nam 1975",
                "1975 den nay",
                "thong nhat ve mat nha nuoc",
                "bao cap",
                "khung hoang kinh te",
                "doi moi",
                "dai hoi vi",
                "1986",
                "nghi quyet 10",
                "hoi nhap quoc te",
                "asean",
                "wto",
                "giao duc lich su",
            ],
            ["1975 den nay"],
        ),
    ]

    preferred_periods: List[str] = []

    for keywords, periods in rules:
        if any(keyword in q for keyword in keywords):
            preferred_periods.extend(periods)

    # Loại trùng nhưng giữ thứ tự
    result = []
    seen = set()

    for period in preferred_periods:
        if period not in seen:
            seen.add(period)
            result.append(period)

    return result


def is_preferred_period(period: str, preferred_periods: List[str]) -> bool:
    if not preferred_periods:
        return True

    period_norm = normalize_text(period)

    return any(expected in period_norm for expected in preferred_periods)


# =========================
# Entity mạnh: nhân vật/sự kiện
# =========================

ENTITY_GROUPS = [
    {
        "aliases": ["hai ba trung", "ha ba trung", "trung trac", "trung nhi"],
        "match_terms": ["hai ba trung", "trung trac", "trung nhi", "khoi nghia hai ba trung", "ba trung"],
    },
    {
        "aliases": ["ba trieu", "trieu thi trinh"],
        "match_terms": ["ba trieu", "trieu thi trinh"],
    },
    {
        "aliases": ["ly bi", "ly nam de"],
        "match_terms": ["ly bi", "ly nam de", "van xuan"],
    },
    {
        "aliases": ["ngo quyen", "bach dang 938"],
        "match_terms": ["ngo quyen", "bach dang 938", "nam han"],
    },
    {
        "aliases": ["dinh bo linh", "dinh tien hoang", "nha dinh"],
        "match_terms": ["dinh bo linh", "dinh tien hoang", "nha dinh", "dai co viet", "hoa lu"],
    },
    {
        "aliases": ["le hoan", "le dai hanh", "tien le"],
        "match_terms": ["le hoan", "le dai hanh", "tien le", "chong tong 981"],
    },
    {
        "aliases": ["ngo dinh tien le", "trieu ngo dinh tien le"],
        "match_terms": ["ngo dinh tien le", "nha ngo", "nha dinh", "tien le", "939 1009"],
    },
    {
        "aliases": ["ly thuong kiet"],
        "match_terms": ["ly thuong kiet", "nam quoc son ha", "nhu nguyet", "chong tong"],
    },
    {
        "aliases": ["tran hung dao", "tran quoc tuan"],
        "match_terms": ["tran hung dao", "tran quoc tuan", "hich tuong si", "bach dang 1288"],
    },
    {
        "aliases": ["le loi", "le thai to"],
        "match_terms": ["le loi", "le thai to", "lam son"],
    },
    {
        "aliases": ["nguyen trai", "binh ngo dai cao"],
        "match_terms": ["nguyen trai", "binh ngo dai cao", "lam son"],
    },
    {
        "aliases": ["quang trung", "nguyen hue"],
        "match_terms": ["quang trung", "nguyen hue", "ngoc hoi", "dong da"],
    },
    {
        "aliases": ["nguyen trung truc"],
        "match_terms": ["nguyen trung truc", "nhut tao"],
    },
    {
        "aliases": ["phan boi chau", "dong du"],
        "match_terms": ["phan boi chau", "dong du", "duy tan hoi"],
    },
    {
        "aliases": ["phan chau trinh"],
        "match_terms": ["phan chau trinh", "duy tan", "canh tan"],
    },
    {
        "aliases": ["ho chi minh", "chu tich ho chi minh", "nguyen ai quoc", "bac ho"],
        "match_terms": ["ho chi minh", "nguyen ai quoc", "nguyen tat thanh", "tuyen ngon doc lap"],
    },
    {
        "aliases": ["vo nguyen giap", "dien bien phu"],
        "match_terms": ["vo nguyen giap", "dien bien phu", "khang chien chong phap"],
    },
    {
        "aliases": ["van tien dung", "chien dich ho chi minh"],
        "match_terms": ["van tien dung", "chien dich ho chi minh", "dai thang mua xuan 1975"],
    },
    {
        "aliases": ["doi moi", "dai hoi vi", "1986"],
        "match_terms": ["doi moi", "dai hoi vi", "1986", "cong cuoc doi moi"],
    },
]


def get_matched_entity_groups(question: str) -> List[Dict[str, List[str]]]:
    q = normalize_text(question)
    matched = []

    for group in ENTITY_GROUPS:
        if any(alias in q for alias in group["aliases"]):
            matched.append(group)

    return matched


def has_strong_entity_match(question: str, metadata: Dict[str, Any], document: str = "") -> bool:
    groups = get_matched_entity_groups(question)

    if not groups:
        return False

    title = normalize_text(str(metadata.get("title", "")))
    file_name = normalize_text(str(metadata.get("file_name", "")))
    period = normalize_text(str(metadata.get("period", "")))
    doc = normalize_text(document)

    title_file_period = f"{title} {file_name} {period}"

    for group in groups:
        for term in group["match_terms"]:
            term_norm = normalize_text(term)

            if term_norm in title_file_period:
                return True

            # Nếu trong nội dung có entity mạnh thì vẫn chấp nhận, nhưng yếu hơn title/file.
            if term_norm in doc:
                return True

    return False


def has_title_or_file_entity_match(question: str, metadata: Dict[str, Any]) -> bool:
    groups = get_matched_entity_groups(question)

    if not groups:
        return False

    title = normalize_text(str(metadata.get("title", "")))
    file_name = normalize_text(str(metadata.get("file_name", "")))
    title_file = f"{title} {file_name}"

    for group in groups:
        for term in group["match_terms"]:
            term_norm = normalize_text(term)

            if term_norm in title_file:
                return True

    return False


# =========================
# Mở rộng câu hỏi
# =========================

def expand_history_query(question: str) -> str:
    """
    Mở rộng nhẹ câu hỏi bằng từ khóa lịch sử phổ biến.
    Phần này chỉ hỗ trợ vector search, không quyết định có trả lời hay không.
    """
    q = normalize_text(question)

    expansions = {
        # Thời tiền sử
        "thoi tien su": "Việt Nam thời tiền sử đồ đá cũ đồ đá mới công cụ đá văn hóa Hòa Bình Sơn Vi Thần Sa cư dân cổ khảo cổ",
        "tien su": "Việt Nam thời tiền sử đồ đá cũ đồ đá mới công cụ đá văn hóa Hòa Bình Sơn Vi Thần Sa cư dân cổ khảo cổ",

        # Thời dựng nước
        "vua hung": "Văn Lang Hùng Vương thời dựng nước Đông Sơn trống đồng",
        "an duong vuong": "Âu Lạc Cổ Loa nỏ thần Cao Lỗ",
        "co loa": "Âu Lạc An Dương Vương Cao Lỗ nỏ thần",

        # Bắc thuộc
        "hai ba trung": "Trưng Trắc Trưng Nhị khởi nghĩa Hai Bà Trưng năm 40 43 nhà Đông Hán thời Bắc thuộc",
        "ha ba trung": "Hai Bà Trưng Trưng Trắc Trưng Nhị khởi nghĩa năm 40 43 nhà Đông Hán thời Bắc thuộc",
        "ba trieu": "Triệu Thị Trinh khởi nghĩa Bà Triệu thời Bắc thuộc chống quân Ngô",
        "ly nam de": "Lý Bí Lý Nam Đế nước Vạn Xuân năm 544 thời Bắc thuộc",
        "ly bi": "Lý Nam Đế nước Vạn Xuân năm 544 thời Bắc thuộc",
        "mai thuc loan": "Mai Hắc Đế khởi nghĩa Mai Thúc Loan thời Bắc thuộc",
        "phung hung": "Bố Cái Đại Vương Phùng Hưng thời Bắc thuộc",
        "ngo quyen": "Bạch Đằng năm 938 quân Nam Hán Kiều Công Tiễn Dương Đình Nghệ thời Bắc thuộc độc lập dân tộc kỷ nguyên độc lập",
        "bach dang 938": "Ngô Quyền quân Nam Hán Kiều Công Tiễn Dương Đình Nghệ năm 938",

        # Ngô - Đinh - Tiền Lê
        "ngo dinh tien le": "giai đoạn 939 1009 nhà Ngô nhà Đinh nhà Tiền Lê Ngô Quyền Đinh Bộ Lĩnh Lê Hoàn Đại Cồ Việt Hoa Lư",
        "trieu ngo": "nhà Ngô Ngô Quyền Cổ Loa năm 939",
        "nha dinh": "Đinh Bộ Lĩnh Đinh Tiên Hoàng Đại Cồ Việt Hoa Lư năm 968",
        "dinh bo linh": "Đinh Tiên Hoàng nhà Đinh dẹp loạn 12 sứ quân Đại Cồ Việt Hoa Lư",
        "tien le": "Lê Hoàn Lê Đại Hành nhà Tiền Lê kháng chiến chống Tống năm 981 Đại Cồ Việt",
        "le hoan": "Lê Đại Hành nhà Tiền Lê chống Tống năm 981",
        "le dai hanh": "Lê Hoàn nhà Tiền Lê chống Tống năm 981",

        # Nhà Lý
        "ly cong uan": "Lý Thái Tổ Chiếu dời đô Thăng Long Hoa Lư Đại La nhà Lý",
        "ly thai to": "Lý Công Uẩn Chiếu dời đô Thăng Long Hoa Lư Đại La nhà Lý",
        "ly thuong kiet": "Nam quốc sơn hà kháng chiến chống Tống sông Như Nguyệt nhà Lý",
        "nam quoc son ha": "Lý Thường Kiệt sông Như Nguyệt kháng chiến chống Tống nhà Lý tuyên ngôn độc lập",

        # Nhà Trần
        "tran hung dao": "Trần Quốc Tuấn Hịch tướng sĩ quân Mông Nguyên Bạch Đằng 1288 nhà Trần",
        "tran quoc tuan": "Trần Hưng Đạo Hịch tướng sĩ quân Mông Nguyên Bạch Đằng 1288 nhà Trần",
        "tran nhan tong": "Phật hoàng Trần Nhân Tông Phật giáo Trúc Lâm nhà Trần",
        "hich tuong si": "Trần Hưng Đạo Trần Quốc Tuấn kháng chiến chống Mông Nguyên nhà Trần",

        # Nhà Hồ
        "ho quy ly": "Nhà Hồ Đại Ngu cải cách cuối thế kỷ XIV đầu thế kỷ XV Thành nhà Hồ",
        "nha ho": "Hồ Quý Ly Đại Ngu cải cách tiền giấy hạn điền hạn nô Thành nhà Hồ chống quân Minh",

        # Lê sơ
        "le loi": "Lê Thái Tổ khởi nghĩa Lam Sơn chống quân Minh Bình Ngô đại cáo nhà Lê sơ",
        "le thai to": "Lê Lợi khởi nghĩa Lam Sơn chống quân Minh Bình Ngô đại cáo nhà Lê sơ",
        "nguyen trai": "Bình Ngô đại cáo khởi nghĩa Lam Sơn Lê Lợi quân Minh nhà Lê sơ",
        "binh ngo dai cao": "Nguyễn Trãi Lê Lợi khởi nghĩa Lam Sơn chống quân Minh tuyên ngôn độc lập nhà Lê sơ",
        "le thanh tong": "Luật Hồng Đức nhà Lê sơ Đại Việt văn trị võ công giáo dục thi cử",
        "luat hong duc": "Lê Thánh Tông Quốc triều hình luật nhà Lê sơ pháp luật Đại Việt",

        # Tây Sơn
        "quang trung": "Nguyễn Huệ Tây Sơn Ngọc Hồi Đống Đa quân Thanh năm 1789",
        "nguyen hue": "Quang Trung Tây Sơn Ngọc Hồi Đống Đa quân Thanh năm 1789",
        "ngoc hoi": "Quang Trung Nguyễn Huệ Tây Sơn đại phá quân Thanh năm 1789 Đống Đa",
        "dong da": "Quang Trung Nguyễn Huệ Tây Sơn Ngọc Hồi đại phá quân Thanh năm 1789",

        # Cận hiện đại
        "ho chi minh": "Chủ tịch Hồ Chí Minh Nguyễn Sinh Cung Nguyễn Tất Thành Nguyễn Ái Quốc Tuyên ngôn Độc lập",
        "bac ho": "Hồ Chí Minh Chủ tịch Hồ Chí Minh Nguyễn Sinh Cung Nguyễn Tất Thành Nguyễn Ái Quốc",
        "nguyen ai quoc": "Hồ Chí Minh Nguyễn Tất Thành Nguyễn Sinh Cung Đảng Cộng sản Việt Nam",

        # 1945-1975
        "khang chien chong phap": "Toàn quốc kháng chiến 1946 Việt Bắc 1947 Biên giới 1950 Điện Biên Phủ 1954 Hiệp định Genève",
        "thuc dan phap 1946 1954": "Toàn quốc kháng chiến Điện Biên Phủ Hiệp định Genève cuộc kháng chiến chống thực dân Pháp",
        "dien bien phu": "Võ Nguyên Giáp kháng chiến chống Pháp năm 1954 Hiệp định Genève",
        "geneve": "Hiệp định Genève năm 1954 Điện Biên Phủ kháng chiến chống Pháp",
        "gionevo": "Hiệp định Genève năm 1954 Điện Biên Phủ kháng chiến chống Pháp",
        "chien dich ho chi minh": "Đại thắng mùa Xuân 1975 giải phóng miền Nam thống nhất đất nước Văn Tiến Dũng",
        "cach mang thang tam": "năm 1945 Tổng khởi nghĩa Hồ Chí Minh Tuyên ngôn Độc lập Việt Nam Dân chủ Cộng hòa",
        "hiep dinh paris": "Hiệp định Paris năm 1973 kháng chiến chống Mỹ Việt Nam hóa chiến tranh",

        # 1975 đến nay
        "doi moi": "Đại hội VI năm 1986 công cuộc Đổi mới phát triển kinh tế xã hội",
        "dai hoi vi": "Đại hội VI năm 1986 đường lối Đổi mới",
        "bao cap": "thời kỳ bao cấp khủng hoảng kinh tế xã hội trước Đổi mới",
        "wto": "Việt Nam gia nhập WTO hội nhập quốc tế",
    }

    expanded_question = question

    for keyword, extra_keywords in expansions.items():
        if keyword in q:
            expanded_question += " " + extra_keywords

    return expanded_question


# =========================
# Chấm điểm keyword/rerank
# =========================

def keyword_score(question: str, document: str, metadata: Dict[str, Any]) -> int:
    """
    Chấm điểm keyword để hỗ trợ rerank.
    Điểm cao khi:
    - đúng entity trong title/file_name
    - đúng giai đoạn
    - đúng keyword trong nội dung
    - tránh nguồn nhiễu khi câu hỏi không hỏi về hiện vật/trưng bày
    """
    q_norm = normalize_text(question)
    doc_norm = normalize_text(document)

    title = str(metadata.get("title", ""))
    period = str(metadata.get("period", ""))
    file_name = str(metadata.get("file_name", ""))
    source = str(metadata.get("source", ""))

    title_norm = normalize_text(title)
    period_norm = normalize_text(period)
    file_name_norm = normalize_text(file_name)
    source_norm = normalize_text(source)

    searchable_text = f"{doc_norm} {title_norm} {period_norm} {file_name_norm} {source_norm}"

    score = 0

    # 1. Ưu tiên giai đoạn phù hợp
    preferred_periods = detect_preferred_periods(question)

    if preferred_periods:
        if is_preferred_period(period, preferred_periods):
            score += 30
        else:
            score -= 25

    # 2. Ưu tiên entity mạnh trong title/file_name
    if has_title_or_file_entity_match(question, metadata):
        score += 80
    elif has_strong_entity_match(question, metadata, document):
        score += 35

    # 3. Keyword quan trọng
    important_keywords = [
        # tiền sử
        "thời tiền sử",
        "tiền sử",
        "đồ đá cũ",
        "đồ đá mới",
        "văn hóa hòa bình",
        "sơn vi",
        "thần sa",
        "con moong",

        # dựng nước
        "văn lang",
        "âu lạc",
        "vua hùng",
        "an dương vương",
        "cổ loa",
        "đông sơn",

        # Bắc thuộc
        "hai bà trưng",
        "trưng trắc",
        "trưng nhị",
        "bà triệu",
        "lý nam đế",
        "lý bí",
        "mai thúc loan",
        "phùng hưng",
        "ngô quyền",
        "bạch đằng",
        "nam hán",
        "kiều công tiễn",
        "dương đình nghệ",

        # Ngô Đinh Tiền Lê
        "ngô đình tiền lê",
        "đinh bộ lĩnh",
        "đinh tiên hoàng",
        "lê hoàn",
        "lê đại hành",
        "đại cồ việt",
        "hoa lư",
        "loạn 12 sứ quân",

        # Lý
        "lý công uẩn",
        "lý thái tổ",
        "lý thường kiệt",
        "thăng long",
        "chiếu dời đô",
        "nam quốc sơn hà",
        "sông như nguyệt",

        # Trần
        "trần hưng đạo",
        "trần quốc tuấn",
        "trần nhân tông",
        "mông nguyên",
        "hịch tướng sĩ",

        # Hồ
        "hồ quý ly",
        "nhà hồ",
        "đại ngu",
        "thành nhà hồ",

        # Lê sơ
        "lê lợi",
        "lê thái tổ",
        "nguyễn trãi",
        "bình ngô đại cáo",
        "lê thánh tông",
        "luật hồng đức",

        # Tây Sơn
        "quang trung",
        "nguyễn huệ",
        "tây sơn",
        "ngọc hồi",
        "đống đa",

        # Nguyễn
        "gia long",
        "minh mệnh",
        "minh mạng",
        "bảo đại",
        "châu bản",
        "mộc bản",

        # 1858-1945
        "nguyễn trung trực",
        "cần vương",
        "phan bội châu",
        "phan châu trinh",
        "nguyễn thái học",
        "việt minh",
        "cách mạng tháng tám",
        "tuyên ngôn độc lập",

        # 1945-1975
        "toàn quốc kháng chiến",
        "kháng chiến chống pháp",
        "việt bắc",
        "biên giới",
        "điện biên phủ",
        "hiệp định genève",
        "hiệp định giơ-ne-vơ",
        "hiệp định paris",
        "chiến dịch hồ chí minh",
        "đại thắng mùa xuân 1975",
        "mậu thân 1968",

        # 1975 đến nay
        "đổi mới",
        "đại hội vi",
        "bao cấp",
        "hội nhập quốc tế",
        "wto",
    ]

    for keyword in important_keywords:
        keyword_norm = normalize_text(keyword)

        if keyword_norm in q_norm and keyword_norm in searchable_text:
            score += 12

            if keyword_norm in title_norm or keyword_norm in file_name_norm:
                score += 18

    # 4. Chấm thêm theo từng từ trong câu hỏi
    stop_words = {
        "la", "gi", "cua", "va", "co", "trong", "voi", "cho",
        "mot", "nhung", "cac", "nao", "sao", "vi", "hay",
        "phan", "tich", "trinh", "bay", "y", "nghia",
        "dien", "ra", "giai", "doan", "thoi", "ky",
        "cho", "biet", "neu", "noi", "ve",
    }

    for word in q_norm.split():
        word = word.strip()

        if len(word) >= 3 and word not in stop_words and word in searchable_text:
            score += 1

            if word in title_norm or word in file_name_norm:
                score += 2

    # 5. Giảm điểm nguồn nhiễu khi câu hỏi không hỏi về trưng bày/hiện vật/ảnh
    noisy_terms = [
        "tranh co dong",
        "trien lam",
        "toa dam",
        "giao duc truyen thong",
        "ky uc",
        "hien vat",
        "bao tang chien thang",
        "suu tap",
        "anh tu lieu",
    ]

    question_asks_noisy = any(
        term in q_norm
        for term in ["tranh", "trien lam", "hien vat", "bao tang", "anh tu lieu", "suu tap"]
    )

    if not question_asks_noisy and any(term in title_norm for term in noisy_terms):
        score -= 15

    return score


def rerank_results(
    question: str,
    documents: List[str],
    metadatas: List[Dict[str, Any]],
    distances: List[float],
    top_k: int,
):
    """
    Rerank kết quả:
    1. Ưu tiên keyword/entity/period score cao hơn
    2. Nếu cùng score, ưu tiên distance nhỏ hơn
    """
    combined = []

    for index, doc in enumerate(documents):
        metadata = metadatas[index]
        distance = distances[index] if index < len(distances) else 999
        score = keyword_score(question, doc, metadata)

        combined.append(
            {
                "document": doc,
                "metadata": metadata,
                "distance": distance,
                "score": score,
            }
        )

    combined.sort(key=lambda item: (-item["score"], item["distance"]))

    selected = combined[:top_k]

    return (
        [item["document"] for item in selected],
        [item["metadata"] for item in selected],
        [item["distance"] for item in selected],
    )


def filter_by_distance(
    documents: List[str],
    metadatas: List[Dict[str, Any]],
    distances: List[float],
    max_distance: float,
):
    """
    Lọc theo distance để bỏ chunk quá xa.
    """
    filtered_documents = []
    filtered_metadatas = []
    filtered_distances = []

    for index, doc in enumerate(documents):
        distance = distances[index] if index < len(distances) else 999
        metadata = metadatas[index]

        if distance <= max_distance:
            filtered_documents.append(doc)
            filtered_metadatas.append(metadata)
            filtered_distances.append(distance)

    return filtered_documents, filtered_metadatas, filtered_distances


def filter_by_source_quality(
    question: str,
    documents: List[str],
    metadatas: List[Dict[str, Any]],
    distances: List[float],
):
    """
    Lọc nguồn theo chất lượng:
    - Nếu nhận diện được giai đoạn, ưu tiên giai đoạn đúng.
    - Nếu có entity mạnh trong title/file/content, vẫn giữ.
    - Nếu tất cả bị lọc hết, trả lại danh sách cũ để tránh mất dữ liệu.
    """
    preferred_periods = detect_preferred_periods(question)

    filtered_documents = []
    filtered_metadatas = []
    filtered_distances = []

    for index, doc in enumerate(documents):
        metadata = metadatas[index]
        distance = distances[index] if index < len(distances) else 999

        period = str(metadata.get("period", ""))
        score = keyword_score(question, doc, metadata)

        period_ok = is_preferred_period(period, preferred_periods)
        strong_entity_ok = has_strong_entity_match(question, metadata, doc)
        title_file_ok = has_title_or_file_entity_match(question, metadata)

        if preferred_periods:
            if period_ok or strong_entity_ok or title_file_ok:
                filtered_documents.append(doc)
                filtered_metadatas.append(metadata)
                filtered_distances.append(distance)
        else:
            # Không đoán được giai đoạn thì giữ các kết quả có chút liên quan.
            if score > 0:
                filtered_documents.append(doc)
                filtered_metadatas.append(metadata)
                filtered_distances.append(distance)

    if filtered_documents:
        return filtered_documents, filtered_metadatas, filtered_distances

    return documents, metadatas, distances


def has_minimum_relevance(question: str, document: str, metadata: Dict[str, Any]) -> bool:
    """
    Chặn nhẹ các câu ngoài phạm vi.
    Không chặn quá gắt để tránh làm mất câu trả lời đúng.
    """
    score = keyword_score(question, document, metadata)

    if score >= 8:
        return True

    if has_strong_entity_match(question, metadata, document):
        return True

    return False


# =========================
# RAG Service
# =========================

class RAGService:
    def __init__(self):
        self.gemini_service = GeminiService()
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()

    def build_context(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]]
    ) -> str:
        context_parts = []

        for index, doc in enumerate(documents):
            metadata = metadatas[index]

            title = metadata.get("title", "Không rõ tiêu đề")
            source = metadata.get("source", "Không rõ nguồn")
            period = metadata.get("period", "Không rõ giai đoạn")
            url = metadata.get("url", "")

            context_parts.append(
                f"""
[Tài liệu {index + 1}]
Tiêu đề: {title}
Nguồn: {source}
URL: {url}
Giai đoạn: {period}
Nội dung:
{doc}
"""
            )

        return "\n".join(context_parts)

    def format_sources(
        self,
        metadatas: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        sources = []
        seen = set()

        for metadata in metadatas:
            key = (
                metadata.get("title"),
                metadata.get("url"),
            )

            if key in seen:
                continue

            seen.add(key)

            sources.append(
                {
                    "title": metadata.get("title"),
                    "source": metadata.get("source"),
                    "period": metadata.get("period"),
                    "url": metadata.get("url"),
                    "file_name": metadata.get("file_name"),
                    "chunk_index": metadata.get("chunk_index"),
                }
            )

        return sources

    def ask(self, question: str) -> Dict[str, Any]:
        if not question or not question.strip():
            return {
                "answer": "Vui lòng nhập câu hỏi.",
                "sources": []
            }

        if self.vector_store.count_documents() == 0:
            return {
                "answer": "Hiện tại hệ thống chưa có dữ liệu lịch sử. Vui lòng nạp tài liệu trước.",
                "sources": []
            }

        # 1. Mở rộng câu hỏi để tăng khả năng vector search đúng.
        expanded_question = expand_history_query(question)

        # 2. Vector search.
        question_embedding = self.embedding_service.create_embedding(expanded_question)

        search_top_k = max(settings.TOP_K * 6, 30)

        results = self.vector_store.search(
            query_embedding=question_embedding,
            top_k=search_top_k
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not documents:
            return {
                "answer": NO_DATA_ANSWER,
                "sources": []
            }

        # 3. Rerank lần 1 theo entity/keyword/period.
        documents, metadatas, distances = rerank_results(
            question=expanded_question,
            documents=documents,
            metadatas=metadatas,
            distances=distances,
            top_k=search_top_k,
        )

        # 4. Distance filter.
        documents, metadatas, distances = filter_by_distance(
            documents=documents,
            metadatas=metadatas,
            distances=distances,
            max_distance=settings.SIMILARITY_THRESHOLD,
        )

        if not documents:
            return {
                "answer": NO_DATA_ANSWER,
                "sources": []
            }

        # 5. Lọc chất lượng nguồn theo giai đoạn/entity.
        documents, metadatas, distances = filter_by_source_quality(
            question=expanded_question,
            documents=documents,
            metadatas=metadatas,
            distances=distances,
        )

        if not documents:
            return {
                "answer": NO_DATA_ANSWER,
                "sources": []
            }

        # 6. Rerank lần 2 sau khi lọc.
        documents, metadatas, distances = rerank_results(
            question=expanded_question,
            documents=documents,
            metadatas=metadatas,
            distances=distances,
            top_k=search_top_k,
        )

        best_distance = distances[0] if distances else 999
        best_score = (
            keyword_score(expanded_question, documents[0], metadatas[0])
            if documents
            else 0
        )

        print("Câu hỏi gốc:", question)
        print("Câu hỏi mở rộng:", expanded_question)
        print("Best distance:", best_distance)
        print("Best keyword score:", best_score)
        print("Best title:", metadatas[0].get("title") if metadatas else None)
        print("Best period:", metadatas[0].get("period") if metadatas else None)
        print("Best file:", metadatas[0].get("file_name") if metadatas else None)

        # 7. Chặn nhẹ nếu kết quả tốt nhất quá ít liên quan.
        if not has_minimum_relevance(expanded_question, documents[0], metadatas[0]):
            return {
                "answer": NO_DATA_ANSWER,
                "sources": []
            }

        # 8. Lấy tối đa 3 tài liệu tốt nhất.
        final_top_k = min(settings.TOP_K, 3)

        documents = documents[:final_top_k]
        metadatas = metadatas[:final_top_k]
        distances = distances[:final_top_k]

        context = self.build_context(documents, metadatas)

        prompt = RAG_PROMPT_TEMPLATE.format(
            context=context,
            question=question
        )

        answer = self.gemini_service.generate_answer(prompt)

        # 9. Nếu Gemini quá tải hoặc lỗi thì không trả sources.
        if is_ai_error_answer(answer):
            return {
                "answer": answer,
                "sources": []
            }

        # 10. Nếu Gemini tự kết luận không đủ dữ liệu thì không trả sources.
        if NO_DATA_ANSWER in answer or "Hiện tại hệ thống chưa có đủ dữ liệu" in answer:
            return {
                "answer": answer,
                "sources": []
            }

        return {
            "answer": answer,
            "sources": self.format_sources(metadatas)
        }