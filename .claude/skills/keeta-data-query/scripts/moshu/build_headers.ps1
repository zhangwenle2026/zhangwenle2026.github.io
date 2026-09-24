# build_headers.ps1 — 境外版 (bi-query-dashboard-overseas)
#
# 生成 CatDesk (Windows) 环境下 navigate 魔数仪表板页面所需的请求头 JSON。
# 输出到 stdout，供 catdesk.cmd browser-action headers 使用。
#
# 用法:
#   $headersJson = & ".\build_headers.ps1"
#   & catdesk.cmd browser-action "{`"action`":`"headers`",`"headers`":$headersJson}"

# --- X-Client-Env ---
if ($env:CATPAW_CLIENT_TYPE -and $env:CATPAW_CLIENT_VERSION) {
    $clientEnv = "$($env:CATPAW_CLIENT_TYPE):$($env:CATPAW_CLIENT_VERSION)"
} elseif ($env:CATCLAW_VERSION) {
    $clientEnv = $env:CATCLAW_VERSION
} else {
    $clientEnv = "other"
}

# --- X-Client-IP ---
$clientIP = "127.0.0.1"
try {
    $adapter = Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "以太网*","Wi-Fi*","Ethernet*","WLAN*" -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' } |
        Select-Object -First 1
    if ($adapter) {
        $clientIP = $adapter.IPAddress
    }
} catch {
    Write-Host "[headers] 无法获取本机内网 IP，使用 127.0.0.1" -ForegroundColor Yellow
}

# --- 输出 JSON ---
$json = @{
    "X-Skill-isOfficial" = "1"
    "X-Skill-Id"         = "40730"
    "X-Skill-Name"       = "bi-query-dashboard-overseas"
    "X-Skill-Version"    = "V17"
    "X-Client-Env"       = $clientEnv
    "X-Client-IP"        = $clientIP
} | ConvertTo-Json -Compress

Write-Output $json
