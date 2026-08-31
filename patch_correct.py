import os
import re

path = os.path.join("LactateReport", "integrate_reports.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. HTML Canvas
# I already replaced HTML in the last step, but let's check if it's there
if 'id="physioChart"' not in content:
    old_canvas = '<canvas id="lactateChart"></canvas>'
    new_canvas = '''<canvas id="physioChart"></canvas>
                </div>
            </div>
            <div class="chart-card" style="margin-top: 20px;">
                <div class="chart-wrapper">
                    <canvas id="lactateChart"></canvas>'''
    content = content.replace(old_canvas, new_canvas)

# 2. Fix JS Start
# In Python f-string it looks like:
# const lactateChart = new Chart(ctx, {{
#             type: 'line',
#             data: {{
#                 datasets: datasets
#             }},
#             options: {{

old_js_start = '''const lactateChart = new Chart(ctx, {{
            type: 'line',
            data: {{
                datasets: datasets
            }},
            options: {{'''

new_js_start = '''const physioDatasets = datasets.filter(d => ['power', 'hr', 'coreTemp'].includes(d.metric));
        const lactateDatasets = datasets.filter(d => ['lactate', 'glucose'].includes(d.metric));

        const physioScales = Object.assign({}, chartScales);
        delete physioScales.yLactate;
        delete physioScales.yGlucose;

        const lactateScales = Object.assign({}, chartScales);
        delete lactateScales.yPowerHr;
        delete lactateScales.yCoreTemp;

        const baseOptions = {{'''

if old_js_start in content:
    content = content.replace(old_js_start, new_js_start)
    print("Replaced JS Start")
else:
    print("Warning: old_js_start not found")


# 3. Fix JS End
old_js_end = '''scales: chartScales
            }}
        }});'''

new_js_end = '''}};

        const physioOptions = Object.assign({}, baseOptions);
        physioOptions.scales = physioScales;

        const lactateOptions = Object.assign({}, baseOptions);
        lactateOptions.scales = lactateScales;

        const ctxPhysio = document.getElementById('physioChart').getContext('2d');
        const physioChart = new Chart(ctxPhysio, {{
            type: 'line',
            data: {{ datasets: physioDatasets }},
            options: physioOptions
        }});

        const lactateChart = new Chart(ctx, {{
            type: 'line',
            data: {{ datasets: lactateDatasets }},
            options: lactateOptions
        }});'''

if old_js_end in content:
    content = content.replace(old_js_end, new_js_end)
    print("Replaced JS End")
else:
    # Check if we already applied a broken end block
    old_broken_end = '''scales: chartScales
            }
        });'''
    if old_broken_end in content:
        content = content.replace(old_broken_end, new_js_end)
        print("Replaced broken JS End")
    else:
        # Check if we applied `patch_robust.py`'s broken end
        old_robust = '''scales: chartScales
            }
        });'''
        print("Warning: old_js_end not found")
        # Try regex cleanup
        content = re.sub(r"scales:\s*chartScales\s*\}\}\s*\}\}\);", new_js_end, content)

# 4. Fix updateChartVisibility and fonts
# Since my previous patch might have succeeded, let's restore it clean
content = content.replace("lactateChart.data.datasets.forEach", "physioChart.data.datasets.forEach(dataset => {\n            const date = dataset.date;\n            const metric = dataset.metric;\n            const isDateVisible = document.getElementById('chk-date-' + date).checked;\n            const isMetricVisible = document.getElementById('chk-metric-' + metric).checked;\n            dataset.hidden = !(isDateVisible && isMetricVisible);\n        });\n        physioChart.update();\n\n        lactateChart.data.datasets.forEach")

content = content.replace('''lactateChart.options.plugins.legend.labels.font.size = baseFontSizes.legend * scale;
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

            lactateChart.update();''',
            '''[physioChart, lactateChart].forEach(chart => {
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
            });''')

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied.")
