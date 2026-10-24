# 即時資料分析與監控系統

Realtime Monitoring System

以 **FastAPI + Streamlit + MariaDB** 建立的監控系統，提供 JWT 使用者認證、角色權限、資料 CRUD、CSV／JSON 匯入、WebSocket 即時推送、統計分析與 Excel 匯出。資料存取使用 **SQLAlchemy ORM + asyncmy**，資料表透過 Alembic 管理，並以 Docker Compose 編排三個服務。

> **驗證紀錄：2026-10-24**
>
> - Backend、Frontend 多階段 Image 已成功建置。
> - MariaDB、Backend、Frontend 均配置 Compose healthcheck，且已通過預編寫檢查。
> - MariaDB 實際版本為 **11.7.2**，Alembic 為 `06a577c57935 (head)`。
> - Backend 容器內測試：**69 passed in 20.76s**。
> - 前端時區顯示測試：**2 passed**（本機執行，使用模擬 API）。
>
> 以上是已驗證範圍，不代表完整瀏覽器驗收或所有原始需求均已完成；規格差異與待辦列於文件末段。

## 1. 功能與需求對照

| 模組／需求 | 目前實作 | 狀態 |
|---|---|---|
| FastAPI REST API、Swagger | 認證、資料、分析、管理與健康檢查端點 | 已實作 |
| JWT 與角色權限 | Admin、User、Viewer；資料更新／刪除驗證建立者或 Admin | 已實作 |
| 使用者註冊 | 公開註冊 User／Viewer；第一位人類 Admin 使用 bootstrap API | API 已實作，前端尚無註冊頁 |
| 資料 CRUD | 標題、數值、分類、時間戳；分頁、分類／時間篩選、排序 | 已實作 |
| CSV／JSON 批次匯入 | Pydantic 驗證，回傳新增筆數 | 已實作，尚無去重 |
| 即時資料與 WebSocket | 水位、溫度模擬資料，JWT 連線驗證與 JSON 廣播 | 已實作 |
| 每秒產生資料 | 目前每輪產生兩種類別，預設間隔 **5 秒**，另加處理時間 | 與原題每秒要求有差異 |
| 即時圖表 | 水位／溫度分圖、大字最新值、每圖最近 20 筆、點與數值標籤 | 折線圖已實作 |
| 柱狀圖 | 目前版本採時序折線呈現，柱狀圖已移除 | 與原題要求有差異 |
| 異常告警 | 後端計算並保存 `is_alert`；目前 Realtime UI 未呈現告警狀態 | 部分完成 |
| 統計與趨勢 | 筆數、平均、最大／最小；分類聚合另含加總；分鐘／小時／日趨勢 | 已實作 |
| Excel | 篩選後的原始紀錄匯出，含 UTC 與 UTC+8 時間欄位 | 已實作 |
| Admin 帳號管理 | 分頁查詢使用者、更新角色、禁止自行移除 Admin 角色 | 已實作 |
| 系統日誌查詢 | 有服務端部分錯誤日誌，尚無 Admin 查詢 API／介面 | 未完成 |
| Admin 資料庫監控 | 有 `/health/db` 連線健康端點，尚未整合 Admin 監控頁 | 部分完成 |
| 即時歷史查詢 | 即時資料已持久化，可由 Data Management／Analytics 查詢 | 通用查詢已實作，尚無 Admin 專用入口 |
| MariaDB／ORM／遷移 | MariaDB 11.7、SQLAlchemy Async ORM、asyncmy、Alembic | 已實作 |
| 連線池與批次寫入 | 正式服務使用 AsyncEngine 連線池；達筆數門檻時批次提交 | 已實作 |
| Streamlit 多頁面／Session | Home、Realtime、Analytics、Admin、Data Management | 已實作，狀態清理仍需補強 |
| Docker | 兩份多階段 Dockerfile、三服務 Compose、內部網路、Volume、環境變數 | 已建置並啟動驗證 |

## 2. 技術棧與專案結構

