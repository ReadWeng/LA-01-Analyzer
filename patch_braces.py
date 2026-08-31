import os

path = os.path.join("LactateReport", "integrate_reports.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix single braces in the visibility function
broken_vis = '''physioChart.data.datasets.forEach(dataset => {
            const date = dataset.date;
            const metric = dataset.metric;
            const isDateVisible = document.getElementById('chk-date-' + date).checked;
            const isMetricVisible = document.getElementById('chk-metric-' + metric).checked;
            dataset.hidden = !(isDateVisible && isMetricVisible);
        });'''

fixed_vis = '''physioChart.data.datasets.forEach(dataset => {{
            const date = dataset.date;
            const metric = dataset.metric;
            
            // Check if the checkboxes exist, otherwise fallback to activeDates dictionary
            const dateCheckbox = document.getElementById('chk-date-' + date);
            const metricCheckbox = document.getElementById('chk-metric-' + metric);
            
            const dateActive = dateCheckbox ? dateCheckbox.checked : activeDates[date];
            const metricActive = metricCheckbox ? metricCheckbox.checked : activeMetrics[metric];
            
            dataset.hidden = !(dateActive && metricActive);
        }});'''
content = content.replace(broken_vis, fixed_vis)

# Font scaling fix also had single braces!
broken_font = '''[physioChart, lactateChart].forEach(chart => {
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

fixed_font = '''[physioChart, lactateChart].forEach(chart => {{
                chart.options.plugins.legend.labels.font.size = baseFontSizes.legend * scale;
                chart.options.plugins.tooltip.titleFont.size = baseFontSizes.tooltipTitle * scale;
                chart.options.plugins.tooltip.bodyFont.size = baseFontSizes.tooltipBody * scale;
                
                chart.options.scales.x.title.font.size = baseFontSizes.axisTitle * scale;
                chart.options.scales.x.ticks.font.size = baseFontSizes.axisTicks * scale;

                ['yPowerHr', 'yLactate', 'yCoreTemp', 'yGlucose'].forEach(axisId => {{
                    if (chart.options.scales[axisId]) {{
                        chart.options.scales[axisId].title.font.size = baseFontSizes.axisTitle * scale;
                        chart.options.scales[axisId].ticks.font.size = baseFontSizes.axisTicks * scale;
                    }}
                }});

                chart.update();
            }});'''
content = content.replace(broken_font, fixed_font)

# Fix autoScaleYAxes which now takes two charts
broken_auto = '''autoScaleYAxes(lactateChart);
            lactateChart.update();'''

fixed_auto = '''autoScaleYAxes(physioChart);
            physioChart.update();
            autoScaleYAxes(lactateChart);
            lactateChart.update();'''

if broken_auto in content:
    content = content.replace(broken_auto, fixed_auto)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed single braces in integrate_reports.py")
