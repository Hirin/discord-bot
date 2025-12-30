"""
Lecture-specific pytest fixtures.
"""
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_chat_raw() -> str:
    """Raw chat session with junk lines to filter."""
    return """Collapse All
Alice
10:00
Chào mọi người, hôm nay học về CNN

👍
2

Bob
10:02
Link tài liệu: https://docs.google.com/doc/12345
Mọi người check nha

Charlie
10:05
ok

Alice
10:08
Các layer của CNN bao gồm:
1. Convolutional Layer
2. Pooling Layer
3. Fully Connected Layer
Mình sẽ đi qua từng cái

👍
5

David
10:10
😊

Eve
10:12
Có ai có link Kahoot không?
https://kahoot.it/challenge/12345

Bob
10:15
```python
import torch.nn as nn

class CNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(3, 64, 3)
```
Code demo nè

Collapse All
"""


@pytest.fixture
def sample_chat_expected_messages() -> int:
    """Expected number of messages after filtering."""
    # Should keep:
    # 1. Alice "Chào mọi người..." (has greeting context)
    # 2. Bob "Link tài liệu..." (has link)
    # 3. Alice "Các layer của CNN..." (>= 6 words)
    # 4. Eve "Có ai có..." (has link, but Kahoot should be excluded from links)
    # 5. Bob code block (>= 3 lines)
    return 5  # Approximate, adjust based on actual logic


@pytest.fixture
def sample_transcript() -> str:
    """Short mock transcript for testing."""
    return """[0s] Giảng viên: Xin chào các bạn, hôm nay chúng ta sẽ học về Convolutional Neural Networks.
[30s] Giảng viên: CNN là một kiến trúc mạng neural đặc biệt cho xử lý ảnh.
[60s] Giảng viên: Có 3 layer chính: Convolutional, Pooling, và Fully Connected.
[120s] Học viên: Thầy ơi, pooling dùng để làm gì ạ?
[150s] Giảng viên: Pooling giúp giảm kích thước spatial và số parameter.
"""


@pytest.fixture
def sample_llm_output_with_timestamps() -> str:
    """Mock LLM output with timestamp markers."""
    return """## Tóm tắt bài giảng

### 1. Giới thiệu CNN
CNN là kiến trúc neural network cho xử lý ảnh. [-30s-]

### 2. Các layer chính
- Convolutional Layer [-60s-]
- Pooling Layer [-150s-]
- Fully Connected Layer

## 📁 Mục lục (Table of Contents)
- [Giới thiệu CNN | -30s-]
- [Pooling Layer | -150s-]
"""


@pytest.fixture
def sample_llm_output_with_pages() -> str:
    """Mock LLM output with page markers."""
    return """## Tổng quan

Nội dung về CNN architecture.

[-PAGE:3-]

### Convolutional Layer
Giải thích chi tiết về conv layer.

[-PAGE:5:"CNN Architecture Diagram"-]

### Pooling
Giảm kích thước feature map.

[-PAGE:7-]
"""


@pytest.fixture
def sample_llm_output_multi_doc() -> str:
    """Mock LLM output with multi-doc page markers."""
    return """## Nội dung chính

Từ tài liệu 1, chúng ta thấy...

[-DOC1:PAGE:3-]

Trong tài liệu 2, có giải thích thêm...

[-DOC2:PAGE:5-]

Kết luận từ cả 2 tài liệu.
"""


@pytest.fixture
def sample_pdf_with_links(tmp_path) -> str:
    """Create a simple PDF with hyperlinks for testing."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        pytest.skip("PyMuPDF not installed")
    
    pdf_path = tmp_path / "test_links.pdf"
    
    doc = fitz.open()
    
    # Page 1 with a link
    page1 = doc.new_page()
    page1.insert_text((50, 50), "Page 1 with link")
    # Use insert_link with proper format for newer PyMuPDF
    rect1 = fitz.Rect(50, 60, 200, 80)
    page1.insert_link({
        "kind": fitz.LINK_URI,
        "uri": "https://example.com/page1",
        "from": rect1,
    })
    
    # Page 2 with another link
    page2 = doc.new_page()
    page2.insert_text((50, 50), "Page 2 with link")
    rect2 = fitz.Rect(50, 60, 200, 80)
    page2.insert_link({
        "kind": fitz.LINK_URI,
        "uri": "https://docs.google.com/document/d/abc123",
        "from": rect2,
    })
    
    doc.save(str(pdf_path))
    doc.close()
    
    return str(pdf_path)


@pytest.fixture
def video_url() -> str:
    """Sample video URL for timestamp formatting."""
    return "https://drive.google.com/file/d/abc123/view"
