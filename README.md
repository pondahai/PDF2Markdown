# PDF 轉 Markdown 工具

這是一個 Web 應用程式，允許使用者上傳 PDF 文件，將其內容（通過直接文本提取和 OCR）發送給大型語言模型 (LLM)，並將 LLM 轉換後的 Markdown 結果流式顯示在前端。應用程式還會顯示 LLM 的「思考過程」。

![image](https://github.com/user-attachments/assets/382409f5-ef5f-46c4-acc3-5ea534d934f9)

## 功能

*   **PDF 上傳**: 使用者可以通過網頁介面選擇並上傳 PDF 文件。
*   **雙重文本提取**:
    *   使用 PyMuPDF (fitz) 進行直接文本提取。
    *   使用 Tesseract OCR (通過 pdf2image) 對 PDF 頁面進行光學字符識別，以處理掃描版或圖片型 PDF。
*   **LLM 整合**:
    *   將提取的文本內容發送給可配置的大型語言模型 (LLM) API。
    *   LLM 被指示先輸出其分析和轉換策略的「思考過程」（包裹在 `<think>` 標籤內）。
    *   然後，LLM 生成 PDF 內容的 Markdown 版本。
*   **流式輸出**:
    *   後端使用 Server-Sent Events (SSE) 將 LLM 的響應（思考過程和 Markdown）實時流式傳輸到前端。
    *   前端實時解析並使用 `marked.js` 渲染 Markdown 內容。
*   **用戶界面**:
    *   清晰地分離顯示 LLM 的「思考過程」和最終的「Markdown 結果」。
    *   提供上傳狀態、處理進度和加載指示。

## 技術棧

*   **後端**:
    *   Python
    *   Flask (Web 框架)
    *   PyMuPDF (PDF 文本提取)
    *   pdf2image (PDF 轉圖片，OCR 前置)
    *   Pytesseract (OCR 引擎接口)
    *   Requests (HTTP 客戶端，用於調用 LLM API)
    *   python-dotenv (環境變量管理)
*   **前端**:
    *   HTML5
    *   CSS3
    *   JavaScript (原生，用於文件上傳、SSE 處理、DOM 操作)
    *   Marked.js (Markdown 轉 HTML 渲染庫)
*   **外部依賴**:
    *   Poppler (pdf2image 的依賴)
    *   Tesseract OCR (pytesseract 的依賴)
    *   一個可訪問的大型語言模型 (LLM) API (例如本地部署的 LM Studio, Ollama, 或商業 API)

## 安裝與設置

### 1. 克隆倉庫

```bash
git clone <你的倉庫URL>
cd <倉庫目錄名>
```

### 2. 安裝外部系統依賴

此專案需要 Poppler 和 Tesseract OCR。請根據你的操作系統安裝它們：

*   **Poppler**:
    *   **Linux (Debian/Ubuntu)**: `sudo apt-get update && sudo apt-get install poppler-utils`
    *   **macOS (Homebrew)**: `brew install poppler`
    *   **Windows**:
        1.  從 [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases/) (或類似來源) 下載最新的二進制版本。
        2.  解壓並將其 `bin\` 目錄的路徑添加到系統的 `PATH` 環境變量中。

*   **Tesseract OCR**:
    *   **Linux (Debian/Ubuntu)**: `sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim tesseract-ocr-chi-tra` (安裝英文、簡體中文、繁體中文語言包，根據需要增減)
    *   **macOS (Homebrew)**: `brew install tesseract tesseract-lang` (然後根據需要安裝額外語言包)
    *   **Windows**:
        1.  從 [Tesseract at UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) 下載 Windows 安裝程序。
        2.  運行安裝程序，確保選擇安裝你需要的語言包（例如，English, Chinese - Simplified, Chinese - Traditional）。
        3.  將 Tesseract 的安裝目錄（例如 `C:\Program Files\Tesseract-OCR`）添加到系統的 `PATH` 環境變量中。

### 3. 創建並激活 Python 虛擬環境

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 4. 安裝 Python 依賴

```bash
pip install -r requirements.txt
```

### 5. 配置環境變量

創建一個名為 `.env` 的文件在專案的根目錄，並填入以下內容（根據你的實際情況修改）：

```env
# Tesseract 和 Poppler 路徑 (如果它們不在系統 PATH 中，或者你想指定特定版本)
# 在 Windows 上，路徑可能需要雙反斜線，例如: C:\\Program Files\\Tesseract-OCR\\tesseract.exe
TESSERACT_CMD="C:/Program Files/Tesseract-OCR/tesseract.exe" # 修改為你的 Tesseract OCR 可執行文件路徑
POPPLER_PATH="C:/path/to/poppler-xx.xx.x/bin" # 修改為你的 Poppler bin 文件夾路徑

# LLM API 配置
LLM_API_KEY="YOUR_LLM_API_KEY"                 # 你的 LLM API 密鑰 (例如 LM Studio 服務器預設 'Not_needed')
LLM_BASE_URL="http://localhost:1234/v1"      # 你的 LLM API 基礎 URL (例如 LM Studio 服務器地址)
LLM_MODEL_NAME="lmstudio-community/Meta-Llama-3-8B-Instruct-GGUF" # 你希望使用的 LLM 模型名稱
```

**注意**:
*   如果 Tesseract 和 Poppler 已經正確添加到系統 PATH，你可以將 `TESSERACT_CMD` 和 `POPPLER_PATH` 留空或註釋掉。
*   `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_NAME` 需要根據你使用的 LLM 服務進行配置。

### 6. 運行應用

```bash
python main.py
```

應用程式將默認運行在 `http://0.0.0.0:5000/` 或 `http://localhost:5000/`。在瀏覽器中打開此地址即可使用。

## 使用方法

1.  打開應用程式的網頁。
2.  點擊 "選擇 PDF 檔案" 按鈕，選擇一個本地 PDF 文件。
3.  文件名將顯示在按鈕下方。
4.  點擊 "開始轉換" 按鈕。
5.  觀察 "思考過程" 和 "Markdown 結果" 區域的實時更新。
6.  轉換完成後，你可以從 "Markdown 結果" 區域複製生成的 Markdown。

## 目錄結構 (簡化)

```
.
├── uploads/            # PDF 上傳後臨時存儲的目錄 (自動創建)
├── templates/
│   └── index.html      # 前端 HTML 模板
├── main.py             # Flask 後端應用邏輯
├── requirements.txt    # Python 依賴列表
├── .env                # 環境變量配置文件 (需手動創建)
└── README.md           # 本文件
```

## 未來可能的改進

*   允許用戶選擇 OCR 語言。
*   更詳細的錯誤處理和用戶反饋。
*   支持複製 Markdown 結果到剪貼板的按鈕。
*   進階的 Markdown 編輯或預覽功能。
*   對大型 PDF 文件的處理進行優化（例如，後台任務隊列）。
*   添加單元測試和集成測試。

## 貢獻

歡迎提交 Pull Requests 或 Issues 來改進此專案。

## 許可證

[MIT](LICENSE) (如果你選擇添加一個 LICENSE 文件)
