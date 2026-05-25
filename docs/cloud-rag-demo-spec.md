# Cloud RAG Security Demo — 專案規格書（Implementation Spec）

> 本文件用於指導 Claude Code / Codex 實作整個 demo 專案。

---

## 一、專案概述

**專案名稱**：cloud-rag-security-demo
**目的**：展示企業 RAG 系統在檢索層、生成層、儲存層的安全漏洞與防禦方案
**場景**：虛構公司 NovaTech Corp 的 HR RAG 知識庫
**呈現方式**：React 前端 + Python 後端（FastAPI），支援四幕攻擊劇本展示

---

## 二、技術棧

### Backend（Python）

| 用途 | 工具 | 版本建議 |
|------|------|----------|
| Web framework | FastAPI | >=0.100 |
| 假資料生成 | Faker | >=20.0 |
| Embedding model | sentence-transformers（`gtr-t5-base`） | >=2.2 |
| 向量資料庫 | ChromaDB | >=0.4 |
| 同態加密 | TenSEAL | >=0.3 |
| LLM（可選） | ollama / vllm / 預錄腳本 | — |
| ASGI server | uvicorn | >=0.20 |

### Frontend（React）

| 用途 | 工具 |
|------|------|
| Framework | React 18+ |
| Styling | Tailwind CSS |
| HTTP client | fetch / axios |
| 動畫（可選） | framer-motion |

---

## 三、資料夾結構

