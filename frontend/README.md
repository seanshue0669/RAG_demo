# Cloud RAG Security Demo — Frontend

React + Vite + Tailwind CSS 前端骨架。

## 環境需求

- Node.js 18+
- 後端 API 預設於 `http://localhost:8000`（可透過 `VITE_API_BASE_URL` 覆寫）

## 啟動

```bash
# 安裝依賴
npm install

# 開發模式（http://localhost:5173）
npm run dev

# 正式建置
npm run build

# 預覽建置結果
npm run preview
```

開發伺服器已設定 proxy：所有 `/api/*` 請求會自動轉送到 `http://localhost:8000`，因此不需要處理 CORS。

## 環境變數

於 `frontend/.env.local` 設定（不會進版控）：

```
VITE_API_BASE_URL=http://localhost:8000
```

`src/config.js` 會匯出 `API_BASE_URL`，元件呼叫後端時請從這裡取得。

## 目錄結構

```
frontend/
├── index.html              Vite entry
├── package.json
├── vite.config.js          dev server + /api proxy
├── tailwind.config.js
├── postcss.config.js
└── src/
    ├── main.jsx            React 入口
    ├── App.jsx             App shell（後續 wave 會掛載 DemoPage）
    ├── config.js           API_BASE_URL 等設定
    └── styles/
        └── globals.css     Tailwind directives + base styles
```
