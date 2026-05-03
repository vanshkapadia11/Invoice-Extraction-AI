# Invoice Parser API — Testing Commands

> All commands use `curl.exe` (PowerShell) or `curl` (CMD / Git Bash).  
> Replace paths like `C:\Work\My College Work\Projects\invoice-project\sample_invoice.png` with your actual file path.

---

<!-- uvicorn app:app --reload -->

## 🔑 Setting Your API Key (Environment Variable)

### Windows CMD

```cmd
set API_KEY=your-key-here
```

### Windows PowerShell ✅ (use this)

```powershell
$env:API_KEY = "admin-e5715f453937ee02a1245014b8949aac"
```

### Linux / macOS / Git Bash

```bash
export API_KEY=your-key-here
```

### Extracting the Admin Key from server startup

When the server first starts, it prints this in the terminal:

```
============================================================
  ADMIN API KEY: admin-e5715f453937ee02a1245014b8949aac
============================================================
```

Copy that key and set it in PowerShell:

```powershell
# $env:API_KEY = "admin-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
$env:API_KEY = "admin-0112807bb9c3fee585ec1076b1caf91a"

```

> ⚠️ **PowerShell Note:** Always use `curl.exe` (not `curl`) in PowerShell.  
> PowerShell's built-in `curl` is actually `Invoke-WebRequest` and uses completely different syntax — it will error.

---

## ✅ Health Check

### PowerShell ✅

```powershell
curl.exe -s -X GET http://localhost:8000/health | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

### CMD

```cmd
curl -s -X GET http://localhost:8000/health | python -m json.tool
```

---

## 🏠 Home / Root

### PowerShell ✅

```powershell
curl.exe -s -X GET http://localhost:8000/ | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

### CMD

```cmd
curl -s -X GET http://localhost:8000/ | python -m json.tool
```

---

## 📄 Sync Invoice Parse

> Parses an invoice image and returns results immediately.

### PowerShell ✅

```powershell
curl.exe -s -X POST http://localhost:8000/parse-invoice `
  -H "X-API-Key: $env:API_KEY" `
  -F "file=@C:\Work\My College Work\Projects\invoice-project\sample_invoice.png" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

### Windows CMD

```cmd
curl -s -X POST http://localhost:8000/parse-invoice ^
  -H "X-API-Key: %API_KEY%" ^
  -F "file=@C:\Work\My College Work\Projects\invoice-project\sample_invoice.png" | python -m json.tool
```

### Linux / macOS / Git Bash

```bash
curl -s -X POST http://localhost:8000/parse-invoice \
  -H "X-API-Key: $API_KEY" \
  -F "file=@/path/to/invoice.jpg" | python3 -m json.tool
```

---

## 🔄 Async Job — Submit

> Submits a job in the background and returns a `job_id` to poll later.

### PowerShell ✅

```powershell
curl.exe -s -X POST http://localhost:8000/jobs/submit `
  -H "X-API-Key: $env:API_KEY" `
  -F "file=@C:\Work\My College Work\Projects\invoice-project\sample_invoice.png" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

### Windows CMD

```cmd
curl -s -X POST http://localhost:8000/jobs/submit ^
  -H "X-API-Key: %API_KEY%" ^
  -F "file=@C:\Work\My College Work\Projects\invoice-project\sample_invoice.png" | python -m json.tool
```

### Linux / macOS / Git Bash

```bash
curl -s -X POST http://localhost:8000/jobs/submit \
  -H "X-API-Key: $API_KEY" \
  -F "file=@/path/to/invoice.jpg" | python3 -m json.tool
```

---

## 🔍 Async Job — Poll Status

> Replace `<JOB_ID>` with the `job_id` value from the submit response above.

### PowerShell ✅

```powershell
curl.exe -s -X GET http://localhost:8000/jobs/<JOB_ID> `
  -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

### Windows CMD

```cmd
curl -s -X GET http://localhost:8000/jobs/<JOB_ID> ^
  -H "X-API-Key: %API_KEY%" | python -m json.tool
```

### Linux / macOS / Git Bash

```bash
curl -s -X GET http://localhost:8000/jobs/<JOB_ID> \
  -H "X-API-Key: $API_KEY" | python3 -m json.tool
```

---

## 📦 Batch Submit

> Submit up to 20 invoices at once. Returns multiple `job_ids`.

### PowerShell ✅

```powershell
curl.exe -s -X POST http://localhost:8000/batch/submit `
  -H "X-API-Key: $env:API_KEY" `
  -F "files=@C:\path\to\invoice1.jpg" `
  -F "files=@C:\path\to\invoice2.jpg" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

### Windows CMD

```cmd
curl -s -X POST http://localhost:8000/batch/submit ^
  -H "X-API-Key: %API_KEY%" ^
  -F "files=@C:\path\to\invoice1.jpg" ^
  -F "files=@C:\path\to\invoice2.jpg" | python -m json.tool
```

### Linux / macOS / Git Bash

