import os
import re

path = os.path.join("LactateReport", "integrate_reports.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. HTML Canvas
old_canvas = '<canvas id="lactateChart"></canvas>'
new_canvas = '''<canvas id="physioChart"></canvas>
            </div>
        </div>
        <div class="chart-card">
            <div class="chart-wrapper">
                <canvas id="lactateChart"></canvas>'''
content = content.replace(old_canvas, new_canvas)

# 2. Get the JS part
# We need to split the datasets and create two charts.
# Currently: `const ctx = document.getElementById('lactateChart').getContext('2d');`
# and `const lactateChart = new Chart(ctx, { ... datasets: datasets ... options: { ... } });`

# Wait! The easiest way is to NOT use Python to parse, but just inject JS to manipulate the config.
# Before `const lactateChart = new Chart(ctx, {`, we can intercept the config object.
old_chart_init = "const lactateChart = new Chart(ctx, {"
new_chart_init = """
        const physioDatasets = datasets.filter(d => ['power', 'hr', 'coreTemp'].includes(d.metric));
        const lactateDatasets = datasets.filter(d => ['lactate', 'glucose'].includes(d.metric));
        
        // Remove unused scales for physio
        const physioScales = Object.assign({}, chartScales);
        delete physioScales.yLactate;
        delete physioScales.yGlucose;
        
        // Remove unused scales for lactate
        const lactateScales = Object.assign({}, chartScales);
        delete lactateScales.yPowerHr;
        delete lactateScales.yCoreTemp;

        const baseConfig = {"""

# We need to find the `options: {` block and the end of the `Chart` constructor.
# Actually, let's just use regular expressions or string splits.
