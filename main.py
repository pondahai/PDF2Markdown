import os
import uuid
import json # Needed for requests
import requests # New import
from flask import Flask, request, render_template, jsonify, Response, stream_with_context
from dotenv import load_dotenv
import fitz # PyMuPDF for text extraction
from pdf2image import convert_from_path
import pytesseract
# import openai # No longer directly needed for LLM call if using requests
import tempfile

# Load environment variables
load_dotenv()

# --- Configuration ---
TESSERACT_CMD = os.getenv("TESSERACT_CMD")
POPPLER_PATH = os.getenv("POPPLER_PATH")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL") # e.g., "http://ubuntu:1234/v1"
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")

# Configure pytesseract
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# --- Flask App Initialization ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Helper Functions (extract_text_from_pdf, ocr_pdf - unchanged) ---
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text("text")
        doc.close()
    except Exception as e:
        print(f"Error extracting text with PyMuPDF: {e}")
        return f"[Error extracting text with PyMuPDF: {e}]"
    return text

def ocr_pdf(pdf_path, lang='eng+chi_sim+chi_tra'):
    ocr_text = ""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            images = convert_from_path(pdf_path, output_folder=temp_dir, poppler_path=POPPLER_PATH)
            for i, image in enumerate(images):
                try:
                    temp_image_path = os.path.join(temp_dir, f"page_{i}.png")
                    image.save(temp_image_path, "PNG")
                    ocr_text += pytesseract.image_to_string(temp_image_path, lang=lang) + "\n\n"
                except Exception as e:
                    print(f"Error OCRing page {i}: {e}")
                    ocr_text += f"[Error OCRing page {i}: {e}]\n\n"
    except Exception as e:
        print(f"Error converting PDF to images or during OCR: {e}")
        return f"[Error during PDF to image conversion or OCR: {e}]"
    return ocr_text
