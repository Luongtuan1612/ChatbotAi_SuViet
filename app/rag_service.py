
import re
import unicodedata
from typing import List, Dict, Any, Tuple, Optional

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
    Chuẩn hóa tiếng Việt để so khớp tốt hơn:
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
                "ho chi minh",
                "chu tich ho chi minh",
                "bac ho",
                "nguyen ai quoc",
                "nguyen tat thanh",
                "nguyen sinh cung",
            ],
            ["1858 1945", "1945 1975", "nhan vat lich su"],
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
                "sap nhap tinh",
                "sat nhap tinh",
                "sap xep don vi hanh chinh",
                "don vi hanh chinh cap tinh",
            ],
            ["1975 den nay"],
        ),
    ]

    preferred_periods: List[str] = []

    for keywords, periods in rules:
        if any(keyword in q for keyword in keywords):
            preferred_periods.extend(periods)

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
        "aliases": ["ho chi minh", "chu tich ho chi minh", "nguyen ai quoc", "nguyen tat thanh", "nguyen sinh cung", "bac ho"],
        "match_terms": [
            "ho chi minh",
            "chu tich ho chi minh",
            "nguyen ai quoc",
            "nguyen tat thanh",
            "nguyen sinh cung",
            "lanh tu",
            "tuyen ngon doc lap",
            "dang cong san viet nam",
        ],
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
    source_title = normalize_text(str(metadata.get("source_title", "")))
    file_name = normalize_text(str(metadata.get("file_name", "")))
    period = normalize_text(str(metadata.get("period", "")))
    doc = normalize_text(document)

    title_file_period = f"{title} {source_title} {file_name} {period}"

    for group in groups:
        for term in group["match_terms"]:
            term_norm = normalize_text(term)

            if term_norm in title_file_period:
                return True

            if term_norm in doc:
                return True

    return False


