import os

path = os.path.join("LactateReport", "integrate_reports.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. HTML Canvas
old_canvas = '<canvas id="lactateChart"></canvas>'
new_canvas = '''<canvas id="physioChart"></canvas>
            </div>
        </div>
        <div class="chart-card" style="margin-top: 20px;">
            <div class="chart-wrapper">
                <canvas id="lactateChart"></canvas>'''
content = content.replace(old_canvas, new_canvas)

# 2. JS replacement
old_js_start = '''const lactateChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: datasets
            },
            options: {'''

new_js_start = '''const physioDatasets = datasets.filter(d => ['power', 'hr', 'coreTemp'].includes(d.metric));
        const lactateDatasets = datasets.filter(d => ['lactate', 'glucose'].includes(d.metric));

        const physioScales = Object.assign({}, chartScales);
        delete physioScales.yLactate;
        delete physioScales.yGlucose;

        const lactateScales = Object.assign({}, chartScales);
        delete lactateScales.yPowerHr;
        delete lactateScales.yCoreTemp;

        const baseOptions = {'''

content = content.replace(old_js_start, new_js_start)

# 3. End of the options block
old_js_end = '''scales: chartScales
            }
        });'''

new_js_end = '''};

        const physioOptions = Object.assign({}, baseOptions);
        physioOptions.scales = physioScales;

        const lactateOptions = Object.assign({}, baseOptions);
        lactateOptions.scales = lactateScales;

        const ctxPhysio = document.getElementById('physioChart').getContext('2d');
        const physioChart = new Chart(ctxPhysio, {
            type: 'line',
            data: { datasets: physioDatasets },
            options: physioOptions
        });

        const lactateChart = new Chart(ctx, {
            type: 'line',
            data: { datasets: lactateDatasets },
            options: lactateOptions
        });'''

content = content.replace(old_js_end, new_js_end)

# Also need to fix the updateChartVisibility function
old_vis = '''lactateChart.data.datasets.forEach(dataset => {
            const date = dataset.date;
            const metric = dataset.metric;
            const isDateVisible = document.getElementById('chk-date-' + date).checked;
            const isMetricVisible = document.getElementById('chk-metric-' + metric).checked;
            dataset.hidden = !(isDateVisible && isMetricVisible);
        });
        lactateChart.update();'''

new_vis = '''physioChart.data.datasets.forEach(dataset => {
            const date = dataset.date;
            const metric = dataset.metric;
            const isDateVisible = document.getElementById('chk-date-' + date).checked;
            const isMetricVisible = document.getElementById('chk-metric-' + metric).checked;
            dataset.hidden = !(isDateVisible && isMetricVisible);
        });
        physioChart.update();

        lactateChart.data.datasets.forEach(dataset => {
            const date = dataset.date;
            const metric = dataset.metric;
            const isDateVisible = document.getElementById('chk-date-' + date).checked;
            const isMetricVisible = document.getElementById('chk-metric-' + metric).checked;
            dataset.hidden = !(isDateVisible && isMetricVisible);
        });
        lactateChart.update();'''
content = content.replace(old_vis, new_vis)

# Font scaling
old_font = '''lactateChart.options.plugins.legend.labels.font.size = baseFontSizes.legend * scale;
            lactateChart.options.plugins.tooltip.titleFont.size = baseFontSizes.tooltipTitle * scale;
            lactateChart.options.plugins.tooltip.bodyFont.size = baseFontSizes.tooltipBody * scale;
            
            lactateChart.options.scales.x.title.font.size = baseFontSizes.axisTitle * scale;
            lactateChart.options.scales.x.ticks.font.size = baseFontSizes.axisTicks * scale;

            ['yPowerHr', 'yLactate', 'yCoreTemp', 'yGlucose'].forEach(axisId => {
                if (lactateChart.options.scales[axisId]) {
                    lactateChart.options.scales[axisId].title.font.size = baseFontSizes.axisTitle * scale;
                    lactateChart.options.scales[axisId].ticks.font.size = baseFontSizes.axisTicks * scale;
                }
            });

            lactateChart.update();'''

new_font = '''[physioChart, lactateChart].forEach(chart => {
                chart.options.plugins.legend.labels.font.size = baseFontSizes.legend * scale;
                chart.options.plugins.tooltip.titleFont.size = baseFontSizes.tooltipTitle * scale;
                chart.options.plugins.tooltip.bodyFont.size = baseFontSizes.tooltipBody * scale;
                
                chart.options.scales.x.title.font.size = baseFontSizes.axisTitle * scale;
                chart.options.scales.x.ticks.font.size = baseFontSizes.axisTicks * scale;

                ['yPowerHr', 'yLactate', 'yCoreTemp', 'yGlucose'].forEach(axisId => {
                    if (chart.options.scales[axisId]) {
                        chart.options.scales[axisId].title.font.size = baseFontSizes.axisTitle * scale;
                        chart.options.scales[axisId].ticks.font.size = baseFontSizes.axisTicks * scale;
                    }
                });

                chart.update();
            });'''
content = content.replace(old_font, new_font)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Split logic applied successfully.")
