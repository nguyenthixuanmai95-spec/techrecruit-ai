import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
import json
import time

# Cấu hình trang Streamlit
st.set_page_config(
    page_title="TechRecruit AI - Hệ thống Sơ loại Ứng viên",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS để giao diện trông hiện đại và chuyên nghiệp hơn
st.markdown("""
    <style>
    /* Gradient background cho tiêu đề */
    .main-title {
        font-family: 'Inter', sans-serif;
        background: linear-gradient(90deg, #FF4B4B, #FF8F00);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }
    
    /* Subtitle */
    .subtitle {
        color: #808495;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Thiết kế thẻ Metric */
    .metric-container {
        background-color: #1E2235;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border: 1px solid #2D314D;
        transition: transform 0.3s ease;
        text-align: center;
    }
    
    .metric-container:hover {
        transform: translateY(-5px);
        border-color: #FF4B4B;
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 5px;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #A0AABF;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Alert styles */
    .alert-share {
        background-color: rgba(255, 75, 75, 0.1);
        border: 1px solid #FF4B4B;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1.5rem;
    }
    </style>
""", unsafe_allow_html=True)

# Khai báo các thông tin Google Sheets
SPREADSHEET_ID = "1809f84g270sunDzMSOwP7xNvIUZOR5gY-SReyd8JNuM"
CREDENTIALS_FILES = ["credentials.json.json", "credentials.json"]

# Hàm kết nối Google Sheet
def get_google_sheet(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    creds = None
    error_msg = ""
    for cred_file in CREDENTIALS_FILES:
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(cred_file, scope)
            break
        except Exception as e:
            error_msg = str(e)
            
    if not creds:
        raise FileNotFoundError(f"Không thể tải file credentials (đã thử cả credentials.json.json và credentials.json). Chi tiết: {error_msg}")
        
    client = gspread.authorize(creds)
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        return spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.APIError as e:
        if "403" in str(e) or "permission" in str(e).lower():
            # Trích xuất email service account để hiển thị cho người dùng
            try:
                with open(cred_file, 'r') as f:
                    cred_data = json.load(f)
                    client_email = cred_data.get("client_email", "Email Service Account")
            except:
                client_email = "Email Service Account của bạn"
            
            st.error("### 🛑 Lỗi phân quyền truy cập Google Sheets")
            st.markdown(f"""
            <div class="alert-share">
                <strong>Yêu cầu cấu hình:</strong> Tài khoản dịch vụ (Service Account) của bạn chưa được cấp quyền truy cập file Google Sheets này.<br>
                👉 Hãy mở file Google Sheets và <strong>Chia sẻ (Share)</strong> quyền chỉnh sửa (Editor) cho địa chỉ email sau:<br>
                <code style="font-size: 1.1rem; color: #FF4B4B;">{client_email}</code>
            </div>
            """, unsafe_allow_html=True)
        raise e

# Hàm chuẩn hóa và tìm index cột
def find_column_indices(headers):
    # Khai báo các từ khóa tìm kiếm cột tương ứng
    keywords_mapping = {
        "Họ tên": ["họ tên", "ho ten", "họ và tên", "ho va ten", "tên", "ten", "candidate name", "name"],
        "Kinh nghiệm": ["kinh nghiệm", "kinh nghiem", "năm kinh nghiệm", "nam kinh nghiem", "yoe", "experience"],
        "Kỹ năng": ["kỹ năng", "ky nang", "kỹ năng lập trình", "skills", "skill", "công nghệ", "cong nghe"],
        "Giới thiệu bản thân": ["giới thiệu", "gioi thieu", "giới thiệu bản thân", "gioi thieu ban than", "summary", "about", "introduction"],
        "Điểm số": ["điểm số", "diem so", "điểm", "diem", "score"],
        "Lý do": ["lý do", "ly do", "lý do chấm điểm", "lý do đánh giá", "reason"],
        "Đề xuất kết quả": ["đề xuất kết quả", "de xuat ket qua", "đề xuất", "de xuat", "decision", "result"],
        "Trạng thái phê duyệt": ["trạng thái phê duyệt", "trang thai phe duyet", "phê duyệt", "phe duyet", "status", "approval"]
    }
    
    indices = {}
    for col_name, keywords in keywords_mapping.items():
        found_idx = -1
        for idx, header in enumerate(headers):
            header_str = str(header).lower().strip()
            for kw in keywords:
                if kw == header_str or (len(kw) > 3 and kw in header_str):
                    found_idx = idx
                    break
            if found_idx != -1:
                break
        indices[col_name] = found_idx
        
    return indices

# Giao diện chính của Streamlit
st.markdown('<div class="main-title">🤖 TechRecruit AI</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Hệ thống sơ loại ứng viên tự động & phê duyệt trực tuyến kết nối Google Sheets</div>', unsafe_allow_html=True)

# Cấu hình thanh Sidebar
st.sidebar.header("⚙️ Cấu hình Hệ thống")

# Input API Key cho Gemini
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password", help="Nhập API Key của bạn để sử dụng AI Agent chấm điểm CV.")
if not gemini_api_key:
    st.sidebar.warning("⚠️ Vui lòng nhập Gemini API Key để kích hoạt AI Agent.")

# Chọn sheet làm việc
sheet_option = st.sidebar.selectbox(
    "Chọn dữ liệu ứng tuyển",
    ["Ung_Vien_Cong_Nghe", "Ho_So_Tin_Dung"],
    index=0
)

# Nút tải lại dữ liệu
refresh_btn = st.sidebar.button("🔄 Làm mới dữ liệu", use_container_width=True)

if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = 0

if refresh_btn:
    st.session_state.refresh_trigger += 1

# Đọc dữ liệu từ Google Sheets
@st.cache_data(show_spinner="Đang đọc dữ liệu ứng viên từ Google Sheets...", ttl=10)
def load_data(sheet_name, trigger):
    try:
        worksheet = get_google_sheet(sheet_name)
        all_records = worksheet.get_all_values()
        if not all_records:
            return pd.DataFrame(), [], None
            
        headers = all_records[0]
        rows = all_records[1:]
        
        # Tìm hoặc khởi tạo các cột cần thiết nếu chưa có
        indices = find_column_indices(headers)
        
        # Kiểm tra xem các cột kết quả đã tồn tại chưa, nếu chưa thì thêm vào sheet
        added_cols = []
        modified_headers = list(headers)
        
        for col in ["Điểm số", "Lý do", "Đề xuất kết quả", "Trạng thái phê duyệt"]:
            if indices[col] == -1:
                modified_headers.append(col)
                indices[col] = len(modified_headers) - 1
                added_cols.append(col)
                
        if added_cols:
            # Cập nhật dòng tiêu đề trên Google Sheets
            worksheet.update("1:1", [modified_headers])
            # Tải lại records sau khi update headers
            all_records = worksheet.get_all_values()
            headers = all_records[0]
            rows = all_records[1:]
            
        # Tạo DataFrame
        df = pd.DataFrame(rows, columns=headers)
        
        # Đảm bảo các hàng có đủ số cột
        for col in ["Điểm số", "Lý do", "Đề xuất kết quả", "Trạng thái phê duyệt"]:
            if col not in df.columns:
                df[col] = ""
                
        return df, headers, indices
    except Exception as e:
        st.error(f"Lỗi khi tải dữ liệu: {e}")
        return pd.DataFrame(), [], {}

df, headers, col_indices = load_data(sheet_option, st.session_state.refresh_trigger)

if not df.empty:
    # ----------------------------------------------------
    # BỘ CHỈ SỐ ĐO LƯỜNG (METRICS DASHBOARD)
    # ----------------------------------------------------
    # Chuẩn hóa dữ liệu điểm số
    df["Điểm số"] = pd.to_numeric(df["Điểm số"], errors="coerce").fillna(-1).astype(int)
    
    total_candidates = len(df)
    
    # Tính số đề xuất duyệt dựa trên cột 'Đề xuất kết quả' hoặc 'Điểm số' >= 70
    approved_candidates = len(df[
        (df["Đề xuất kết quả"].str.lower().str.strip() == "duyệt") | 
        (df["Điểm số"] >= 70)
    ])
    
    # Tính số bị loại
    rejected_candidates = len(df[
        (df["Đề xuất kết quả"].str.lower().str.strip() == "loại") | 
        ((df["Điểm số"] < 70) & (df["Điểm số"] >= 0))
    ])
    
    # Hiển thị chỉ số
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
            <div class="metric-container">
                <div class="metric-value">{total_candidates}</div>
                <div class="metric-label">Tổng hồ sơ</div>
            </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
            <div class="metric-container" style="border-left: 5px solid #2ECC71;">
                <div class="metric-value" style="color: #2ECC71;">{approved_candidates}</div>
                <div class="metric-label">Đề xuất duyệt (Điểm ≥ 70)</div>
            </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""
            <div class="metric-container" style="border-left: 5px solid #E74C3C;">
                <div class="metric-value" style="color: #E74C3C;">{rejected_candidates}</div>
                <div class="metric-label">Bị loại (Điểm < 70)</div>
            </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    
    # ----------------------------------------------------
    # BẢNG TƯƠNG TÁC PHÊ DUYỆT (HR INTERACTION)
    # ----------------------------------------------------
    st.subheader("📋 Bảng Checkpoint phê duyệt ứng viên")
    st.info("💡 Bạn có thể chỉnh sửa trực tiếp cột 'Trạng thái phê duyệt' trên bảng dưới đây, sau đó bấm nút 'Lưu thay đổi' phía dưới.")
    
    # Chuẩn hóa cột Trạng thái phê duyệt
    df["Trạng thái phê duyệt"] = df["Trạng thái phê duyệt"].apply(
        lambda x: x if x in ["Chờ xem xét", "Đồng ý phỏng vấn", "Từ chối"] else "Chờ xem xét"
    )
    
    # Hiển thị DataFrame cho phép sửa đổi cột Trạng thái phê duyệt
    # Tắt tính năng chỉnh sửa cho tất cả các cột ngoại trừ cột "Trạng thái phê duyệt"
    disabled_cols = [col for col in df.columns if col != "Trạng thái phê duyệt"]
    
    # Hiển thị bảng tương tác
    edited_df = st.data_editor(
        df,
        column_config={
            "Trạng thái phê duyệt": st.column_config.SelectboxColumn(
                label="Trạng thái phê duyệt (HR)",
                options=["Chờ xem xét", "Đồng ý phỏng vấn", "Từ chối"],
                required=True,
                width="medium"
            ),
            "Điểm số": st.column_config.NumberColumn(
                label="Điểm số (AI)",
                format="%d"
            ),
            "Lý do": st.column_config.TextColumn(
                label="Lý do chấm điểm (AI)",
                width="large"
            ),
            "Đề xuất kết quả": st.column_config.TextColumn(
                label="Đề xuất (AI)"
            )
        },
        disabled=disabled_cols,
        use_container_width=True,
        key="candidate_editor"
    )
    
    # Nút Lưu thay đổi trạng thái phê duyệt
    if st.button("💾 Lưu thay đổi trạng thái phê duyệt lên Google Sheets", type="primary"):
        # Tìm những hàng có sự thay đổi
        changed_rows = []
        for idx in range(len(df)):
            orig_val = df.iloc[idx]["Trạng thái phê duyệt"]
            new_val = edited_df.iloc[idx]["Trạng thái phê duyệt"]
            if orig_val != new_val:
                changed_rows.append((idx + 2, new_val)) # Dòng Google Sheets bắt đầu từ 2 (dòng 1 là tiêu đề)
                
        if changed_rows:
            try:
                worksheet = get_google_sheet(sheet_option)
                # Lấy số thứ tự cột Trạng thái phê duyệt (1-indexed)
                status_col_name = "Trạng thái phê duyệt"
                status_col_idx = headers.index(status_col_name) + 1
                
                with st.spinner("Đang lưu thay đổi lên Google Sheets..."):
                    # Thực hiện cập nhật từng ô thay đổi
                    for row_num, new_status in changed_rows:
                        worksheet.update_cell(row_num, status_col_idx, new_status)
                        time.sleep(0.5) # Tránh rate limit của Google API
                        
                st.success(f"🎉 Đã lưu thành công trạng thái phê duyệt cho {len(changed_rows)} ứng viên!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi khi cập nhật lên Google Sheets: {e}")
        else:
            st.info("Không có thay đổi nào cần lưu.")
            
    st.markdown("---")
    
    # ----------------------------------------------------
    # CHẠY AI AGENT LỌC CV
    # ----------------------------------------------------
    st.subheader("🤖 AI Agent Sơ loại CV tự động")
    
    col_ai1, col_ai2 = st.columns([3, 1])
    with col_ai1:
        re_run_all = st.checkbox("Chấm điểm lại toàn bộ danh sách (Mặc định chỉ chấm điểm cho hồ sơ mới chưa có điểm)")
    
    with col_ai2:
        run_ai_btn = st.button("🚀 Chạy AI Agent chấm điểm CV", type="secondary", use_container_width=True)
        
    if run_ai_btn:
        if not gemini_api_key:
            st.error("Vui lòng nhập Gemini API Key ở thanh bên trái trước khi chạy AI Agent.")
        else:
            try:
                # Cấu hình API Key
                genai.configure(api_key=gemini_api_key)
                # Sử dụng gemini-1.5-flash để xử lý nhanh và tối ưu chi phí
                model = genai.GenerativeModel("gemini-1.5-flash")
                
                # Xác định các hàng cần xử lý
                rows_to_process = []
                for idx in range(len(df)):
                    # Lấy điểm số cũ
                    old_score = df.iloc[idx]["Điểm số"]
                    # Nếu chạy lại toàn bộ hoặc chưa có điểm số (=-1 hoặc rỗng)
                    if re_run_all or old_score == -1 or pd.isna(df.iloc[idx]["Điểm số"]) or str(df.iloc[idx]["Điểm số"]).strip() == "":
                        rows_to_process.append(idx)
                        
                if not rows_to_process:
                    st.info("Không có ứng viên mới cần chấm điểm. Tích chọn 'Chấm điểm lại toàn bộ danh sách' nếu muốn chạy lại.")
                else:
                    worksheet = get_google_sheet(sheet_option)
                    
                    # Tìm index các cột đầu vào
                    idx_name = col_indices["Họ tên"]
                    idx_exp = col_indices["Kinh nghiệm"]
                    idx_skill = col_indices["Kỹ năng"]
                    idx_intro = col_indices["Giới thiệu bản thân"]
                    
                    # Lấy index cột đầu ra
                    idx_score_col = headers.index("Điểm số") + 1
                    idx_reason_col = headers.index("Lý do") + 1
                    idx_decision_col = headers.index("Đề xuất kết quả") + 1
                    
                    progress_text = "Đang xử lý hồ sơ ứng viên..."
                    progress_bar = st.progress(0, text=progress_text)
                    
                    success_count = 0
                    
                    for step, idx in enumerate(rows_to_process):
                        candidate_row = df.iloc[idx]
                        
                        # Lấy giá trị đầu vào an toàn
                        cand_name = candidate_row.iloc[idx_name] if idx_name != -1 else "Ứng viên không rõ tên"
                        cand_exp = candidate_row.iloc[idx_exp] if idx_exp != -1 else "Không khai báo"
                        cand_skill = candidate_row.iloc[idx_skill] if idx_skill != -1 else "Không khai báo"
                        cand_intro = candidate_row.iloc[idx_intro] if idx_intro != -1 else "Không khai báo"
                        
                        progress_bar.progress((step) / len(rows_to_process), text=f"Đang phân tích CV: {cand_name} ({step + 1}/{len(rows_to_process)})")
                        
                        # Xây dựng prompt
                        prompt = f"""
Bạn là AI Agent chấm điểm CV chuyên nghiệp cho bộ phận tuyển dụng V-Tech.
Nhiệm vụ của bạn là đánh giá ứng viên dựa trên thông tin sau:
- Họ và tên: {cand_name}
- Kinh nghiệm làm việc: {cand_exp}
- Kỹ năng lập trình/Công nghệ: {cand_skill}
- Giới thiệu bản thân: {cand_intro}

Tiêu chí chấm điểm (Điểm khởi điểm là 0 điểm):
1. Kinh nghiệm làm việc từ 3 năm trở lên: Cộng 40 điểm (Nếu dưới 3 năm thì cộng 0 điểm).
2. Có kỹ năng lập trình Python hoặc React: Cộng 30 điểm (Nếu không có cả 2 thì cộng 0 điểm).
3. Có phần giới thiệu bản thân rõ ràng, mạch lạc: Cộng 30 điểm (Nếu quá sơ sài hoặc không rõ ràng thì cộng ít hơn hoặc 0 điểm).

Hãy trả về kết quả dưới định dạng JSON duy nhất với cấu trúc sau:
{{
  "score": <điểm số từ 0 đến 100>,
  "reason": "<lý do chấm điểm chi tiết cụ thể cho từng kỹ năng và kinh nghiệm của ứng viên>",
  "decision": "<'Duyệt' nếu score >= 70, ngược lại ghi là 'Loại'>"
}}
Chú ý: Chỉ trả về JSON, không bao gồm ký tự ```json ở đầu hoặc cuối.
"""
                        try:
                            # Gọi API
                            response = model.generate_content(
                                prompt,
                                generation_config={"response_mime_type": "application/json"}
                            )
                            
                            # Parse JSON kết quả
                            res_data = json.loads(response.text)
                            score = res_data.get("score", 0)
                            reason = res_data.get("reason", "Không có lý do")
                            decision = res_data.get("decision", "Loại")
                            
                            # Dòng trên Google Sheets (1-indexed, dòng đầu là header -> cộng thêm 2)
                            row_num = idx + 2
                            
                            # Ghi dữ liệu vào Google Sheet
                            worksheet.update_cell(row_num, idx_score_col, score)
                            worksheet.update_cell(row_num, idx_reason_col, reason)
                            worksheet.update_cell(row_num, idx_decision_col, decision)
                            
                            success_count += 1
                            time.sleep(0.5) # Delay nhẹ để tránh rate limit
                            
                        except Exception as inner_e:
                            st.warning(f"Lỗi khi xử lý ứng viên {cand_name}: {inner_e}")
                            time.sleep(1)
                            
                    progress_bar.progress(1.0, text="Hoàn thành phân tích!")
                    st.success(f"🎉 Đã sơ loại thành công {success_count}/{len(rows_to_process)} ứng viên!")
                    
                    # Clear cache và tải lại
                    st.cache_data.clear()
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Đã xảy ra lỗi khi chạy AI Agent: {e}")
else:
    st.warning("⚠️ Không thể tải dữ liệu hoặc Sheet rỗng. Vui lòng kiểm tra lại quyền truy cập của Service Account.")