def has_title_or_file_entity_match(question: str, metadata: Dict[str, Any]) -> bool:
    groups = get_matched_entity_groups(question)

    if not groups:
        return False

    title = normalize_text(str(metadata.get("title", "")))
    source_title = normalize_text(str(metadata.get("source_title", "")))
    file_name = normalize_text(str(metadata.get("file_name", "")))

    title_file = f"{title} {source_title} {file_name}"

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
        "thoi tien su": "Việt Nam thời tiền sử đồ đá cũ đồ đá mới công cụ đá văn hóa Hòa Bình Sơn Vi Thần Sa cư dân cổ khảo cổ",
        "tien su": "Việt Nam thời tiền sử đồ đá cũ đồ đá mới công cụ đá văn hóa Hòa Bình Sơn Vi Thần Sa cư dân cổ khảo cổ",

        "vua hung": "Văn Lang Hùng Vương thời dựng nước Đông Sơn trống đồng",
        "an duong vuong": "Âu Lạc Cổ Loa nỏ thần Cao Lỗ",
        "co loa": "Âu Lạc An Dương Vương Cao Lỗ nỏ thần",

        "hai ba trung": "Trưng Trắc Trưng Nhị khởi nghĩa Hai Bà Trưng năm 40 43 nhà Đông Hán thời Bắc thuộc",
        "ha ba trung": "Hai Bà Trưng Trưng Trắc Trưng Nhị khởi nghĩa năm 40 43 nhà Đông Hán thời Bắc thuộc",
        "ba trieu": "Triệu Thị Trinh khởi nghĩa Bà Triệu thời Bắc thuộc chống quân Ngô",
        "ly nam de": "Lý Bí Lý Nam Đế nước Vạn Xuân năm 544 thời Bắc thuộc",
        "ly bi": "Lý Nam Đế nước Vạn Xuân năm 544 thời Bắc thuộc",
        "mai thuc loan": "Mai Hắc Đế khởi nghĩa Mai Thúc Loan thời Bắc thuộc",
        "phung hung": "Bố Cái Đại Vương Phùng Hưng thời Bắc thuộc",
        "ngo quyen": "Bạch Đằng năm 938 quân Nam Hán Kiều Công Tiễn Dương Đình Nghệ thời Bắc thuộc độc lập dân tộc kỷ nguyên độc lập",
        "bach dang 938": "Ngô Quyền quân Nam Hán Kiều Công Tiễn Dương Đình Nghệ năm 938",

        "ngo dinh tien le": "giai đoạn 939 1009 nhà Ngô nhà Đinh nhà Tiền Lê Ngô Quyền Đinh Bộ Lĩnh Lê Hoàn Đại Cồ Việt Hoa Lư",
        "trieu ngo": "nhà Ngô Ngô Quyền Cổ Loa năm 939",
        "nha dinh": "Đinh Bộ Lĩnh Đinh Tiên Hoàng Đại Cồ Việt Hoa Lư năm 968",
        "dinh bo linh": "Đinh Tiên Hoàng nhà Đinh dẹp loạn 12 sứ quân Đại Cồ Việt Hoa Lư",
        "tien le": "Lê Hoàn Lê Đại Hành nhà Tiền Lê kháng chiến chống Tống năm 981 Đại Cồ Việt",
        "le hoan": "Lê Đại Hành nhà Tiền Lê chống Tống năm 981",
        "le dai hanh": "Lê Hoàn nhà Tiền Lê chống Tống năm 981",

        "ly cong uan": "Lý Thái Tổ Chiếu dời đô Thăng Long Hoa Lư Đại La nhà Lý",
        "ly thai to": "Lý Công Uẩn Chiếu dời đô Thăng Long Hoa Lư Đại La nhà Lý",
        "ly thuong kiet": "Nam quốc sơn hà kháng chiến chống Tống sông Như Nguyệt nhà Lý",
        "nam quoc son ha": "Lý Thường Kiệt sông Như Nguyệt kháng chiến chống Tống nhà Lý tuyên ngôn độc lập",

        "tran hung dao": "Trần Quốc Tuấn Hịch tướng sĩ quân Mông Nguyên Bạch Đằng 1288 nhà Trần",
        "tran quoc tuan": "Trần Hưng Đạo Hịch tướng sĩ quân Mông Nguyên Bạch Đằng 1288 nhà Trần",
        "tran nhan tong": "Phật hoàng Trần Nhân Tông Phật giáo Trúc Lâm nhà Trần",
        "hich tuong si": "Trần Hưng Đạo Trần Quốc Tuấn kháng chiến chống Mông Nguyên nhà Trần",

        "ho quy ly": "Nhà Hồ Đại Ngu cải cách cuối thế kỷ XIV đầu thế kỷ XV Thành nhà Hồ",
        "nha ho": "Hồ Quý Ly Đại Ngu cải cách tiền giấy hạn điền hạn nô Thành nhà Hồ chống quân Minh",

        "le loi": "Lê Thái Tổ khởi nghĩa Lam Sơn chống quân Minh Bình Ngô đại cáo nhà Lê sơ",
        "le thai to": "Lê Lợi khởi nghĩa Lam Sơn chống quân Minh Bình Ngô đại cáo nhà Lê sơ",
        "nguyen trai": "Bình Ngô đại cáo khởi nghĩa Lam Sơn Lê Lợi quân Minh nhà Lê sơ",
        "binh ngo dai cao": "Nguyễn Trãi Lê Lợi khởi nghĩa Lam Sơn chống quân Minh tuyên ngôn độc lập nhà Lê sơ",
        "le thanh tong": "Luật Hồng Đức nhà Lê sơ Đại Việt văn trị võ công giáo dục thi cử",
        "luat hong duc": "Lê Thánh Tông Quốc triều hình luật nhà Lê sơ pháp luật Đại Việt",

        "quang trung": "Nguyễn Huệ Tây Sơn Ngọc Hồi Đống Đa quân Thanh năm 1789",
        "nguyen hue": "Quang Trung Tây Sơn Ngọc Hồi Đống Đa quân Thanh năm 1789",
        "ngoc hoi": "Quang Trung Nguyễn Huệ Tây Sơn đại phá quân Thanh năm 1789 Đống Đa",
        "dong da": "Quang Trung Nguyễn Huệ Tây Sơn Ngọc Hồi đại phá quân Thanh năm 1789",

        "ho chi minh": "Hồ Chí Minh Chủ tịch Hồ Chí Minh Nguyễn Sinh Cung Nguyễn Tất Thành Nguyễn Ái Quốc lãnh tụ cách mạng Việt Nam tiểu sử nhân vật lịch sử",
        "bac ho": "Hồ Chí Minh Chủ tịch Hồ Chí Minh Nguyễn Sinh Cung Nguyễn Tất Thành Nguyễn Ái Quốc lãnh tụ cách mạng Việt Nam tiểu sử nhân vật lịch sử",
        "nguyen ai quoc": "Hồ Chí Minh Nguyễn Ái Quốc Nguyễn Tất Thành Nguyễn Sinh Cung lãnh tụ cách mạng Việt Nam tiểu sử nhân vật lịch sử",
        "nguyen tat thanh": "Hồ Chí Minh Nguyễn Tất Thành Nguyễn Sinh Cung Nguyễn Ái Quốc lãnh tụ cách mạng Việt Nam tiểu sử nhân vật lịch sử",

        "khang chien chong phap": "Toàn quốc kháng chiến 1946 Việt Bắc 1947 Biên giới 1950 Điện Biên Phủ 1954 Hiệp định Genève",
        "thuc dan phap 1946 1954": "Toàn quốc kháng chiến Điện Biên Phủ Hiệp định Genève cuộc kháng chiến chống thực dân Pháp",
        "dien bien phu": "Võ Nguyên Giáp kháng chiến chống Pháp năm 1954 Hiệp định Genève",
        "geneve": "Hiệp định Genève năm 1954 Điện Biên Phủ kháng chiến chống Pháp",
        "gionevo": "Hiệp định Genève năm 1954 Điện Biên Phủ kháng chiến chống Pháp",
        "chien dich ho chi minh": "Đại thắng mùa Xuân 1975 giải phóng miền Nam thống nhất đất nước Văn Tiến Dũng",
        "cach mang thang tam": "năm 1945 Tổng khởi nghĩa Hồ Chí Minh Tuyên ngôn Độc lập Việt Nam Dân chủ Cộng hòa",
        "hiep dinh paris": "Hiệp định Paris năm 1973 kháng chiến chống Mỹ Việt Nam hóa chiến tranh",

        "doi moi": "Đại hội VI năm 1986 công cuộc Đổi mới phát triển kinh tế xã hội",
        "dai hoi vi": "Đại hội VI năm 1986 đường lối Đổi mới",
        "bao cap": "thời kỳ bao cấp khủng hoảng kinh tế xã hội trước Đổi mới",
        "wto": "Việt Nam gia nhập WTO hội nhập quốc tế",

        "sap nhap tinh": "sắp xếp đơn vị hành chính cấp tỉnh năm 2025 diện tích tự nhiên quy mô dân số tỉnh thành phố",
        "sat nhap tinh": "sắp xếp đơn vị hành chính cấp tỉnh năm 2025 diện tích tự nhiên quy mô dân số tỉnh thành phố",
        "don vi hanh chinh": "sắp xếp đơn vị hành chính cấp tỉnh năm 2025 diện tích tự nhiên quy mô dân số tỉnh thành phố",
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
    """
    q_norm = normalize_text(question)
    doc_norm = normalize_text(document)

    title = str(metadata.get("title", ""))
    source_title = str(metadata.get("source_title", ""))
    period = str(metadata.get("period", ""))
    file_name = str(metadata.get("file_name", ""))
    source = str(metadata.get("source", ""))

    title_norm = normalize_text(title)
    source_title_norm = normalize_text(source_title)
    period_norm = normalize_text(period)
    file_name_norm = normalize_text(file_name)
    source_norm = normalize_text(source)

    searchable_text = f"{doc_norm} {title_norm} {source_title_norm} {period_norm} {file_name_norm} {source_norm}"

    score = 0

    preferred_periods = detect_preferred_periods(question)

    if preferred_periods:
        if is_preferred_period(period, preferred_periods):
            score += 30
        else:
            score -= 25

    if has_title_or_file_entity_match(question, metadata):
        score += 80
    elif has_strong_entity_match(question, metadata, document):
        score += 35

    important_keywords = [
        "thời tiền sử",
        "tiền sử",
        "đồ đá cũ",
        "đồ đá mới",
        "văn hóa hòa bình",
        "sơn vi",
        "thần sa",
        "con moong",

        "văn lang",
        "âu lạc",
        "vua hùng",
        "an dương vương",
        "cổ loa",
        "đông sơn",

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

        "ngô đình tiền lê",
        "đinh bộ lĩnh",
        "đinh tiên hoàng",
        "lê hoàn",
        "lê đại hành",
        "đại cồ việt",
        "hoa lư",
        "loạn 12 sứ quân",

        "lý công uẩn",
        "lý thái tổ",
        "lý thường kiệt",
        "thăng long",
        "chiếu dời đô",
        "nam quốc sơn hà",
        "sông như nguyệt",

        "trần hưng đạo",
        "trần quốc tuấn",
        "trần nhân tông",
        "mông nguyên",
        "hịch tướng sĩ",

        "hồ quý ly",
        "nhà hồ",
        "đại ngu",
        "thành nhà hồ",

        "lê lợi",
        "lê thái tổ",
        "nguyễn trãi",
        "bình ngô đại cáo",
        "lê thánh tông",
        "luật hồng đức",

        "quang trung",
        "nguyễn huệ",
        "tây sơn",
        "ngọc hồi",
        "đống đa",

        "gia long",
        "minh mệnh",
        "minh mạng",
        "bảo đại",
        "châu bản",
        "mộc bản",

        "hồ chí minh",
        "chủ tịch hồ chí minh",
        "nguyễn ái quốc",
        "nguyễn tất thành",
        "nguyễn sinh cung",
        "bác hồ",
        "lãnh tụ",

        "nguyễn trung trực",
        "cần vương",
        "phan bội châu",
        "phan châu trinh",
        "nguyễn thái học",
        "việt minh",
        "cách mạng tháng tám",
        "tuyên ngôn độc lập",

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

        "đổi mới",
        "đại hội vi",
        "bao cấp",
        "hội nhập quốc tế",
        "wto",

        "sáp nhập tỉnh",
        "sát nhập tỉnh",
        "sắp xếp đơn vị hành chính",
        "đơn vị hành chính",
        "diện tích tự nhiên",
        "quy mô dân số",
    ]

    for keyword in important_keywords:
        keyword_norm = normalize_text(keyword)

        if keyword_norm in q_norm and keyword_norm in searchable_text:
            score += 12

            if keyword_norm in title_norm or keyword_norm in source_title_norm or keyword_norm in file_name_norm:
                score += 18

    stop_words = {
        "la", "ai", "gi", "cua", "va", "co", "trong", "voi", "cho",
        "mot", "nhung", "cac", "nao", "sao", "vi", "hay",
        "phan", "tich", "trinh", "bay", "y", "nghia",
        "dien", "ra", "giai", "doan", "thoi", "ky",
        "biet", "neu", "noi", "ve",
    }

    for word in q_norm.split():
        word = word.strip()

        if len(word) >= 3 and word not in stop_words and word in searchable_text:
            score += 1

            if word in title_norm or word in source_title_norm or word in file_name_norm:
                score += 2

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
# Quét sâu trong tài liệu cha
# =========================

SCAN_STOP_WORDS = {
    "la", "ai", "gi", "cua", "va", "co", "trong", "voi", "cho",
    "mot", "nhung", "cac", "nao", "sao", "vi", "hay",
    "phan", "trinh", "bay", "y", "nghia",
    "ra", "giai", "doan", "thoi", "ky",
    "biet", "neu", "noi", "ve", "duoc", "khong",
    "bao", "nhieu", "sau", "khi",
}


def get_meaningful_tokens(question: str) -> List[str]:
    """
    Tách các từ quan trọng từ câu hỏi.
    Không hard-code tên tỉnh, tên người, tên sự kiện.
    """
    q_norm = normalize_text(question)

    tokens = []

    for token in q_norm.split():
        token = token.strip()

        if len(token) < 2:
            continue

        if token in SCAN_STOP_WORDS:
            continue

        tokens.append(token)

    return tokens


def build_query_phrases(question: str) -> List[str]:
    """
    Tạo cụm từ 2, 3, 4 từ liên tiếp từ câu hỏi.
    """
    tokens = get_meaningful_tokens(question)

    phrases = []

    for size in [2, 3, 4]:
        for index in range(0, len(tokens) - size + 1):
            phrase = " ".join(tokens[index:index + size])
            phrases.append(phrase)

    return phrases


def contains_token(text_norm: str, token: str) -> bool:
    """
    So khớp token theo từ, tránh match nhầm chuỗi con.
    """
    return f" {token} " in f" {text_norm} "


def contains_phrase(text_norm: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text_norm} "


def generic_text_score(
    question: str,
    document: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Chấm điểm tổng quát cho một chunk dựa trên câu hỏi.
    Không dùng danh sách keyword cố định.
    """
    if not question or not document:
        return 0

    metadata = metadata or {}

    doc_norm = normalize_text(document)

    metadata_text = " ".join(
        [
            str(metadata.get("title", "")),
            str(metadata.get("source_title", "")),
            str(metadata.get("file_name", "")),
            str(metadata.get("period", "")),
            str(metadata.get("source", "")),
            str(metadata.get("url", "")),
            str(metadata.get("source_url", "")),
        ]
    )

    metadata_norm = normalize_text(metadata_text)

    tokens = get_meaningful_tokens(question)
    phrases = build_query_phrases(question)

    score = 0

    for token in tokens:
        if contains_token(doc_norm, token):
            score += 2

        if contains_token(metadata_norm, token):
            score += 1

    for phrase in phrases:
        if contains_phrase(doc_norm, phrase):
            score += 8

        if contains_phrase(metadata_norm, phrase):
            score += 3

    return score