```
cloud-rag-security-demo/
│
├── README.md                          # 專案說明
├── docker-compose.yml                 # 可選：一鍵啟動
│
├── backend/
│   ├── requirements.txt
│   ├── main.py                        # FastAPI 入口
│   │
│   ├── config/
│   │   └── settings.py                # 全域設定（模型路徑、DB 路徑、參數等）
│   │
│   ├── data_gen/
│   │   ├── __init__.py
│   │   ├── generate_employees.py      # 員工個資（Level 3）
│   │   ├── generate_internal_docs.py  # 部門內部文件（Level 2）
│   │   ├── generate_public_docs.py    # 公開政策文件（Level 1）
│   │   ├── generate_poisoned_docs.py  # 含 prompt injection payload 的文件
│   │   ├── templates/                 # 文件模板（自然語言段落模板）
│   │   │   ├── employee_profile.txt
│   │   │   ├── performance_review.txt
│   │   │   ├── policy_document.txt
│   │   │   └── poisoned_policy.txt
│   │   └── run_all.py                 # 一鍵生成所有假資料 → 輸出 JSON
│   │
│   ├── embedding/
│   │   ├── __init__.py
│   │   ├── embedder.py                # 封裝 sentence-transformers 模型
│   │   └── batch_embed.py             # 批次對所有文件生成 embedding
│   │
│   ├── vectordb/
│   │   ├── __init__.py
│   │   ├── chroma_store.py            # ChromaDB 封裝：insert / query / query_with_filter
│   │   ├── seed_db.py                 # 初始化：生成資料 → embedding → 寫入 ChromaDB
│   │   └── db_data/                   # ChromaDB 持久化資料（gitignore）
│   │
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── retriever.py               # 檢索邏輯：接受 query + user_role → 回傳 top-k 文件
│   │   ├── generator.py               # 生成邏輯：接受 context + query → 回傳答案
│   │   │                              #   - 支援兩種 mode：llm / scripted
│   │   └── pipeline.py                # 完整 RAG pipeline：query → retrieve → generate
│   │
│   ├── attacks/
│   │   ├── __init__.py
│   │   ├── retrieval_bypass.py        # 第二幕：無 filter 搜尋 vs 有 filter 搜尋
│   │   ├── prompt_injection.py        # 第三幕：觸發 poisoned doc 的攻擊流程
│   │   └── embedding_inversion.py     # 第四幕：Vec2Text 逆向（預錄結果 loader）
│   │
│   ├── defenses/
│   │   ├── __init__.py
│   │   ├── metadata_filter.py         # 第二幕防禦：metadata-based access control
│   │   ├── prompt_guard.py            # 第三幕防禦（可選）：input/output 過濾
│   │   └── he_search/                 # 第四幕防禦：同態加密搜尋
│   │       ├── __init__.py
│   │       ├── ckks_engine.py         # TenSEAL CKKS 封裝：加密 / 解密 / encrypted dot product
│   │       ├── encrypted_store.py     # 加密向量儲存：明文 embedding → CKKS 加密 → 儲存
│   │       └── encrypted_search.py    # 加密搜尋流程：加密 query → 密文相似度計算 → 解密 top-k
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes_query.py            # POST /api/query — 主要 RAG 查詢端點
│   │   ├── routes_demo.py             # POST /api/demo/{act} — demo 控制端點（切幕、切角色）
│   │   ├── routes_he.py               # POST /api/he/search — 同態加密搜尋端點
│   │   └── schemas.py                 # Pydantic request/response models
│   │
│   └── scripts/
│       ├── setup.sh                   # 環境初始化腳本
│       ├── seed.py                    # 生成資料 + embedding + 寫入 DB
│       └── benchmark_he.py            # CKKS 效能測試腳本
│
├── frontend/
│   ├── package.json
│   ├── tailwind.config.js
│   ├── public/
│   │   └── index.html
│   └── src/
│       ├── App.jsx                    # 主入口 + 路由
│       ├── index.jsx
│       │
│       ├── components/
│       │   ├── ChatWindow.jsx         # RAG 對話介面
│       │   ├── MessageBubble.jsx      # 單則訊息（支援標紅 PII、顯示 metadata）
│       │   ├── UserRoleSwitcher.jsx   # 切換使用者身份（一般員工 / 主管 / HR）
│       │   ├── ActNavigation.jsx      # 切換幕（第一幕 ~ 第四幕）
│       │   ├── SystemLog.jsx          # 側欄：顯示檢索到的文件、filter 狀態、加密狀態
│       │   ├── SecuritySpectrum.jsx   # 安全性光譜視覺化
│       │   └── HEDashboard.jsx        # 同態加密 demo 面板（顯示加密/搜尋/解密耗時）
│       │
│       ├── hooks/
│       │   ├── useQuery.js            # 發送 RAG 查詢
│       │   └── useDemo.js             # demo 控制（切幕、切角色）
│       │
│       ├── pages/
│       │   ├── DemoPage.jsx           # 主 demo 頁面（整合所有元件）
│       │   └── OverviewPage.jsx       # 可選：RAG 架構說明頁
│       │
│       └── styles/
│           └── globals.css
│
├── data/
│   ├── generated/                     # faker 生成的原始 JSON 資料
│   │   ├── employees.json
│   │   ├── internal_docs.json
│   │   ├── public_docs.json
│   │   └── poisoned_docs.json
│   │
│   ├── prerecorded/                   # 預錄結果（用於不需要 live 計算的展示）
│   │   ├── vec2text_attack_results.json       # 第四幕：embedding 逆向結果
│   │   ├── vec2text_encrypted_fail.json       # 第四幕：加密後逆向失敗結果
│   │   └── prompt_injection_responses.json    # 第三幕（備用）：預錄 LLM 回應
│   │
│   └── embeddings/                    # 預計算的 embedding（可選，加速啟動）
│       └── all_embeddings.npy
│
└── docs/
    ├── demo-design.md                 # Demo 設計文件（已完成）
    ├── api-spec.md                    # API 端點詳細規格
    └── presentation-script.md         # 口頭報告劇本（待完成）
```

---

## 四、模組功能說明

### 4.1 data_gen — 假資料生成

**目標**：用 faker 生成自然語言段落形式的 HR 文件。

**員工個資模板範例**（`templates/employee_profile.txt`）：
```
員工 {name}（編號 {emp_id}）任職於{department}，職稱為{title}。
目前年薪為新台幣 {salary} 萬元，到職日為 {start_date}。
身份證字號為 {ssn}，聯絡電話 {phone}，居住地址為{address}。
緊急聯絡人為{emergency_name}（關係：{emergency_relation}），電話 {emergency_phone}。
```

**每筆資料需要附帶 metadata**：
```json
{
  "doc_id": "EMP-0042",
  "doc_type": "employee_record",
  "department": "finance",
  "security_level": 3,
  "text": "員工張小明（編號 EMP-0042）任職於財務部..."
}
```

**資料量**：
- 員工個資：50 筆（Level 3）
- 部門內部文件：20 筆（Level 2）
- 公開政策文件：15 筆（Level 1）
- Poisoned 文件：3 筆（Level 1，內嵌 prompt injection payload）

