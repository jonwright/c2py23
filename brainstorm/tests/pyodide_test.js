// brainstorm/tests/pyodide_test.js -- run gold benchmarks in Pyodide, append to results.json
const { loadPyodide } = require("pyodide");
const fs = require("fs");
const path = require("path");

async function main() {
    const py = await loadPyodide();
    await py.loadPackage("numpy");

    for (const name of ["gold_noargs", "gold_vnorm"]) {
        const wasm = fs.readFileSync(name + ".wasm");
        py.FS.writeFile("/tmp/" + name + ".cpython-314-wasm32-emscripten.so", wasm);
    }

    const loadMod = async (name) => {
        const soPath = "/tmp/" + name + ".cpython-314-wasm32-emscripten.so";
        await py.runPythonAsync(`
import importlib.machinery, importlib.util
loader = importlib.machinery.ExtensionFileLoader("${name}", "${soPath}")
spec = importlib.util.spec_from_file_location("${name}", "${soPath}", loader=loader)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
`);
    };

    await loadMod("gold_noargs");
    await loadMod("gold_vnorm");

    const noargsNs = await py.runPythonAsync(`
import gold_noargs, time
N = 500_000
for _ in range(500): gold_noargs.noargs()
t0 = time.perf_counter_ns()
for _ in range(N): gold_noargs.noargs()
(time.perf_counter_ns() - t0) / N
`);

    const vnormNs = await py.runPythonAsync(`
import gold_vnorm, time, numpy as np
N = 3; IT = 50_000
vec = np.random.rand(N, 3).astype(np.float64)
mods = np.zeros(N, np.float64)
for _ in range(200): gold_vnorm.varargs(vec, mods)
t0 = time.perf_counter_ns()
for _ in range(IT): gold_vnorm.varargs(vec, mods)
(time.perf_counter_ns() - t0) / IT
`);

    // Read existing results, merge, write back
    const resultPath = path.join(__dirname, "results.json");
    let results = {};
    try { results = JSON.parse(fs.readFileSync(resultPath, "utf8")); } catch (e) {}
    results["pyodide_noargs"] = noargsNs;
    results["pyodide_vnorm"] = vnormNs;
    fs.writeFileSync(resultPath, JSON.stringify(results, null, 1));
    console.log("Pyodide results written to", resultPath);
}

main().catch(e => console.error("Error:", e));