# --- LLM Call using requests ---
def call_llm_stream_with_requests(text_content):
    """Calls the LLM API using requests with streaming and custom headers."""
    
    api_url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream", # Important for server to know client expects SSE
        "ngrok-skip-browser-warning": "true" # Your custom header
    }

    system_prompt = """你是一個專業的PDF文件分析助手。
你的任務是分析提供的PDF提取內容（可能包含純文字提取和OCR提取的結果），理解其結構和內容，並將其轉換為格式良好、易於閱讀的Markdown。
在生成Markdown之前，請先輸出一組`<think></think>`標籤，在其中描述你的分析過程、內容理解、版型預測和Markdown生成策略。
這個思考過程只出現在最開始。
例如：
<think>
1.  **文件類型分析**：這是一份技術報告/學術論文/產品手冊...
2.  **主要內容識別**：識別了主要章節標題，如引言、方法、結果、結論...
3.  **結構預測**：預計使用 H1 作為文檔標題，H2 作為主要章節標題，H3 作為子章節標題。列表將使用無序或有序列表。程式碼塊將使用反引號包裹。圖片（如果信息中包含圖片描述）將使用 Markdown 圖片語法。
4.  **特殊元素處理**：注意到有表格，將嘗試使用 Markdown 表格語法呈現。有腳註或參考文獻，將嘗試保留其標識。
5.  **Markdown生成策略**：將按順序處理文本塊，應用預測的標題層級，轉換列表、表格等。
</think>
接下來，直接生成Markdown內容，不要有任何額外的解釋或開場白。
確保Markdown的語法正確且排版清晰。
"""
    user_prompt_content = f"""以下是從PDF文件中提取的內容，包含了純文字提取和OCR提取的結果。請分析這些內容並將其轉換為Markdown。

[純文字提取結果開始]
{text_content['direct_text']}
[純文字提取結果結束]

[OCR提取結果開始]
{text_content['ocr_text']}
[OCR提取結果結束]

請嚴格按照上述指示，先輸出`<think>`思考過程，然後輸出Markdown結果。
"""

    payload = {
        "model": LLM_MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt_content}
        ],
        "stream": True
    }

    try:
        # Using requests.post with stream=True
        response = requests.post(api_url, headers=headers, json=payload, stream=True, timeout=180) # Added timeout
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

        # Iterate over the response content line by line
        # LLM streaming responses are typically Server-Sent Events (SSE)
        for line_bytes in response.iter_lines():
            if line_bytes:
                line_str = line_bytes.decode('utf-8')
                # print(f"LLM Raw Stream Line: {line_str}") # Debug: LLM's own SSE line

                if line_str.startswith("data: "):
                    data_json_str = line_str[6:] # Remove "data: " prefix
                    if data_json_str.strip() == "[DONE]": # OpenAI specific stream end
                        # print("LLM Stream indicated [DONE]")
                        break # Stop processing if LLM signals [DONE]
                    
                    try:
                        # Parse the JSON data part of the SSE message from LLM
                        data_obj = json.loads(data_json_str)
                        if isinstance(data_obj, dict) and data_obj.get("choices"):
                            delta = data_obj["choices"][0].get("delta", {})
                            original_content_piece = delta.get("content")

                        if original_content_piece is not None:
                            # print(f"LLM Raw original_content_piece: '{original_content_piece}' (len: {len(original_content_piece)})") # <--- 關鍵調試打印
                            final_sse_lines = []
                            
                            # --- 修改開始：簡化 original_content_piece 的處理 ---
                            # 移除針對 "\n" 和 "" 的特殊 if/elif 條件句
                            # 通用邏輯可以正確處理這些情況
                            lines_from_llm = original_content_piece.split('\n')
                            for l_idx, l_content in enumerate(lines_from_llm):
                                # 如果 l_content 是空字符串 (例如，來自 "\n".split('\n') -> ["", ""] 或原始空字符串)
                                # f"data: {l_content}\n" 將正確生成 "data: \n"
                                final_sse_lines.append(f"data: {l_content}\n")
                            # --- 修改結束 ---

                            
                           
                            if final_sse_lines:
                                # Join all "data: <line>\n" parts and add the final "\n" for SSE event termination
                                sse_event_to_frontend = "".join(final_sse_lines) + "\n" 
                                # print(f"Sending to frontend: '{sse_event_to_frontend}' (Original: '{original_content_piece}')")
                                yield sse_event_to_frontend

                    except json.JSONDecodeError as je:
                        # print(f"JSON Decode Error for LLM data: {data_json_str} - {je}")
                        # Might be a non-JSON message or malformed.
                        # If it's not "[DONE]", it could be an error message or something else.
                        # For simplicity, we'll ignore non-JSON data lines unless they are [DONE]
                        pass
                # Empty lines in SSE stream are delimiters, ignore here as we process line by line
    
    except requests.exceptions.RequestException as e:
        print(f"LLM API Request Error: {e}")
        yield f"data: [LLM_REQUEST_ERROR] {str(e)}\n\n"
    except Exception as e:
        print(f"LLM Stream Processing Error: {e}")
        yield f"data: [LLM_STREAM_ERROR] {str(e)}\n\n"
    finally:
        yield f"data: [STREAM_END]\n\n" # Our signal to the client

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'pdfFile' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['pdfFile']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and file.filename.endswith('.pdf'):
        # ... (file saving logic - unchanged) ...
        filename = str(uuid.uuid4()) + ".pdf"
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(pdf_path)

        direct_text = extract_text_from_pdf(pdf_path)
        # print("--- Direct Text Extracted ---")
        ocr_text = ocr_pdf(pdf_path)
        # print("--- OCR Text Extracted ---")

        combined_content = {
            "direct_text": direct_text,
            "ocr_text": ocr_text
        }
        
        # Use the new function for LLM call
        response_stream = Response(stream_with_context(call_llm_stream_with_requests(combined_content)), mimetype='text/event-stream')
        response_stream.headers['Cache-Control'] = 'no-cache'
        response_stream.headers['X-Accel-Buffering'] = 'no'
        return response_stream
    else:
        return jsonify({"error": "Invalid file type, please upload a PDF"}), 400

if __name__ == '__main__':
    if POPPLER_PATH and POPPLER_PATH not in os.environ['PATH']:
         os.environ['PATH'] += os.pathsep + POPPLER_PATH
         # print(f"Temporarily added {POPPLER_PATH} to PATH for this session.")
    app.run(debug=True, host='0.0.0.0', port=5000)