### 4.2 embedding — 向量化

**模型**：`sentence-transformers/gtr-t5-base`（512 維）
**批次處理**：一次處理所有文件，輸出 numpy array 或直接寫入 ChromaDB

### 4.3 vectordb — ChromaDB 封裝

**核心 API**：
```python
class ChromaStore:
    def insert(self, doc_id, text, embedding, metadata): ...
    def query(self, query_embedding, top_k=5): ...
    def query_with_filter(self, query_embedding, top_k=5, security_level=None): ...
    def get_raw_embedding(self, doc_id) -> list[float]: ...  # 給第四幕用
```

### 4.4 rag — 檢索 + 生成 pipeline

**Retriever**：
```python
def retrieve(query: str, user_role: str, use_filter: bool = True) -> list[Document]:
    # 1. query → embedding
    # 2. 根據 user_role 決定 security_level
    # 3. 如果 use_filter=True，用 query_with_filter；否則用 query
    # 4. 回傳 top-k 文件
```

**Generator**：
```python
def generate(query: str, context_docs: list[Document], mode: str = "scripted") -> str:
    # mode="scripted": 從預錄回應中匹配
    # mode="llm": 呼叫 local LLM（ollama API）
```

**Pipeline**：
```python
def run(query: str, user_role: str, use_filter: bool, gen_mode: str) -> RAGResponse:
    docs = retrieve(query, user_role, use_filter)
    answer = generate(query, docs, gen_mode)
    return RAGResponse(answer=answer, retrieved_docs=docs, metadata=...)
```

### 4.5 attacks — 攻擊模組

**retrieval_bypass.py**：
- 同一個 query，分別用 `use_filter=False` 和 `use_filter=True` 呼叫 pipeline
- 回傳兩組結果供前端對比顯示

**prompt_injection.py**：
- 確保 poisoned doc 在 Level 1 中被檢索到
- 呼叫 generator（mode=llm），觀察 LLM 回應是否包含非授權資訊

**embedding_inversion.py**：
- 從 ChromaDB 取出一筆 embedding
- 載入預錄的 Vec2Text 逆向結果
- 回傳原文 vs 逆向文字 vs PII 匹配結果

### 4.6 defenses/he_search — 同態加密搜尋

**ckks_engine.py**：
```python
class CKKSEngine:
    def __init__(self, poly_modulus_degree=8192, ...):
        # 初始化 TenSEAL context
    
    def encrypt_vector(self, plaintext_vector: list[float]) -> ts.CKKSVector: ...
    def encrypted_dot_product(self, enc_v1, enc_v2) -> ts.CKKSVector: ...
    def decrypt_scalar(self, enc_scalar) -> float: ...
```

**encrypted_store.py**：
```python
class EncryptedStore:
    def __init__(self, ckks_engine, embeddings: dict[str, list[float]]):
        # 預先加密所有 embedding 並存在記憶體中
    
    def encrypt_all(self) -> None: ...
    def get_encrypted_embedding(self, doc_id) -> ts.CKKSVector: ...
```

**encrypted_search.py**：
```python
def encrypted_search(
    query_embedding: list[float],
    encrypted_store: EncryptedStore,
    ckks_engine: CKKSEngine,
    top_k: int = 5
) -> EncryptedSearchResult:
    # 1. 加密 query embedding（計時）
    # 2. 對每筆加密 embedding 做 encrypted dot product（計時）
    # 3. 解密所有相似度分數（計時）
    # 4. 排序取 top-k
    # 5. 回傳結果 + 各步驟耗時
```

### 4.7 api — FastAPI 端點

**POST /api/query**：
```json
// Request
{
  "query": "張小明的薪資是多少？",
  "user_role": "employee",      // employee | manager | hr_admin
  "use_filter": true,
  "gen_mode": "scripted"         // scripted | llm
}

// Response
{
  "answer": "...",
  "retrieved_docs": [
    {"doc_id": "EMP-0042", "text": "...", "security_level": 3, "similarity": 0.87}
  ],
  "filter_applied": true
}
```