| 項目 | 技術 |
|---|---|
| 執行環境 | Python 3.13；Docker Linux containers |
| 後端 | FastAPI、Uvicorn（`websockets-sansio`） |
| 前端 | Streamlit 1.66.1、Pandas、Plotly、requests、websocket-client |
| 認證 | PyJWT、Passlib／bcrypt |
| 驗證 | Pydantic v2、pydantic-settings |
| 資料庫 | MariaDB 11.7、SQLAlchemy 2.x Async ORM、asyncmy |
| 遷移 | Alembic |
| Excel | openpyxl |
| 測試 | pytest、FastAPI TestClient、Streamlit AppTest |
| 部署 | Docker 多階段建置、Docker Compose、bridge network、named volume |

完整依賴：[Backend requirements](./backend/requirements.txt)、[Frontend requirements](./frontend/requirements.txt)。

```text
Realtime_Monitoring_System/
├── compose.yaml
├── .env.example
├── .dockerignore
├── .gitignore
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── api/          # auth、admin、data_records、analytics、realtime
│   │   ├── core/         # 密碼／JWT 與共用 UTC 轉換
│   │   ├── models/       # User、DataRecord
│   │   ├── schemas/      # Pydantic 請求／回應模型
│   │   ├── services/     # 分析查詢
│   │   └── realtime/     # 生成器、buffer 與連線管理
│   └── test/
├── frontend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py
│   ├── pages/
│   │   ├── 1_realtime.py
│   │   ├── 2_analytics.py
│   │   ├── 3_admin.py
│   │   └── 4_data_management.py
│   ├── services/         # HTTP 與 WebSocket client
│   └── test/
└── sample_data/
    ├── data_records_2026-10-21.csv
    └── data_records_2026-10-22.json
```

## 3. 系統架構圖

```mermaid
flowchart TB
    Browser["瀏覽器"]
    APIUser["Swagger / REST Client"]

    subgraph Net["Docker bridge network: monitoring_net"]
        subgraph Frontend["Frontend 容器 :8501"]
            UI["Streamlit 多頁面 / Session State"]
            HTTP["APIClient"]
            WSClient["WebSocket 背景執行緒"]
            Queue["Queue / 圖表局部更新"]
            UI --> HTTP
            WSClient --> Queue
            Queue --> UI
        end
        subgraph Backend["Backend 容器 :8000 / 單一 worker"]
            REST["FastAPI REST Routers"]
            Auth["JWT / RBAC"]
            WSRoute["WebSocket Router"]
            Manager["ConnectionManager"]
            Generator["RealtimeService / 生成與批次 buffer"]
            ORM["SQLAlchemy AsyncSession / Engine"]
            Migration["Alembic"]
            REST --> Auth
            REST --> ORM
            WSRoute --> Manager
            Generator --> Manager
            Generator --> ORM
        end
        DB[("MariaDB :3306")]
        HTTP -->|"HTTP + Bearer JWT / backend:8000"| REST
        WSClient <-->|"WebSocket + JWT / backend:8000"| WSRoute
        Manager -->|"JSON 推送"| WSClient
        ORM -->|"asyncmy"| DB
        Migration -->|"Schema 遷移"| DB
    end

    Browser <-->|"localhost:8501 / Streamlit HTTP 與 WebSocket"| UI
    APIUser -->|"localhost:8000"| REST
    DB --- Volume[("mariadb_data / 資料持久化")]
```

- 瀏覽器與 Streamlit 的通訊，和 Streamlit Python 與 FastAPI 的 WebSocket，是兩條不同連線。
- 前端不直接連線資料庫；應用資料操作使用 SQLAlchemy 映射模型與查詢表達式。
- Engine 隨 FastAPI lifespan 建立／釋放；每次 REST 請求取得獨立 Session。
- 即時生成器每輪產生水位與溫度，先透過 WebSocket 廣播，再檢查 buffer；目前 `batch_size=2`，達門檻時嘗試以同一交易寫入 DB，正常停止時也會嘗試 flush。
- Realtime 圖表由 WebSocket 訊息更新，不需等待 DB 寫入成功；Data Management／Analytics 則查詢已持久化的資料。寫入失敗時會記錄錯誤並將 batch 放回記憶體 buffer，不能保證每輪一定成功落庫。
- `REALTIME_AUTO_START=true` 時隨應用啟動資料生成器；否則第一次有效 WebSocket 連線會啟動它。關閉前端連線不等於停止後端生成器。
- 生成器與連線集合存在單一 process 記憶體中；目前使用 1 worker，不應在未處理跨 process 協調前直接增加 worker 或副本。

