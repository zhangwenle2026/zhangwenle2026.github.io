/**
 * 商家流量效果分析看板 - 本地代理服务器
 * 解决 file:// 打开 HTML 时 fetch bi.keetapp.com 的 CORS 问题
 *
 * 用法：node bi-proxy-server.js
 * 然后浏览器访问：http://localhost:7788
 *
 * Cookie 自动刷新机制：
 *   1. 启动时从 catdesk 浏览器实时读取 bi.keetapp.com 的 Cookie
 *   2. 代理请求收到 401 / 302→login 时，自动重新抓取并重试
 *   3. Cookie 缓存到 .bi-cookie-cache 文件，下次启动优先读缓存（加速启动）
 */

const http       = require('http');
const https      = require('https');
const fs         = require('fs');
const os         = require('os');
const path       = require('path');
const url        = require('url');
const { execSync, exec, execFile } = require('child_process');

const PORT      = parseInt(process.env.PORT || '7788', 10);
const SKILL_ROOT = path.join(__dirname, '..');
const TRACKER_SCRIPT = path.join(SKILL_ROOT, 'scripts', 'skill_tracker.py');

// ── 启动前自动释放端口（杀掉占用同端口的旧进程）──
try {
  const result = execSync(`lsof -ti tcp:${PORT}`, { encoding: 'utf8' }).trim();
  if (result) {
    const pids = result.split('\n').filter(Boolean);
    pids.forEach(pid => {
      try {
        process.kill(parseInt(pid), 'SIGKILL');
        console.log(`🔪 已终止占用端口 ${PORT} 的旧进程 (PID: ${pid})`);
      } catch (_) {}
    });
    // 等待端口释放
    execSync('sleep 0.5');
  }
} catch (_) {
  // lsof 无输出（端口空闲）时会抛异常，忽略即可
}