**POST /api/demo/{act}**：
```json
// act = "act1" | "act2_no_filter" | "act2_with_filter" | "act3" | "act4_attack" | "act4_defense"
// 每個 act 有預設的 query、角色、設定
// 回傳該幕的完整展示資料

// Response
{
  "act": "act2_no_filter",
  "query": "張小明的薪資是多少？",
  "user_role": "employee",
  "result": { ... },
  "narration": "一般員工在無存取控制的情況下查詢..."
}
```

**POST /api/he/search**：
```json
// Request
{
  "query": "張小明的薪資",
  "top_k": 5
}

// Response
{
  "results": [
    {"doc_id": "EMP-0042", "similarity": 0.85, "text": "..."}
  ],
  "timing": {
    "encrypt_query_ms": 680,
    "compute_similarity_ms": 3200,
    "decrypt_ms": 340,
    "total_ms": 4220
  },
  "plaintext_results": [
    {"doc_id": "EMP-0042", "similarity": 0.87, "text": "..."}
  ],
  "plaintext_timing_ms": 12
}
```

---

## 五、前端元件說明

### DemoPage.jsx — 主頁面佈局

```
┌─────────────────────────────────────────────────────┐
│  [ActNavigation]  第一幕 | 第二幕 | 第三幕 | 第四幕  │
├──────────────────────────┬──────────────────────────┤
│                          │                          │
│   [ChatWindow]           │   [SystemLog]            │
│                          │                          │
│   使用者輸入 / AI 回應    │   - 檢索到的文件列表      │
│                          │   - metadata / filter 狀態│
│                          │   - 加密狀態              │
│                          │   - 耗時資訊              │
│                          │                          │
├──────────────────────────┴──────────────────────────┤
│  [UserRoleSwitcher]  一般員工 | 部門主管 | HR 管理員   │
└─────────────────────────────────────────────────────┘
```

第四幕時，SystemLog 區域替換為 [HEDashboard]，顯示加密搜尋的即時狀態和計時。

### 關鍵互動邏輯

1. 切換幕 → 前端自動設定對應的角色、filter 狀態、query 建議
2. 第二幕有 toggle 開關：「啟用存取控制」on/off → 即時對比
3. 第四幕分三個 tab：攻擊 | 加密搜尋 | 安全性光譜

---

## 六、啟動流程

```bash
# 1. 安裝依賴
cd backend && pip install -r requirements.txt
cd frontend && npm install

# 2. 生成假資料 + embedding + 寫入 ChromaDB
cd backend && python scripts/seed.py

# 3. 啟動後端
cd backend && uvicorn main:app --reload --port 8000

# 4. 啟動前端
cd frontend && npm run dev
```

---

## 七、實作優先順序

**Phase 1 — 核心 RAG（先讓系統跑起來）**
1. data_gen：faker 生成所有假資料
2. embedding：批次向量化
3. vectordb：ChromaDB 封裝 + seed
4. rag/retriever：基本搜尋
5. api/routes_query：基本查詢端點
6. 前端：ChatWindow + 基本 query

**Phase 2 — 攻擊展示**
7. attacks/retrieval_bypass：有 filter vs 無 filter
8. attacks/prompt_injection：poisoned doc 攻擊
9. attacks/embedding_inversion：預錄結果載入
10. 前端：ActNavigation + UserRoleSwitcher + SystemLog

**Phase 3 — 同態加密防禦**
11. defenses/he_search/ckks_engine：TenSEAL 封裝
12. defenses/he_search/encrypted_store + encrypted_search
13. api/routes_he：加密搜尋端點
14. 前端：HEDashboard

**Phase 4 — 收尾**
15. 前端：SecuritySpectrum 視覺化
16. rag/generator：接 local LLM（如果要 live）或完善預錄腳本
17. 整體 UI 打磨
18. 撰寫口頭報告劇本

---

## 八、注意事項

- 所有假資料使用 `faker` 的 `zh_TW` locale 生成繁體中文
- embedding model 第一次載入會下載模型，需要網路
- TenSEAL 只支援 CPU 運算，CKKS 加密搜尋會比明文搜尋慢很多（這正是 demo 要展示的）
- ChromaDB 預設持久化到 `backend/vectordb/db_data/`，可以 git ignore
- 前端和後端分開跑，前端透過 API 呼叫後端
- demo 當天建議提前跑好 seed，不要現場生成資料
