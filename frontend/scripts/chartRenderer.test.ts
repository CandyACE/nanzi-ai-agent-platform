import assert from "node:assert/strict";
import {
  buildChartTableRows,
  createSseLineParser,
  mergeChartDefaults,
  parseChartOptions,
} from "../src/utils/chartRenderer.ts";

const parsed = parseChartOptions(`
{
  xAxis: { type: "category", data: ["A"] },
  yAxis: { type: "value" },
  series: [{ type: "bar", data: [1] }]
}
`);
assert.equal(parsed.ok, true);
if (parsed.ok) {
  assert.equal(parsed.option.series[0].type, "bar");
}

const legacySeriesObject = parseChartOptions(`
{
  series: { type: "pie", data: [{ name: "A", value: 1 }] }
}
`);
assert.equal(legacySeriesObject.ok, true);
if (legacySeriesObject.ok) {
  assert.equal(Array.isArray(legacySeriesObject.option.series), true);
  assert.equal(legacySeriesObject.option.series[0].type, "pie");
}

const legacyChartJsOption = parseChartOptions(`
{
  type: "bar",
  data: {
    labels: ["2026-05", "2026-06"],
    datasets: [{
      label: "变化次数",
      data: [46, 97],
      backgroundColor: ["#111111", "#222222"]
    }]
  }
}
`);
assert.equal(legacyChartJsOption.ok, true);
if (legacyChartJsOption.ok) {
  assert.deepEqual(legacyChartJsOption.option.xAxis.data, ["2026-05", "2026-06"]);
  assert.equal(legacyChartJsOption.option.series[0].name, "变化次数");
  assert.equal(legacyChartJsOption.option.series[0].type, "bar");
  assert.deepEqual(legacyChartJsOption.option.series[0].data[0], {
    value: 46,
    itemStyle: { color: "#111111" },
  });
}

const unsupportedType = parseChartOptions(`
{
  series: [{ type: "sankey", data: [] }]
}
`);
assert.equal(unsupportedType.ok, false);
if (!unsupportedType.ok) {
  assert.equal(unsupportedType.error.code, "unsupported_series_type");
}

const missingSeries = parseChartOptions(`
{
  title: { text: "不是图表" }
}
`);
assert.equal(missingSeries.ok, false);
if (!missingSeries.ok) {
  assert.equal(missingSeries.error.code, "invalid_option");
}

const echartsFencePattern = /(?:<thought>([\s\S]*?)<\/thought>)|(?:<chart>([\s\S]*?)<\/chart>)|(?:```\s*(?:chart|echarts)\s*([\s\S]*?)```)|(?:```\s*mermaid\s*([\s\S]*?)```)|(?::::analysis\s*([^\n]*)\n([\s\S]*?)\n:::)/gi;
const echartsFence = '```echarts\n{"series":[{"type":"bar","data":[1]}]}\n```';
const echartsMatch = echartsFencePattern.exec(echartsFence);
assert.equal(echartsMatch?.[3]?.includes('"series"'), true);
assert.equal(echartsFencePattern.exec('```json\n{"rows":[1]}\n```'), null);

const executable = parseChartOptions(`
{
  series: [{
    type: "bar",
    data: [globalThis.__chartRendererExecuted = true]
  }]
}
`);
assert.equal(executable.ok, false);
assert.equal((globalThis as any).__chartRendererExecuted, undefined);

const pie = mergeChartDefaults({
  series: [{ type: "pie", data: [{ name: "A", value: 1 }] }],
});
assert.equal("xAxis" in pie, false);
assert.equal("yAxis" in pie, false);
assert.equal("grid" in pie, false);
assert.equal(pie.tooltip.trigger, "item");

const bar = mergeChartDefaults({
  xAxis: { data: ["A"] },
  series: [{ type: "bar", data: [1] }],
});
assert.equal("xAxis" in bar, true);
assert.equal("yAxis" in bar, true);
assert.equal("grid" in bar, true);
assert.equal(bar.xAxis.axisLabel.color, "#6b7280");

const lightAxis = mergeChartDefaults({
  xAxis: {
    data: ["2026-06-11"],
    axisLabel: { color: "#f3f4f6" },
  },
  series: [{ type: "line", data: [1] }],
});
assert.equal(lightAxis.xAxis.axisLabel.color, "#6b7280");

const nestedTextStyle = mergeChartDefaults({
  xAxis: {
    data: ["A"],
    axisLabel: { textStyle: { color: "#eeeeee" } },
  },
  series: [{ type: "line", data: [1] }],
});
assert.equal(nestedTextStyle.xAxis.axisLabel.textStyle.color, "#6b7280");

const cartesianTable = buildChartTableRows({
  xAxis: { data: ["06-01", "06-02"] },
  series: [
    { name: "新增用户", type: "line", data: [3, 5] },
    { name: "活跃用户", type: "bar", data: [{ value: 7 }, 9] },
  ],
});
assert.deepEqual(cartesianTable.columns, ["维度", "新增用户", "活跃用户"]);
assert.deepEqual(cartesianTable.rows, [
  ["06-01", 3, 7],
  ["06-02", 5, 9],
]);

const pieTable = buildChartTableRows({
  series: [
    {
      type: "pie",
      data: [
        { name: "华东", value: 12 },
        { name: "华南", value: 8 },
      ],
    },
  ],
});
assert.deepEqual(pieTable.columns, ["名称", "数值"]);
assert.deepEqual(pieTable.rows, [
  ["华东", 12],
  ["华南", 8],
]);

const parseSse = createSseLineParser();
assert.deepEqual(parseSse.feed("data: {\"content\":\"hel"), []);
assert.deepEqual(parseSse.feed("lo\"}\n\ndata: [DONE]\n"), [
  '{"content":"hello"}',
  "[DONE]",
]);
assert.deepEqual(parseSse.flush(), []);