def expand_context_by_parent_document_scan(
    question: str,
    vector_store: VectorStore,
    best_metadata: Dict[str, Any],
    max_best_chunks: int = 5,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Quét sâu trong một tài liệu cha.
    """
    parent_chunks = vector_store.get_chunks_by_document_metadata(best_metadata)

    print("Parent document scan: ON")
    print("Parent chunks found:", len(parent_chunks))

    if not parent_chunks:
        return [], []

    scored_chunks = []

    for item in parent_chunks:
        document = item.get("document", "")
        metadata = item.get("metadata", {})
        chunk_index = item.get("chunk_index", 0)

        score = generic_text_score(question, document, metadata)

        scored_chunks.append(
            {
                "score": score,
                "document": document,
                "metadata": metadata,
                "chunk_index": chunk_index,
            }
        )

    scored_chunks.sort(key=lambda item: item["score"], reverse=True)

    best_score = scored_chunks[0]["score"] if scored_chunks else 0

    print("Best parent scan score:", best_score)

    if best_score <= 0:
        return [], []

    selected_indexes = set()

    for item in scored_chunks[:max_best_chunks]:
        if item["score"] <= 0:
            continue

        chunk_index = item["chunk_index"]

        selected_indexes.add(chunk_index)
        selected_indexes.add(chunk_index - 1)
        selected_indexes.add(chunk_index + 1)

    selected_chunks = [
        item for item in parent_chunks
        if item.get("chunk_index", 0) in selected_indexes
    ]

    selected_chunks.sort(key=lambda item: item.get("chunk_index", 0))

    documents = [item.get("document", "") for item in selected_chunks]
    metadatas = [item.get("metadata", {}) for item in selected_chunks]

    print("Selected parent chunks:", len(documents))

    if scored_chunks:
        best_preview = scored_chunks[0]
        print("Best parent chunk preview:", best_preview.get("document", "")[:700])

    return documents, metadatas


def find_best_parent_context(
    question: str,
    vector_store: VectorStore,
    metadatas: List[Dict[str, Any]],
    max_candidates: int = 8,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Quét sâu trên nhiều tài liệu cha, không chỉ top 1.

    Mục tiêu:
    - Tránh trường hợp top 1 có nhắc đến entity nhưng không phải tài liệu chính.
    - Ví dụ hỏi "Hồ Chí Minh là ai?" nhưng top 1 lại là tài liệu về Tuyên ngôn độc lập.
    - Hàm này thử quét nhiều file ứng viên rồi chọn context có điểm tốt nhất.
    """
    best_documents: List[str] = []
    best_metadatas: List[Dict[str, Any]] = []
    best_score = 0
    checked_keys = set()

    candidate_metadatas = metadatas[:max_candidates]

    print("Multi-parent scan: ON")
    print("Parent candidates:", len(candidate_metadatas))

    for metadata in candidate_metadatas:
        if not metadata:
            continue

        key = (
            metadata.get("document_id")
            or metadata.get("file_path")
            or metadata.get("source_url")
            or metadata.get("url")
            or metadata.get("file_name")
        )

        if not key:
            continue

        if key in checked_keys:
            continue

        checked_keys.add(key)

        documents, parent_metadatas = expand_context_by_parent_document_scan(
            question=question,
            vector_store=vector_store,
            best_metadata=metadata,
            max_best_chunks=5,
        )

        if not documents:
            continue

        context_score = 0

        for doc, meta in zip(documents, parent_metadatas):
            context_score += generic_text_score(question, doc, meta)

        if has_title_or_file_entity_match(question, metadata):
            context_score += 120
        elif has_strong_entity_match(question, metadata, " ".join(documents)):
            context_score += 50

        title = (
            metadata.get("title")
            or metadata.get("source_title")
            or metadata.get("file_name")
        )

        print("Candidate parent:", title)
        print("Candidate parent score:", context_score)

        if context_score > best_score:
            best_score = context_score
            best_documents = documents
            best_metadatas = parent_metadatas

    print("Best multi-parent score:", best_score)

    return best_documents, best_metadatas


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

            title = (
                metadata.get("title")
                or metadata.get("source_title")
                or "Không rõ tiêu đề"
            )

            source = metadata.get("source", "Không rõ nguồn")
            period = metadata.get("period", "Không rõ giai đoạn")

            url = (
                metadata.get("url")
                or metadata.get("source_url")
                or ""
            )

            chunk_index = metadata.get("chunk_index", "")

            context_parts.append(
                f"""
[Tài liệu {index + 1}]
Tiêu đề: {title}
Nguồn: {source}
URL: {url}
Giai đoạn: {period}
Chunk: {chunk_index}
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
            url = metadata.get("url") or metadata.get("source_url")

            key = (
                metadata.get("title") or metadata.get("source_title"),
                url,
            )

            if key in seen:
                continue

            seen.add(key)

            sources.append(
                {
                    "title": metadata.get("title") or metadata.get("source_title"),
                    "source": metadata.get("source"),
                    "period": metadata.get("period"),
                    "url": url,
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

        # 7. Quét sâu nhiều tài liệu cha.
        parent_documents, parent_metadatas = find_best_parent_context(
            question=question,
            vector_store=self.vector_store,
            metadatas=metadatas,
            max_candidates=8,
        )

        if parent_documents:
            print("Dùng context từ multi-parent document scan.")
            documents = parent_documents
            metadatas = parent_metadatas
        else:
            print("Không tìm được context tốt từ parent scan, quay lại top chunk cũ.")

            if not has_minimum_relevance(expanded_question, documents[0], metadatas[0]):
                return {
                    "answer": NO_DATA_ANSWER,
                    "sources": []
                }

            final_top_k = min(settings.TOP_K, 3)

            documents = documents[:final_top_k]
            metadatas = metadatas[:final_top_k]
            distances = distances[:final_top_k]

        # 8. Build context từ chunk đã được chọn.
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
