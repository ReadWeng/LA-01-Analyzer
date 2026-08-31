import os
import re

path = os.path.join("LactateReport", "integrate_reports.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the Chart creation
# We need to find `const lactateChart = new Chart(ctx, {` and split it.
# Wait, actually let's just find `const lactateChart = new Chart(ctx, {`
# and replace it with our setup.

match_start = re.search(r"const lactateChart = new Chart\(ctx, \{\s*type: 'line',\s*data: \{\s*datasets: datasets\s*\},", content)
if match_start:
    new_js = """
        const physioDatasets = datasets.filter(d => ['power', 'hr', 'coreTemp'].includes(d.metric));
        const lactateDatasets = datasets.filter(d => ['lactate', 'glucose'].includes(d.metric));

        const physioScales = Object.assign({}, chartScales);
        delete physioScales.yLactate;
        delete physioScales.yGlucose;

        const lactateScales = Object.assign({}, chartScales);
        delete lactateScales.yPowerHr;
        delete lactateScales.yCoreTemp;

        const baseOptions = """
    # But wait, what about the `options: {` block?
    # Actually, `content` has:
    # const lactateChart = new Chart(ctx, {
    #     type: 'line',
    #     data: {
    #         datasets: datasets
    #     },
    #     options: {
    # We can replace:
    old_start = "const lactateChart = new Chart(ctx, {\n            type: 'line',\n            data: {\n                datasets: datasets\n            },\n            options: {"
    new_start = new_js + "{"
    
    if old_start in content:
        content = content.replace(old_start, new_start)
        print("Replaced start block via exact match")
    else:
        # fallback to regex
        content = re.sub(
            r"const lactateChart = new Chart\(ctx, \{\s*type: 'line',\s*data: \{\s*datasets: datasets\s*\},\s*options: \{",
            new_js + "{",
            content
        )
        print("Replaced start block via regex")
else:
    print("Could not find start block")

# Replace end block
# scales: chartScales
#             }
#         });
old_end = "scales: chartScales\n            }\n        });"
new_end = """};

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
        });"""

if old_end in content:
    content = content.replace(old_end, new_end)
    print("Replaced end block via exact match")
else:
    content = re.sub(r"scales:\s*chartScales\s*\}\s*\}\);", new_end, content)
    print("Replaced end block via regex")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
