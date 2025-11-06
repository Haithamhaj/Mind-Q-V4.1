function nf(v) {
  return new Intl.NumberFormat("ar-SA", { maximumFractionDigits: 1 }).format(v);
}

function drawOption(domId, opt, rows) {
  if (!rows || !rows.length) {
    return;
  }
  window._lastRows = rows;
  const sample = rows[0];
  const xKey = sample.dt !== undefined ? "dt" : sample.dim !== undefined ? "dim" : Object.keys(sample)[0];
  const yKey = Object.keys(sample).find((k) => k !== xKey) || "val";
  const x = rows.map((r) => String(r[xKey]));
  const y = rows.map((r) => Number(r[yKey]));
  const element = document.getElementById(domId);
  if (!element) return;
  const chart = echarts.init(element, null, { renderer: "canvas" });
  const base = {
    textStyle: { fontFamily: "system-ui" },
    grid: { left: 24, right: 16, top: 24, bottom: 36 },
    dataZoom: [{ type: "inside" }, { type: "slider" }],
    tooltip: {
      trigger: "axis",
      formatter: (ps) => `${ps[0].axisValue}<br/>${ps[0].seriesName || "Value"}: ${nf(ps[0].data)}`,
    },
  };
  const option = Object.assign({}, base, opt, {
    xAxis: Object.assign({ type: "category", data: x, axisLabel: { align: "right" } }, opt.xAxis || {}),
    yAxis: Object.assign(
      { type: "value", axisLabel: { formatter: (value) => nf(value) } },
      opt.yAxis || {}
    ),
    series: (opt.series?.length ? opt.series : [{ type: "line" }]).map((series) =>
      Object.assign({}, series, { data: y })
    ),
  });
  chart.setOption(option, true);
  addEventListener("resize", () => chart.resize());
}

function downloadCSV(rows) {
  if (!rows || !rows.length) {
    return;
  }
  const keys = Object.keys(rows[0]);
  const csv = [keys.join(",")].concat(rows.map((row) => keys.map((key) => row[key]).join(","))).join("\n");
  const anchor = document.createElement("a");
  anchor.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  anchor.download = "data.csv";
  anchor.click();
}

async function initialiseExecutive() {
  const response = await fetch("/api/meta");
  const meta = await response.json();
  const catalog = meta.metrics.map((m) => ({ id: m.id, name: m.name }));
  const catalogEl = document.getElementById("catalog");
  if (catalogEl) {
    catalogEl.textContent = JSON.stringify(catalog, null, 2);
  }

  const heroCandidates = ["sla_pct", "rto_pct", "cod_rate"];
  const heroTargets = ["kpi1", "kpi2", "kpi3"];
  heroTargets.forEach(async (elementId, index) => {
    const metricId = heroCandidates[index];
    const metric =
      meta.metrics.find((m) => m.id === metricId) || meta.metrics[index] || meta.metrics[0];
    if (!metric) continue;
    const queryResp = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql: metric.sql }),
    });
    if (!queryResp.ok) continue;
    const data = await queryResp.json();
    const option = {
      grid: { left: 24, right: 16, top: 24, bottom: 36 },
      tooltip: { trigger: "axis" },
      xAxis: { type: "category" },
      yAxis: { type: "value" },
      series: [{ type: "line", smooth: true, areaStyle: { opacity: 0.1 } }],
    };
    drawOption(elementId, option, data.rows);
  });

  const form = document.getElementById("qform");
  const copyBtn = document.getElementById("copy-sql");
  const downloadBtn = document.getElementById("download-csv");
  let lastSQL = "";

  if (form) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const questionInput = document.getElementById("q");
      const question = questionInput ? questionInput.value : "";
      const resp = await fetch("/api/llm/decide_chart", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const payload = await resp.json();
      if (!resp.ok) {
        alert(payload.detail || "Unable to generate chart");
        return;
      }
      const { plan, data } = payload;
      lastSQL = plan.sql;
       window._lastSQL = plan.sql;
       window._lastRows = data;
      drawOption("chart", plan.option, data);
      const explain = document.getElementById("explain");
      if (explain) {
        explain.textContent = plan.explain_ar;
      }
    });
  }

  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      if (!lastSQL) return;
      navigator.clipboard.writeText(lastSQL);
    });
  }

  if (downloadBtn) {
    downloadBtn.addEventListener("click", () => downloadCSV(window._lastRows || []));
  }

  const tryExamples = document.getElementById("try-examples");
  const examples = [
    "line sla_pct trend by date",
    "bar rto_pct by city last month",
    "heatmap sla_pct by city and carrier",
  ];
  if (tryExamples) {
    let index = 0;
    tryExamples.addEventListener("click", () => {
      const input = document.getElementById("q");
      if (!input) return;
      input.value = examples[index % examples.length];
      index += 1;
    });
  }
}

async function initialiseExplorer() {
  const response = await fetch("/api/meta");
  const meta = await response.json();
  const metrics = meta.metrics || [];
  const dimensions = meta.dimensions || [];

  const metricSelect = document.getElementById("metric");
  const dimSelect = document.getElementById("dim");
  if (!metricSelect || !dimSelect) return;

  metrics.forEach((metric) => {
    const option = document.createElement("option");
    option.value = metric.id;
    option.text = metric.name;
    metricSelect.appendChild(option);
  });

  dimensions.forEach((dimension) => {
    const option = document.createElement("option");
    option.value = dimension.id;
    option.text = dimension.id;
    dimSelect.appendChild(option);
  });

  const runButton = document.getElementById("run");
  if (runButton) {
    runButton.addEventListener("click", async () => {
      const metric = metricSelect.value;
      const dimension = dimSelect.value;
      const question = `bar ${metric} by ${dimension}`;
      const resp = await fetch("/api/llm/decide_chart", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const payload = await resp.json();
      if (!resp.ok) {
        alert(payload.detail || "Unable to run explorer query");
        return;
      }
      drawOption("chart", payload.plan.option, payload.data);
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("catalog")) {
    initialiseExecutive();
  }
  if (document.getElementById("metric")) {
    initialiseExplorer();
  }
});
