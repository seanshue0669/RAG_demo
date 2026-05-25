# CLAUDE.md

本檔案是 Claude Code 在此專案中生成程式碼時必須遵守的約束規則。

## 專案背景

這是一個 RAG 安全性 demo 專案，部署在 NVIDIA DGX GB10（ARM64, 128GB unified memory）上。目的是展示企業 RAG 系統在檢索層、生成層、儲存層的安全漏洞與防禦方案。

完整規格請參考 docs/ 下的 spec 文件。

## 環境約束

- Python 環境：使用獨立 Conda 環境，不可依賴系統層級的套件
- 架構：ARM64。選擇依賴時需確認 ARM64 相容性
- TenSEAL 如果無法透過 pip 安裝，需從 source build
- 不使用容器化部署，直接在 Conda 環境中運行
- 前後端分離，前端透過 HTTP API 呼叫後端

## 程式碼風格

- 語言：Python 3.10+，使用 type hints
- 非同步：FastAPI 端點使用 async def
- 設定集中管理：所有路徑、URL、參數都從 config/settings.py 讀取，不可在模組中 hardcode
- 每個模組的 public interface（類別名稱、函式簽名）以 spec 為準，不可自行更改
- Pydantic 用於所有 request/response model
- 錯誤處理：FastAPI 端點層統一處理，內部模組用 exception 上拋

## 資料層規則

- 所有假資料用 Faker 的 zh_TW locale 生成，輸出為繁體中文
- 每筆文件必須附帶完整 metadata（doc_id, doc_type, department, security_level, text）
- security_level 的正確性是整個權限機制的根基，生成時必須確保標記正確
- Poisoned 文件的 security_level 必須為 1

## ChromaDB 規則

- 持久化路徑：backend/vectordb/db_data/
- insert 時必須同時寫入 embedding 和完整 metadata
- query_with_filter 的 security_level 條件為「小於等於」（向下包含），不是「等於」

## RAG Pipeline 規則

- 角色到 security_level 的對應：employee → 1, manager → 2, hr_admin → 3
- 對應邏輯是「該角色可存取 security_level <= 自身等級的所有文件」
- generator 必須同時支援 llm 和 scripted 兩種 mode，透過參數切換
- llm mode 接現有 vLLM endpoint（URL 從 settings.py 讀取）
- scripted mode 從 data/prerecorded/prompt_injection_responses.json 匹配回應
- pipeline 的 gen_mode 預設為 llm，fallback 邏輯：vLLM 連線失敗時自動降級為 scripted

## LLM 整合規則

- 透過 HTTP 呼叫現有 vLLM endpoint，不要在本專案內啟動 LLM 服務
- 只需基本 completion，不使用 tool calling 或 thinking mode
- System prompt 不可過度嚴格。第三幕需要展示 prompt injection 攻擊成功的場景，如果 system prompt 的安全護欄太強會導致攻擊無法演示
- Prompt 組裝格式：system prompt + 檢索到的文件作為 context + 使用者的 query

## 同態加密規則

- CKKS poly_modulus_degree 固定為 8192
- 所有 embedding 在 seed 階段預先加密，加密後存在記憶體中
- 加密搜尋的每個步驟必須獨立計時（encrypt_query、compute_similarity、decrypt），不可只記錄總耗時
- 同時回傳加密搜尋結果和明文搜尋結果，供前端對比
- CKKS 的近似計算特性會導致相似度分數與明文版本有微小差異，這是預期行為，不需要對齊

## Vec2Text 規則

- 逆向結果為預錄 JSON，不在 demo 執行期間即時計算
- scripts/prepare_vec2text.py 負責生成預錄結果，與 demo 主流程分離
- 預錄結果必須包含：原始文字、逆向還原文字、PII 匹配分析
- 選擇展示案例時，優先選短文件和自然語言 PII（姓名、部門、職稱），避免以數字型 PII（身分證字號、電話）作為主要展示

## API 規則

- /api/query 的所有參數由前端決定
- /api/demo/{act} 的參數由後端預設，每個 act 有固定的 query、角色、filter 設定
- 兩組端點共用同一個 pipeline 實例
- Response 中的 retrieved_docs 必須包含 doc_id, text, security_level, similarity

## 前端規則

- 登入頁面提供角色下拉選單，不實作真正的認證邏輯
- 進入 demo 後角色仍可切換
- 第四幕時 SystemLog 區域替換為 HEDashboard
- MessageBubble 需支援 PII 標紅顯示

## 檔案與路徑

- 生成的假資料 JSON 存放於 data/generated/
- 預錄結果存放於 data/prerecorded/
- ChromaDB 持久化資料存放於 backend/vectordb/db_data/
- 以上三個路徑加入 .gitignore