```bash
curl -s -X POST http://localhost:8000/batch/submit \
  -H "X-API-Key: $API_KEY" \
  -F "files=@/path/to/invoice1.jpg" \
  -F "files=@/path/to/invoice2.jpg" | python3 -m json.tool
```

---

## 🔔 Webhooks

### Register a Webhook

#### PowerShell ✅

```powershell
curl.exe -s -X POST "http://localhost:8000/webhooks?url=https://webhook.site/eeaac634-5d99-4bbd-97f7-5cc8cd1d3aef" `
  -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

#### CMD

```cmd
curl -s -X POST "http://localhost:8000/webhooks?url=https://your-endpoint.com/hook" ^
  -H "X-API-Key: %API_KEY%" | python -m json.tool
```

---

### List Webhooks

#### PowerShell ✅

```powershell
curl.exe -s -X GET http://localhost:8000/webhooks `
  -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

#### CMD

```cmd
curl -s -X GET http://localhost:8000/webhooks ^
  -H "X-API-Key: %API_KEY%" | python -m json.tool
```

---

### Delete a Webhook

> Replace `<WEBHOOK_ID>` with the `id` from the list response.

#### PowerShell ✅

```powershell
curl.exe -X DELETE http://localhost:8000/webhooks/<WEBHOOK_ID> `
  -H "X-API-Key: $env:API_KEY"
```

#### CMD

```cmd
curl -X DELETE http://localhost:8000/webhooks/<WEBHOOK_ID> ^
  -H "X-API-Key: %API_KEY%"
```

---

## 🛡️ Admin Routes

> All admin routes require the **Admin / Enterprise** API key.

### Create a New API Key

**Free tier:**

```powershell
curl.exe -s -X POST "http://localhost:8000/admin/keys?name=TestUser&tier=free" `
  -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

**Pro tier:**

```powershell
curl.exe -s -X POST "http://localhost:8000/admin/keys?name=ProUser&tier=pro" `
  -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

**Enterprise tier with 30-day expiry:**

```powershell
curl.exe -s -X POST "http://localhost:8000/admin/keys?name=EnterpriseUser&tier=enterprise&expires_days=30" `
  -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

---

### List All API Keys

```powershell
curl.exe -s -X GET http://localhost:8000/admin/keys `
  -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

---

### Update a Key

> Replace `<KEY_ID>` with the numeric `id` from the keys list.

**Deactivate a key:**

```powershell
curl.exe -X PATCH "http://localhost:8000/admin/keys/<KEY_ID>?is_active=0" `
  -H "X-API-Key: $env:API_KEY"
```

**Reactivate a key:**

```powershell
curl.exe -X PATCH "http://localhost:8000/admin/keys/<KEY_ID>?is_active=1" `
  -H "X-API-Key: $env:API_KEY"
```

**Change tier to pro:**

```powershell
curl.exe -X PATCH "http://localhost:8000/admin/keys/<KEY_ID>?tier=pro" `
  -H "X-API-Key: $env:API_KEY"
```

---

### Revoke a Key

```powershell
curl.exe -X DELETE http://localhost:8000/admin/keys/<KEY_ID> `
  -H "X-API-Key: $env:API_KEY"
```

---

### View Usage Stats

```powershell
curl.exe -s -X GET http://localhost:8000/admin/usage `
  -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

---

### View Recent Logs

**Last 50 (default):**

```powershell
curl.exe -s -X GET http://localhost:8000/admin/logs `
  -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

**Custom limit (e.g. last 100):**

```powershell
curl.exe -s -X GET "http://localhost:8000/admin/logs?limit=100" `
  -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

---

## 🎨 Pretty JSON — Quick Reference

| Shell         | Pretty Print Method                                               |
| ------------- | ----------------------------------------------------------------- |
| PowerShell    | `curl.exe -s ... \| ConvertFrom-Json \| ConvertTo-Json -Depth 10` |
| CMD           | `curl -s ... \| python -m json.tool`                              |
| Git Bash      | `curl -s ... \| python3 -m json.tool`                             |
| Git Bash (jq) | `curl -s ... \| jq .` _(requires jq installed)_                   |

> `-s` flag silences the curl progress bar so piping works cleanly.

---

## 📊 Tier Limits Reference

| Tier       | Req/min | Req/day | Max File Size |
| ---------- | ------- | ------- | ------------- |
| free       | 5       | 20      | 5 MB          |
| pro        | 30      | 500     | 20 MB         |
| enterprise | 200     | 10,000  | 50 MB         |

---

## 💡 Tips

- **Always use `curl.exe` in PowerShell** — plain `curl` is `Invoke-WebRequest` and will throw errors.
- Use `/docs` in your browser (`http://localhost:8000/docs`) for interactive Swagger UI testing — no terminal needed.
- The `job_id` from `/jobs/submit` and `/batch/submit` can be polled at `/jobs/<JOB_ID>` until `status` is `done` or `failed`.
- Webhooks fire automatically when a job completes — no polling needed if you register one.
- PDF invoices are supported if `pymupdf` is installed: `pip install pymupdf`
- Add `-s` to any `curl.exe` command to suppress the progress bar for cleaner pretty-print output.