const BI_HOST   = 'bi.keetapp.com';
const HTML_FILE = path.join(__dirname, '商家流量效果分析看板.html');
const CACHE_FILE = path.join(__dirname, '.bi-cookie-cache');
// catdesk 路径：优先 .catdesk/bin/catdesk，兜底 .catpaw/bin/catdesk
const CATDESK   = (() => {
  const candidates = [
    path.join(process.env.HOME, '.catdesk/bin/catdesk'),
    path.join(process.env.HOME, '.catpaw/bin/catdesk'),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return candidates[0]; // 兜底，启动时报错更友好
})();

// ── 当前生效的 Cookie（运行时动态更新）──
let currentCookie = '';
let isRefreshing  = false;   // 防止并发重复刷新

function writeTrackingFile(prefix, value, tempFiles) {
  const unique = `${process.pid}_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  const file = path.join(os.tmpdir(), `merchant_tracking_${unique}_${prefix}.txt`);
  fs.writeFileSync(file, String(value || ''), 'utf8');
  tempFiles.push(file);
  return file;
}

function reportScript(params, output, costMs, success = true, errorMsg = '') {
  if (!fs.existsSync(TRACKER_SCRIPT)) return;
  const tempFiles = [];
  const args = [
    TRACKER_SCRIPT,
    'script',
    '--params-file', writeTrackingFile('params', params, tempFiles),
    '--output-file', writeTrackingFile('output', output, tempFiles),
    '--cost-ms', String(Math.max(0, Math.round(costMs || 0))),
    '--status', success ? 'success' : 'fail',
  ];
  if (!success && errorMsg) {
    args.push('--error-file', writeTrackingFile('error', errorMsg, tempFiles));
  }
  execFile('python3', args, { timeout: 15000, cwd: SKILL_ROOT }, err => {
    tempFiles.forEach(file => { try { fs.unlinkSync(file); } catch (_) {} });
    if (err) console.warn('[tracking] 脚本节点上报失败:', err.message);
  });
}

// ============================================================
// Cookie 管理
// ============================================================

/** 从 catdesk 浏览器实时抓取 bi.keetapp.com 的 Cookie */
async function fetchCookieFromBrowser() {
  return new Promise((resolve, reject) => {
    // 先导航到 bi.keetapp.com（确保页面已加载），再读取 document.cookie
    const navigateCmd = `"${CATDESK}" browser-action '{"action":"navigate","url":"https://bi.keetapp.com","waitUntil":"load"}'`;
    exec(navigateCmd, { timeout: 15000 }, (err) => {
      if (err) {
        console.warn('[cookie] 导航失败，尝试直接读取 Cookie:', err.message);
      }
      const evalCmd = `"${CATDESK}" browser-action '{"action":"evaluate","script":"document.cookie"}'`;
      exec(evalCmd, { timeout: 10000 }, (err2, stdout) => {
        if (err2) return reject(new Error('catdesk evaluate 失败: ' + err2.message));
        try {
          const data = JSON.parse(stdout);
          const cookie = data?.data?.result || '';
          if (!cookie) return reject(new Error('获取到的 Cookie 为空'));
          resolve(cookie);
        } catch (e) {
          reject(new Error('解析 catdesk 输出失败: ' + e.message));
        }
      });
    });
  });
}

/** 刷新 Cookie：从浏览器抓取 → 更新内存 → 写缓存 */
async function refreshCookie(reason = '') {
  if (isRefreshing) {
    // 等待正在进行的刷新完成
    await new Promise(r => setTimeout(r, 3000));
    return;
  }
  isRefreshing = true;
  console.log(`\n🔄 [cookie] 刷新中${reason ? '（原因：' + reason + '）' : ''}...`);
  try {
    const cookie = await fetchCookieFromBrowser();
    currentCookie = cookie;
    fs.writeFileSync(CACHE_FILE, cookie, 'utf8');
    console.log(`✅ [cookie] 刷新成功，已写入缓存`);
  } catch (e) {
    console.error(`❌ [cookie] 刷新失败：${e.message}`);
    console.error('   请确保 catdesk 浏览器已打开并登录 bi.keetapp.com');
  } finally {
    isRefreshing = false;
  }
}

/** 初始化 Cookie：优先读缓存立即启动，Cookie 刷新完全异步化（不阻塞查询） */
async function initCookie() {
  // 1. 先尝试读缓存（让服务器能快速启动，不阻塞）
  if (fs.existsSync(CACHE_FILE)) {
    try {
      const cached = fs.readFileSync(CACHE_FILE, 'utf8').trim();
      if (cached) {
        currentCookie = cached;
        console.log('📦 [cookie] 已从缓存加载，服务器即将启动...');
      }
    } catch (_) {}
  }

  // 2. Cookie 刷新完全异步化，不阻塞服务器启动和查询
  //    - 有缓存：延迟 5 秒后台刷新，避免占用浏览器影响启动后的首批查询
  //    - 无缓存：打印警告后延迟 2 秒刷新，刷新完成前查询会报 503（属预期行为）
  if (currentCookie) {
    setTimeout(() => {
      refreshCookie('初始化（后台延迟刷新）').catch(() => {});
    }, 5000);
    console.log('⏱️  [cookie] 将在 5 秒后后台刷新 Cookie，不影响当前查询');
  } else {
    console.warn('⚠️  [cookie] 无缓存，将在 2 秒后后台获取 Cookie；获取完成前查询可能报 503');
    setTimeout(() => {
      refreshCookie('初始化（无缓存后台获取）').catch(() => {});
    }, 2000);
  }
}

/** 判断响应是否表示 Cookie 失效（需要重新登录） */
function isCookieExpired(statusCode, responseHeaders) {
  if (statusCode === 401 || statusCode === 403) return true;
  // BI 平台登录过期时会 302 跳转到 SSO 登录页
  if (statusCode === 302) {
    const loc = responseHeaders['location'] || '';
    if (loc.includes('login') || loc.includes('sso') || loc.includes('passport')) return true;
  }
  return false;
}

// ============================================================
// 代理请求（支持 Cookie 过期自动重试）
// ============================================================

function proxyRequest(req, res, cookie, isRetry = false) {
  const parsed    = url.parse(req.url);
  const targetPath = parsed.pathname.replace('/bi-api', '') + (parsed.search || '');
  const startTime = Date.now();

  let body = [];
  req.on('data', chunk => body.push(chunk));
  req.on('end', () => {
    const bodyBuf = Buffer.concat(body);
    const requestBody = bodyBuf.toString('utf8');

    const options = {
      hostname: BI_HOST,
      port: 443,
      path: targetPath,
      method: req.method,
      headers: {
        'Content-Type':   req.headers['content-type']  || 'application/json',
        'Accept':         req.headers['accept']         || 'application/json',
        'Cookie':         cookie,
        'User-Agent':     'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer':        'https://bi.keetapp.com/',
        'Origin':         'https://bi.keetapp.com',
        'Content-Length': bodyBuf.length,
      }
    };

    const proxyReq = https.request(options, proxyRes => {
      // 检测 Cookie 是否过期
      if (!isRetry && isCookieExpired(proxyRes.statusCode, proxyRes.headers)) {
        console.warn(`\n⚠️  [cookie] 检测到登录失效（HTTP ${proxyRes.statusCode}），自动刷新 Cookie 并重试...`);
        // 消费掉响应体，避免 socket hang
        proxyRes.resume();
        refreshCookie('登录失效').then(() => {
          // 重建请求对象（body 已读完，需要重新注入）
          const fakeReq = Object.assign(Object.create(req), {
            on: (event, cb) => {
              if (event === 'data') cb(bodyBuf);
              if (event === 'end')  cb();
              return fakeReq;
            }
          });
          proxyRequest(fakeReq, res, currentCookie, true);
        });
        return;
      }

      res.writeHead(proxyRes.statusCode, {
        'Content-Type': proxyRes.headers['content-type'] || 'application/json',
        'Access-Control-Allow-Origin': '*',
      });
      proxyRes.on('end', () => {
        reportScript(
          `endpoint=/bi-api method=${req.method} path=${targetPath} retry=${isRetry} request_body=${requestBody}`,
          `status=${proxyRes.statusCode}`,
          Date.now() - startTime,
          proxyRes.statusCode < 400,
          proxyRes.statusCode < 400 ? '' : `HTTP ${proxyRes.statusCode}`
        );
      });
      proxyRes.pipe(res);
    });

    proxyReq.on('error', err => {
      console.error('[proxy error]', err.message);
      reportScript(
        `endpoint=/bi-api method=${req.method} path=${targetPath} retry=${isRetry} request_body=${requestBody}`,
        '',
        Date.now() - startTime,
        false,
        err.message
      );
      if (!res.headersSent) {
        res.writeHead(502);
        res.end(JSON.stringify({ code: -1, message: '代理请求失败: ' + err.message }));
      }
    });

    proxyReq.write(bodyBuf);
    proxyReq.end();
  });
}

// ============================================================
// HTTP 服务器
// ============================================================

const server = http.createServer((req, res) => {
  const parsed = url.parse(req.url);

  // CORS 预检
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type,Accept');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  // 静态 HTML
  if (req.method === 'GET' && (parsed.pathname === '/' || parsed.pathname === '/index.html')) {
    fs.readFile(HTML_FILE, (err, data) => {
      if (err) { res.writeHead(500); res.end('HTML 文件读取失败: ' + err.message); return; }
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(data);
    });
    return;
  }

  // 健康检查（GET /ping）
  if (req.method === 'GET' && parsed.pathname === '/ping') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, engine: 'keeta-bi' }));
    return;
  }

  // 手动刷新 Cookie 接口（供调试用：GET /refresh-cookie）
  if (req.method === 'GET' && parsed.pathname === '/refresh-cookie') {
    refreshCookie('手动触发').then(() => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true, message: 'Cookie 已刷新' }));
    });
    return;
  }

  // ── /keeta-bi-query：通过 keeta-bi skill（keeta_bi_skill.py）执行 Hive SQL ──
  if (req.method === 'POST' && parsed.pathname === '/keeta-bi-query') {
    let body = [];
    req.on('data', chunk => body.push(chunk));
    req.on('end', () => {
      let sql = '', project = '0', queue = 'root.fra02.hadoop-sailor.query', limit = 1000;
      try {
        const payload = JSON.parse(Buffer.concat(body).toString());
        sql     = (payload.sql     || '').trim();
        project = payload.project  || '0';
        queue   = payload.queue    || 'root.fra02.hadoop-sailor.query';
        limit   = payload.limit    || 1000;
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ code: -1, message: '请求体解析失败，需要 JSON { sql: "..." }' }));
        return;
      }
      if (!sql) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ code: -1, message: 'sql 字段不能为空' }));
        return;
      }

      // keeta_bi_skill.py 路径：优先用 keeta-bi skill 目录下的，兜底用 merchant-traffic-analysis 的
      const keetaBiScript = (() => {
        const candidates = [
          path.join(process.env.HOME, '.catpaw/skills/keeta-bi/scripts/keeta_bi_skill.py'),
          path.join(__dirname, 'scripts/keeta_bi_skill.py'),
        ];
        for (const c of candidates) {
          try { if (fs.existsSync(c)) return c; } catch (_) {}
        }
        return null;
      })();

      if (!keetaBiScript) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ code: -1, message: '未找到 keeta_bi_skill.py，请确认 keeta-bi skill 已安装' }));
        return;
      }

      console.log(`\n📊 [keeta-bi] 执行 SQL（${sql.length} 字符），project=${project} queue=${queue}...`);
      const startTime = Date.now();

      // 将 SQL 写入临时文件，避免命令行参数过长（macOS ARG_MAX 限制）
      const tmpFile = path.join(require('os').tmpdir(), `keeta_bi_${Date.now()}.sql`);
      try {
        fs.writeFileSync(tmpFile, sql, 'utf8');
      } catch (writeErr) {
        reportScript(
          `endpoint=/keeta-bi-query project=${project} queue=${queue} sql=${sql}`,
          '',
          Date.now() - startTime,
          false,
          '临时文件写入失败: ' + writeErr.message
        );
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ code: -1, message: '临时文件写入失败: ' + writeErr.message }));
        return;
      }

      const cmd = `python3 ${JSON.stringify(keetaBiScript)} run ${JSON.stringify(tmpFile)} -p ${JSON.stringify(project)} -q ${JSON.stringify(queue)} -n ${limit} --timeout 900 --json`;
      const execEnv = Object.assign({}, process.env, { OPENCLAW_WORKSPACE_ROOT: __dirname });
      exec(cmd, { timeout: 930000, maxBuffer: 50 * 1024 * 1024, cwd: __dirname, env: execEnv }, (err, stdout, stderr) => {
        // 清理临时文件
        try { fs.unlinkSync(tmpFile); } catch (_) {}
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        if (err) {
          // stderr 可能只是 urllib3/pip 警告（非致命），先尝试解析 stdout
          // 只有 stdout 无法解析时才返回 500
          const hasStdout = stdout && stdout.trim().includes('{');
          if (!hasStdout) {
            console.error(`❌ [keeta-bi] 执行失败（${elapsed}s）:`, stderr || err.message);
            reportScript(
              `endpoint=/keeta-bi-query project=${project} queue=${queue} sql=${sql}`,
              stdout || '',
              Date.now() - startTime,
              false,
              stderr || err.message
            );
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({
              code: -1,
              message: `keeta-bi 执行失败: ${(stderr || err.message || '').slice(0, 500)}`
            }));
            return;
          }
          console.warn(`⚠️  [keeta-bi] 进程退出码非 0，但 stdout 有内容，尝试解析（${elapsed}s）`);
        } else {
          console.log(`✅ [keeta-bi] 执行成功（${elapsed}s）`);
        }
        try {
          // keeta_bi_skill.py --json 输出格式：
          //   { success: true, columns: ["col1",...], data: [["v1",...], ...], total_num: N }
          // stdout 可能包含 urllib3 警告行，需提取最后一个完整 JSON 块
          let jsonStr = '';
          // 找到第一个 '{' 到最后一个 '}' 之间的内容
          const firstBrace = stdout.indexOf('{');
          const lastBrace  = stdout.lastIndexOf('}');
          if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
            jsonStr = stdout.slice(firstBrace, lastBrace + 1);
          } else {
            jsonStr = stdout;
          }
          const parsed = JSON.parse(jsonStr);
          if (parsed.success === false) {
            const errMsg = parsed.error || parsed.message || 'keeta-bi 查询失败';
            console.error(`❌ [keeta-bi] 查询失败（${elapsed}s）: ${errMsg}`);
            reportScript(
              `endpoint=/keeta-bi-query project=${project} queue=${queue} sql=${sql}`,
              JSON.stringify(parsed),
              Date.now() - startTime,
              false,
              errMsg
            );
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ code: -1, message: `keeta-bi 查询失败: ${errMsg}` }));
            return;
          }
          const columns = parsed.columns || [];
          // data 是二维数组 [[v1,v2,...], ...]；rows 是对象数组（兼容旧格式）
          const rawRows = parsed.data || parsed.rows || [];
          const rows = rawRows.map(r => {
            if (Array.isArray(r)) {
              const obj = {};
              columns.forEach((col, i) => { obj[col] = r[i]; });
              return obj;
            }
            return r;
          });
          reportScript(
            `endpoint=/keeta-bi-query project=${project} queue=${queue} sql=${sql}`,
            JSON.stringify(parsed),
            Date.now() - startTime,
            true
          );
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ code: 0, data: { rows, total: rows.length } }));
        } catch (parseErr) {
          console.error('[keeta-bi] JSON 解析失败:', parseErr.message, '\nstdout:', stdout.slice(0, 500));
          reportScript(
            `endpoint=/keeta-bi-query project=${project} queue=${queue} sql=${sql}`,
            stdout || '',
            Date.now() - startTime,
            false,
            'keeta-bi 输出解析失败: ' + parseErr.message
          );
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ code: -1, message: 'keeta-bi 输出解析失败: ' + parseErr.message }));
        }
      });
    });
    return;
  }

  // ── /mtdata-query：通过 mtdata bi run 执行 SQL（无需 Cookie，推荐在线版使用）──
  if (req.method === 'POST' && parsed.pathname === '/mtdata-query') {
    let body = [];
    req.on('data', chunk => body.push(chunk));
    req.on('end', () => {
      let sql = '';
      try {
        const payload = JSON.parse(Buffer.concat(body).toString());
        sql = (payload.sql || '').trim();
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ code: -1, message: '请求体解析失败，需要 JSON { sql: "..." }' }));
        return;
      }
      if (!sql) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ code: -1, message: 'sql 字段不能为空' }));
        return;
      }

      // 找 mtdata 可执行文件
      const mtdataBin = (() => {
        const candidates = [
          path.join(process.env.HOME, '.local/bin/mtdata'),
          '/usr/local/bin/mtdata',
          'mtdata',
        ];
        for (const c of candidates) {
          try { if (fs.existsSync(c)) return c; } catch (_) {}
        }
        return 'mtdata'; // 兜底，依赖 PATH
      })();

      console.log(`\n📊 [mtdata] 执行 SQL（${sql.length} 字符）...`);
      const startTime = Date.now();

      // mtdata bi run --format json 输出结构化 JSON
      const child = exec(
        `"${mtdataBin}" bi run --base-url https://bi.keetapp.com --format json --limit 500 ${JSON.stringify(sql)}`,
        { timeout: 120000, maxBuffer: 50 * 1024 * 1024 },
        (err, stdout, stderr) => {
          const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
          if (err) {
            console.error(`❌ [mtdata] 执行失败（${elapsed}s）:`, stderr || err.message);
            reportScript(
              `endpoint=/mtdata-query sql=${sql}`,
              stdout || '',
              Date.now() - startTime,
              false,
              stderr || err.message
            );
            res.writeHead(500, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({
              code: -1,
              message: `mtdata 执行失败: ${(stderr || err.message || '').slice(0, 500)}`
            }));
            return;
          }
          console.log(`✅ [mtdata] 执行成功（${elapsed}s）`);
          // mtdata --format json 输出：{ columns: [...], rows: [[...], ...] }
          // 转换为前端期望的 { data: { rows: [{col: val, ...}, ...] } } 格式
          try {
            const parsed = JSON.parse(stdout);
            // mtdata json 格式：{ columns: ["col1","col2",...], rows: [[v1,v2,...], ...] }
            const columns = parsed.columns || [];
            const rawRows = parsed.rows || parsed.data || [];
            const rows = rawRows.map(r => {
              if (Array.isArray(r)) {
                const obj = {};
                columns.forEach((col, i) => { obj[col] = r[i]; });
                return obj;
              }
              return r; // 已经是对象格式
            });
            reportScript(
              `endpoint=/mtdata-query sql=${sql}`,
              stdout,
              Date.now() - startTime,
              true
            );
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ code: 0, data: { rows, total: rows.length } }));
          } catch (parseErr) {
            reportScript(
              `endpoint=/mtdata-query sql=${sql}`,
              stdout,
              Date.now() - startTime,
              true
            );
            // 解析失败时原样透传，让前端自行处理
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(stdout);
          }
        }
      );
    });
    return;
  }

  // 代理 /bi-api/* → https://bi.keetapp.com/*（兼容本地访问模式）
  if (parsed.pathname.startsWith('/bi-api/')) {
    if (!currentCookie) {
      res.writeHead(503);
      res.end(JSON.stringify({ code: -1, message: 'Cookie 尚未就绪，请稍后重试' }));
      return;
    }
    proxyRequest(req, res, currentCookie);
    return;
  }

  res.writeHead(404);
  res.end('Not found');
});

// ============================================================
// 启动
// ============================================================

(async () => {
  console.log('\n🚀 商家流量效果分析看板 - 代理服务器');
  console.log('─'.repeat(50));

  // 检查 catdesk 是否存在
  if (!fs.existsSync(CATDESK)) {
    console.error(`❌ 未找到 catdesk：${CATDESK}`);
    console.error('   请确保 CatPaw Desk 已安装');
    process.exit(1);
  }

  // 初始化 Cookie
  await initCookie();

  // 启动服务器
  server.listen(PORT, '127.0.0.1', () => {
    console.log(`\n✅ 服务器已启动`);
    console.log(`   看板地址：http://localhost:${PORT}`);
    console.log(`   代理路径：/bi-api/* → https://${BI_HOST}/*`);
    console.log(`   手动刷新：http://localhost:${PORT}/refresh-cookie`);
    console.log(`\n   按 Ctrl+C 停止\n`);
  });
})();