## 4. 環境設定

以下終端機範例以 **Windows PowerShell** 為準；除另有註明外，從專案根目錄執行。取得／解壓完整專案後再操作，不要只下載 Dockerfile。

### 4.1 建立本機設定

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

編輯 `.env`。不要覆蓋已可工作的帳號密碼，也不要將真實 `.env` 提交 GitHub。

| 變數 | 用途 |
|---|---|
| `MARIADB_DATABASE` | 初始化的資料庫名稱 |
| `MARIADB_USER` / `MARIADB_PASSWORD` | 應用資料庫帳號／密碼 |
| `MARIADB_ROOT_PASSWORD` | MariaDB root 密碼，必須設定非空值；目前 Compose 會拒絕未設定或空字串，應用程式不使用 root 帳號 |
| `DATABASE_URL` | Windows 本機後端／測試使用的 `mysql+asyncmy` URL |
| `DATABASE_URL_DOCKER` | Backend 容器使用的 URL，Compose 將它注入容器的 `DATABASE_URL` |
| `JWT_SECRET_KEY` | 請設定隨機且保密的 JWT 簽章密鑰|
| `JWT_ALGORITHM` | 預設 `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 預設 30 分鐘 |
| `SYSTEM_BOT_PASSWORD` | 內部即時資料寫入帳號的密碼，請自行設定 |
| `REALTIME_AUTO_START` | 是否在應用啟動時自動啟動資料生成器 |

兩個 URL 的帳號、密碼、DB 名稱應與 `MARIADB_*` 一致，只有主機與埠不同：

```dotenv
# 僅為格式範例：REPLACE_DB_PASSWORD 必須替換成同一份實際 DB 密碼。
DATABASE_URL=mysql+asyncmy://monitoring_app:REPLACE_DB_PASSWORD@127.0.0.1:3307/monitoring
DATABASE_URL_DOCKER=mysql+asyncmy://monitoring_app:REPLACE_DB_PASSWORD@mariadb:3306/monitoring
```

請特別確認 [.env.example](./.env.example) 複製後的 URL 密碼已同步替換，不能直接沿用不同的占位值。

新環境建議使用隨機十六進位密碼／密鑰，避免 URL 特殊字元。可在 PowerShell 執行以下命令產生一組 32-byte 亂數，再分別產生不同值使用：

```powershell
$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$rng.Dispose()
([BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
```

**既有資料庫注意：** MariaDB 初始化環境變數主要在空資料目錄首次啟動時生效。修改 `.env` 不會自動修改既有 Volume 裡的 DB 密碼；不要為了修正連線而刪除 Volume。

### 4.2 容器與本機位址

| 連線來源 | 目標 | 位址 |
|---|---|---|
| Windows 瀏覽器 | Streamlit | `http://localhost:8501` |
| Windows 瀏覽器／REST client | FastAPI | `http://localhost:8000` |
| Frontend 容器 | Backend REST | `http://backend:8000` |
| Frontend 容器 | Backend WebSocket | `ws://backend:8000` |
| Backend 容器 | MariaDB | `mariadb:3306` |
| Windows 本機後端／工具 | MariaDB | `127.0.0.1:3307` |

Compose 會為 Frontend 注入 `API_BASE_URL`、`WS_BASE_URL`。容器內的 `localhost` 是該容器自己；不要把 Frontend 側欄的 URL 改成 Windows 瀏覽器使用的位址。

## 5. Docker 部署（推薦）

### 5.1 前置條件

- Docker Desktop（使用 Linux containers）或 Linux Docker Engine，並提供 Docker Compose。
- 足夠的磁碟、記憶體及首次下載 Image／套件的網路。
- 已完成上一節的 `.env` 設定。
- 主機的 8000、8501 未被本機 Backend／Streamlit 占用；3307 供本專案 MariaDB 使用。

不需要預先在主機安裝 Python、MariaDB 或 Python 套件。

```powershell
docker version
docker compose version
docker compose config --quiet
```

設定檢查成功通常沒有輸出。

### 5.2 建置與啟動

```powershell
docker compose build backend frontend
docker compose up -d --wait --wait-timeout 180
docker compose ps
```

- `build` 建立 Image，不會執行應用的啟動命令。
- `up` 建立／更新並啟動容器；`-d` 背景執行，`--wait` 等待健康狀態。
- MariaDB 使用現成 `mariadb:11.7` Image。
- Backend 與 Frontend 使用 builder／runtime 多階段建置，runtime 以非 root 帳號執行。
- 啟動順序為：**MariaDB healthy → Backend 執行 migration、啟動並 healthy → Frontend**。
- `.dockerignore` 排除 `.env`、虛擬環境與快取；密鑰在啟動時注入，不烘焙進 Image。

部署檔案：[Compose](./compose.yaml)、[Backend Dockerfile](./backend/Dockerfile)、[Frontend Dockerfile](./frontend/Dockerfile)。

### 5.3 存取與驗證

| 介面 | 連結 |
|---|---|
| Streamlit | <http://localhost:8501> |
| Swagger UI | <http://localhost:8000/docs> |
| OpenAPI JSON | <http://localhost:8000/openapi.json> |
| ReDoc | <http://localhost:8000/redoc> |
| 應用健康 | <http://localhost:8000/health> |
| DB 連線健康 | <http://localhost:8000/health/db> |

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/health/db
docker compose exec -T backend python -m alembic current
```

預期健康回應分別為 `{"status":"ok!!"}`、`{"database":"connected"}`；migration 為 `06a577c57935 (head)`。

驗證跨容器通訊：

```powershell
docker compose exec -T frontend python -c "import urllib.request; print(urllib.request.urlopen('http://backend:8000/health', timeout=5).status)"
```

預期為 `200`。健康檢查不取代登入、WebSocket 與匯入等功能驗收。

### 5.4 更新、停止與持久化

修改 Python 原始碼後，需要重新建置並套用 Image；目前沒有原始碼 bind mount：

```powershell
docker compose build backend frontend
docker compose up -d --wait --wait-timeout 180
```

只改 Backend 時可只 build Backend，但 `up` 建議仍啟動完整服務。`--no-deps` 僅適用於依賴服務仍正常運行的情況，否則可能因 DB 未啟動而失敗。

```powershell
# 查看日誌；分享前遮蔽 JWT、密碼與連線字串
docker compose logs --tail 100 backend frontend mariadb

# 停止但保留容器
docker compose stop

# 移除服務容器與網路，預設保留 named volume
docker compose down
```

**不要執行 `docker compose down -v`，除非明確接受刪除資料。**

資料保存在 `mariadb_data` 掛載的 `/var/lib/mysql`。維持相同 Compose project name，重建容器後才會繼續使用同一份 Volume。可記下一筆資料 ID，執行不帶 `-v` 的 `down`／`up`，再查回該 ID 驗證；不要只比總筆數，生成器可能持續新增資料。

目前主機埠綁定 `127.0.0.1`，只供本機存取；Streamlit 顯示的 External URL 不代表已開放公網。

## 6. 本機開發模式（Python 在主機、MariaDB 在 Docker）

需要 Python 3.13 與 Docker，並完成第 4 節的設定。本機與全容器模式不要同時占用 8000／8501。

### 6.1 啟動 DB、安裝依賴

在專案根目錄：

```powershell
docker compose stop backend frontend
docker compose up -d --wait --wait-timeout 180 mariadb

py -3.13 -m venv .\backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
.\backend\.venv\Scripts\python.exe -m pip install -r .\frontend\requirements.txt
```

本機開發為方便操作，共用這組 venv；Docker 部署中的兩個服務則各自安裝依賴。

### 6.2 啟動 Backend

在第一個終端機：

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --ws websockets-sansio --workers 1
```

本機後端讀取專案根目錄的 `.env`，使用 `DATABASE_URL`，不是 `DATABASE_URL_DOCKER`。

### 6.3 啟動 Frontend

在另一個終端機，由專案根目錄執行：

```powershell
$env:API_BASE_URL = "http://localhost:8000"
$env:WS_BASE_URL = "ws://localhost:8000"
Set-Location .\frontend
..\backend\.venv\Scripts\python.exe -m streamlit run app.py
```

開啟 <http://localhost:8501>。停止前端只會停止前端程式，不會停止另一個終端機中的後端生成器。

## 7. 測試帳號與首次初始化

**全新資料庫不會自動建立以下人類測試帳號。** 請先執行本節的建立流程，再登入。以下密碼只供本機測驗展示，不能用於公開部署。

| 角色 | 帳號 | 本機展示密碼 | 建立方式 |
|---|---|---|---|
| Admin | `demo_admin` | `DemoAdmin2026!` | 首次 bootstrap API |
| User | `demo_user` | `DemoUser2026!` | 公開 register API |
| Viewer | `demo_viewer` | `DemoViewer2026!` | 公開 register API |

在 PowerShell 執行一次：

```powershell
$api = "http://localhost:8000/api/v1"

$admin = @{
    username = "demo_admin"
    email = "demo_admin@example.com"
    password = "DemoAdmin2026!"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$api/admin/bootstrap" -ContentType "application/json" -Body $admin

$user = @{
    username = "demo_user"
    email = "demo_user@example.com"
    password = "DemoUser2026!"
    role = "user"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$api/auth/register" -ContentType "application/json" -Body $user

$viewer = @{
    username = "demo_viewer"
    email = "demo_viewer@example.com"
    password = "DemoViewer2026!"
    role = "viewer"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$api/auth/register" -ContentType "application/json" -Body $viewer
```

- 已有任何人類 Admin 時，bootstrap 回傳 `409`；請使用原有 Admin，不要為重跑範例刪除資料。
- 重複 username／email 會回傳衝突；帳號建立命令不是自動重設密碼的工具。
- 公開 register 不允許建立 Admin。
- `system_bot` 是即時資料寫入的內部帳號，非展示登入帳號，也不出現在 Admin 管理列表。
- 請先在本機完成 bootstrap，再考慮任何對外服務設定。

### 權限矩陣

| 操作 | Viewer | User | Admin |
|---|---|---|---|
| 讀取資料、分析、Excel、即時監控 | 可 | 可 | 可 |
| 建立／匯入資料 | 不可 | 可 | 可 |
| 更新／刪除資料 | 不可 | 僅自己建立的資料 | 所有資料 |
| 管理使用者角色 | 不可 | 不可 | 可；不得自行降級 |

權限以後端驗證為準。角色被變更後，前端登入狀態可能尚未同步，請重新登入。

## 8. 前端操作與測試資料

1. **Home**：登入／登出，設定 API／WS URL。
2. **Realtime**：分別顯示水位與溫度最新值、最近 20 筆折線及點上數值；圖表區預設每 2 秒局部更新，不代表後端每 2 秒生成資料。
3. **Analytics**：選分類、台灣時間範圍及 minute／hour／day，顯示摘要、分类表、趨勢及 Excel 下載。水位、溫度尺度不同，建議分別選分類查詢。
4. **Admin**：Load Users 後查看使用者及建立時間；User ID 可手動輸入或從當頁資料的 ID 升冪選單選擇，再更新角色。
5. **Data Management**：分頁／篩選／排序、建立／更新／刪除、貼上 JSON 或上傳 CSV。

### 範例資料

| 檔案 | 台灣時間範圍 | 筆數 |
|---|---|---|
| [data_records_2026-10-21.csv](./sample_data/data_records_2026-10-21.csv) | 2026-10-21 00:00～05:59 | 720 |
| [data_records_2026-10-22.json](./sample_data/data_records_2026-10-22.json) | 2026-10-22 00:00～05:59 | 720 |

每份包含 `Water_Level`、`Temperature` 各 360 筆，每個類別每分鐘一筆，時間戳含 `+08:00`。兩檔使用不同日期，避免彼此重疊。

**測资不會在啟動時自動匯入；目前沒有去重，同一檔請勿反覆匯入。**

CSV 表頭與示例：

```csv
title,value,category,timestamp
wl-20261021-0000,50.0,Water_Level,2026-10-21T00:00:00+08:00
temp-20261021-0000,25.5,Temperature,2026-10-21T00:00:00+08:00
```

- CSV 必須為 UTF-8（可含 BOM），至少包含 `title,value,category`；`timestamp` 可省略。
- JSON API 格式為 `{"records": [...]}`，每次 **1～1000 筆**；六小時範例 720 筆符合限制。
- 前端 JSON 輸入框可接受陣列並自動包成 `records`；直接呼叫 API 時仍須傳物件格式。
- 前端目前沒有 JSON 檔案上傳元件：開啟 JSON 檔並將完整內容貼入輸入框。
- 匯入成功預期回傳 `{"inserted_count":720}`。匯入紀錄會持久化，但不會直接作為即時生成器的 WebSocket 推送內容。
- 匯入後可查 10/21 或 10/22 的 `00:00:00～05:59:59`（UTC+8）；每個分類應有 360 筆，前提是沒有重複匯入或同範圍其他資料。

## 9. API 文件與端點

完整參數、request／response schema 請參考 [Swagger](http://localhost:8000/docs)。

登入提供两種方式：

- `POST /api/v1/auth/login`：JSON，供前端使用。
- `POST /api/v1/auth/token`：表單，供 Swagger 的 **Authorize** 使用；輸入 username／password 即可。

受保護的 REST API 使用 `Authorization: Bearer <JWT>`。

| 方法 | 路徑 | 用途／權限 |
|---|---|---|
| GET | `/health`、`/health/db` | 應用／DB 連線健康，目前無登入限制 |
| POST | `/api/v1/auth/register` | 註冊 User／Viewer |
| POST | `/api/v1/auth/login`、`/api/v1/auth/token` | 登入取得 JWT |
| GET | `/api/v1/auth/me` | 當前使用者 |
| POST | `/api/v1/admin/bootstrap` | 尚無人類 Admin 時建立第一位 Admin |
| GET | `/api/v1/admin/users` | Admin：使用者分頁／關鍵字／角色篩選 |
| GET | `/api/v1/admin/users/{user_id}` | Admin：取得使用者 |
| PATCH | `/api/v1/admin/users/{user_id}/role` | Admin：更新角色 |
| POST | `/api/v1/data-records` | User／Admin：建立 |
| GET | `/api/v1/data-records` | 登入後：分頁／分類／時間篩選／排序 |
| GET | `/api/v1/data-records/{record_id}` | 登入後：讀取單筆 |
| PUT | `/api/v1/data-records/{record_id}` | 建立者／Admin：更新指定欄位 |
| DELETE | `/api/v1/data-records/{record_id}` | 建立者／Admin：刪除 |
| POST | `/api/v1/data-records/import/json` | User／Admin：JSON 批次匯入 |
| POST | `/api/v1/data-records/import/csv` | User／Admin：multipart `file` 欄位上傳 |
| GET | `/api/v1/realtime/status` | 登入後：生成器狀態與連線數 |
| WS | `/api/v1/ws/realtime?token=<JWT>` | 即時資料推送 |
| GET | `/api/v1/analytics/summary` | 登入後：筆數、平均、最大、最小 |
| GET | `/api/v1/analytics/by-category` | 登入後：分類統計與加總 |
| GET | `/api/v1/analytics/trend` | 登入後：minute／hour／day 聚合 |
| GET | `/api/v1/analytics/export/excel` | 登入後：匯出篩選後原始紀錄 |

資料列表支援 `page`、`size`（1～100）、`category`、`start_time`、`end_time`、`sort_by`（timestamp／value／title／category）、`sort_order`（asc／desc）。

WebSocket 建立連線後先收到 `{"event":"connected","user_id":...}`，後續訊息包含 `title`、`value`、`category`、`timestamp`、`is_alert`。JWT 置於 query string，請勿將含真實 token 的 URL 或 log 公開。

## 10. 時區與資料語意

- **DB 儲存 UTC**：MariaDB `DATETIME` 不保留時區；CRUD／匯入先轉 UTC，再寫入不帶 offset 的 UTC 值。新建帳號的 ORM 預設建立時間也使用 UTC。
- **前端操作與顯示 UTC+8**：日期選擇器按台灣時間解讀，送 API 前轉 UTC；API 回應在畫面轉回台灣時間。
- **API 接受 offset**：CRUD 與所有 Analytics 篩選接受 ISO 8601 `+08:00`、`Z` 等格式。無 offset 的 API 時間沿用 **UTC**，不是主機當地時間。
- 起訖篩選均為包含邊界；正規化後起點晚於終點，回傳 `422`。
- 趨勢按台灣分鐘／小時／自然日分組；`day` 以台灣午夜為界，API `bucket` 回傳 UTC ISO 時間。例如 `2026-10-20T16:00:00Z` 對應台灣 **10/21 00:00**。
- SQLAlchemy 使用固定 offset 進行聚合，不依賴 MariaDB 命名時區表。
- Excel 保留原有欄位，`timestamp` 明確帶 `+00:00`，另加 `timestamp_taipei` 帶 `+08:00`。兩欄使用 ISO 8601 文字，避免 Excel 丟失時區。
- 既有無時區 DB 值按 UTC 解讀，不會自動校正早期匯入的錯誤時間。

等價查詢：

```text
台灣：2026-10-21T00:00:00+08:00 ～ 2026-10-21T05:59:59+08:00
UTC： 2026-10-20T16:00:00Z      ～ 2026-10-20T21:59:59Z
```

資料欄位包含 `id`、`title`、`value`、`category`、`timestamp`、`is_alert`、`creator_id`。目前閾值預設為 `value > 80.0`；水位、溫度共用該門檻，尚未實作分類專屬設定。模擬值以先前值加上隨機變動產生，不是每次連線都重置為起始值。

## 11. 測試與驗收

### 11.1 容器內後端測試

在根目錄、三個服務正常啟動後執行：

```powershell
docker compose exec -T -e REALTIME_AUTO_START=False backend python -m pytest test -q -o cache_dir=/tmp/monitoring-pytest-cache
```

2026-10-24 實際紀錄：**69 passed in 20.76s**。

- 測試涵蓋認證、RBAC、CRUD、批次匯入、Admin、WebSocket／持久化、健康檢查、UTC offset 等價查詢、台灣日界線與 Excel。
- 測試用 Engine 使用 `NullPool`，避免多次 `asyncio.run()` 之間重用綁定舊事件迴圈的連線；正式服務仍使用連線池。
- 非 root 容器的 pytest 快取寫入 `/tmp`，不需要改用 root 或放寬程式目錄權限。
- `-e REALTIME_AUTO_START=False` 只影響這次 exec 測試程序，不會停止正在運行的正式生成器。

**資料安全：整合測試使用目前設定的 DB，會建立並清理符合 `itest_` 命名規則的資料與關聯紀錄。不要用正式資料庫執行，也不要將有價值的資料命名為測試前綴；建議使用獨立測試環境。**

### 11.2 本機測試

由專案根目錄執行，需先完成本機依賴安裝與 DB migration：

```powershell
Push-Location .\backend
.\.venv\Scripts\python.exe -m pytest test -q
Pop-Location

Push-Location .\frontend
..\backend\.venv\Scripts\python.exe -m pytest test\test_timezone_pages.py -q
Pop-Location
```

前端測試使用模擬 API，不連 DB，驗證 Admin 建立時間與 Analytics 日分組在 UI 顯示 UTC+8；先前結果為 **2 passed**。Frontend runtime Image 不包含獨立 pytest 安裝，以上以前述本機共用 venv 執行。

### 11.3 手動驗收指引

- [ ] 依設定範本啟動三個服務，健康檢查通過、migration 在 head。
- [ ] 建立展示帳號並測試登入、登出、角色限制。
- [ ] 建立資料、依分類／時間查詢，確認建立者與 Admin 的更新／刪除權限。
- [ ] CSV／JSON 各匯入一次，確認每份 720 筆與 UTC+8 查詢。
- [ ] WebSocket 持續收到兩種類別，最新資料時間持續前進。
- [ ] Analytics 的分類、台灣時間日界線與 Excel 兩個時間欄正確。
- [ ] 不刪 Volume 地重建容器後，可查回原有資料 ID。

## 12. 常見問題

| 現象 | 檢查與處理 |
|---|---|
| build 很快、原始碼 COPY 顯示 `CACHED` | 確認檔案已儲存；未改變的內容使用快取是正常的，不必直接 `--no-cache` |
| 改了 Python 檔案，容器行為沒變 | 原始碼是 COPY 進 Image，需 build 後再 up；只有 restart 不會更新原始碼 |
| Backend unhealthy、找不到 `mariadb` | 檢查 DB 是否已停止、是否同一網路；使用完整 `docker compose up -d --wait --wait-timeout 180`，不要在 DB 停止時加 `--no-deps` |
| Access denied | URL 帳密必須與既有 DB 一致；修改 `.env` 不會重設既有 DB 帳密 |
| pytest 跨事件迴圈錯誤 | 確認映像包含最新的測試 `NullPool` 設定；不可因此移除正式服務的連線池 |
| pytest cache Permission denied | 使用前述 `-o cache_dir=/tmp/monitoring-pytest-cache` |
| 8000／8501 已被占用 | 停止本機舊 Backend／Streamlit；不要終止不相關的 Python 程序 |
| JWT 失效或回傳 401 | 重新登入；目前沒有 refresh token 功能 |
| CSV／JSON 匯入 422 | 檢查欄位與型別；JSON 另須符合 `records` 物件格式及每次 1～1000 筆限制，目前 CSV 沒有相同的筆數上限 |
| Alembic URL 包含 `%` 時發生 interpolation 錯誤 | 密碼特殊字元需 URL 編碼；目前 [alembic/env.py](./backend/alembic/env.py) 的 `config.set_main_option` 還需要百分比跳脫（傳入 `database_url.replace("%", "%%")`）；新環境可先用隨機 hex 密碼 |
| MariaDB 提示 io_uring 不可用 | 若日誌顯示已採替代 I/O 且 ready／healthy，可繼續功能驗證；不要為消除警告任意開 privileged |
| log 時間比台灣慢八小時 | 容器 log 使用 UTC，屬正常現象，前端顯示才轉 UTC+8 |

## 13. 已知限制與後續工作

1. **原始規格差異**：資料生成預設 5 秒而非 1 秒；目前不提供柱狀圖；後端異常旗標尚未呈現在 Realtime 圖表／卡片。
2. **Admin 待補**：系統日誌查詢、DB 監控介面、Admin 專用即時歷史查詢入口；現有通用歷史查詢可供管理員使用。
3. **前端狀態**：Auto reconnect 可能在主動 Stop 後重新連線，暫時需先取消勾選再 Stop；連線狀態主要依背景 thread 判斷。25 秒無資料時的 rerun 不保證修復連線，接收 Queue 尚無容量限制。
4. **查詢與登入狀態**：Analytics 結果未完整跨 rerun 保留；登出尚未清除所有頁面快取。Viewer／User／Admin UI 狀態可能需重新登入才同步。
5. **資料品質**：尚無 `title + category + timestamp` 去重或 idempotency；部分明確 `null` 輸入、衝突案例與錯誤處理仍需補強。
6. **分析語意**：不指定分類時，summary／trend 會混合各類別數值；不同量綱請分別查詢。全體 summary 提供筆數，數值加總目前在分類聚合提供。
7. **可靠性與擴展**：尚無跨 process 廣播或持久化訊息佇列；異常退出可能遺失未落庫的記憶體 buffer。批次失敗重試、慢連線處理及壓力測試仍需加強。
8. **部署與交付**：目前為 localhost HTTP 部署，未包含 TLS／反向代理、CI/CD 與全新主機一鍵驗收。部分依賴與基礎 Image tag 可隨時間更新，嚴格重現時需進一步鎖版／digest。
