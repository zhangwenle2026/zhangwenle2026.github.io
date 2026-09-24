const { chromium } = require('playwright');

(async () => {
    console.log('Starting...');
    try {
        const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
        console.log('Connected! Contexts:', browser.contexts().length);
        const context = browser.contexts()[0];
        const page = await context.newPage();
        console.log('New page created');
        
        await page.goto('https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446', { waitUntil: 'networkidle', timeout: 90000 });
        console.log('Page loaded:', page.url());
        
        await page.waitForFunction(() => typeof window.DashboardController !== 'undefined', { timeout: 30000 });
        console.log('DashboardController ready!');
        
        const charts = [
            ["Last 10 days - New Signs", "chart-e8ns5-c9347"],
            ["Last 10 Days - Order Performance", "dashboard-chart-container-7p18g-b0ef9"],
            ["Last 10 days - Promotion", "chart-iyhbp-a03a1"],
            ["Last 10 days - Operation Performance", "chart-sqalg-1f515"],
            ["Last 10 days - User Experience", "chart-ltuz6-6cbdc"],
            ["CM - Business Performance", "chart-6kwer-1357d"],
        ];
        
        const results = {};
        for (const [name, chartId] of charts) {
            console.log(`\nQuerying: ${name}...`);
            try {
                const data = await page.evaluate(
                    id => window.DashboardController.executeQueryAndGetCHNResult(id).then(res => res),
                    chartId
                );
                results[name] = data;
                if (data && data.code === 0) {
                    const rows = data.data?.data || [];
                    console.log(`  -> OK: ${rows.length} rows`);
                } else {
                    console.log(`  -> Response: ${JSON.stringify(data).slice(0, 200)}`);
                }
            } catch (e) {
                console.log(`  -> ERROR: ${e.message}`);
                results[name] = { error: e.message };
            }
        }
        
        const fs = require('fs');
        fs.writeFileSync('/mnt/openclaw/.openclaw/workspace/bi_raw_data.json', JSON.stringify(results, null, 2));
        console.log('\nData saved!');
        
        await page.close();
        await browser.close();
    } catch (e) {
        console.error('Fatal error:', e.message);
        process.exit(1);
    }
})();
