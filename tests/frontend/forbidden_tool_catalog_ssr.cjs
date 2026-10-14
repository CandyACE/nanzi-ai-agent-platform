/**
 * 真渲染 ForbiddenToolCatalog.vue：验证 `resource` 泛化的两种模式确实互斥。
 *
 * 为什么用真编译而不是字符串断言：源码里"有 v-if/v-else"不等于渲染出来只有一个大组
 * （注释夹在 v-if / v-else 之间、分支写反、模板没编译进去都会骗过字符串断言）。
 * 这里用 vue/compiler-sfc 编译真实源码、esbuild 剥 TS、@vue/server-renderer 真渲染，
 * 不复制任何模板逻辑。
 *
 * 局限：SSR 不触发 onMounted，目录不会加载，所以候选条目渲染不出来——聚合 / 计数 /
 * 全选 / 过滤由 test_forbidden_tool_grouping_behavior.py（纯函数行为）覆盖，接线由
 * test_forbidden_tool_grouping_contract.py（源码契约）覆盖。
 *
 * 输出 JSON（断言交给 pytest）。cwd 必须是 frontend。
 */
const fs = require("fs");
const path = require("path");

const fromFrontend = (name) => require(require.resolve(name, { paths: [process.cwd()] }));
const { parse, compileScript, compileTemplate } = fromFrontend("vue/compiler-sfc");
const Vue = fromFrontend("vue");
const { renderToString } = fromFrontend("@vue/server-renderer");
const esbuild = fromFrontend("esbuild");

const COMPONENT = path.resolve("src/components/system/ForbiddenToolCatalog.vue");
const frontendRequire = (id) => require(require.resolve(id, { paths: [process.cwd()] }));

function buildComponent(source) {
  const { descriptor, errors } = parse(source, { filename: COMPONENT });
  if (errors.length) throw new Error("parse: " + errors.map(String).join("; "));

  const script = compileScript(descriptor, { id: "forbidden-catalog" });
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename: COMPONENT,
    id: "forbidden-catalog",
    compilerOptions: {
      bindingMetadata: script.bindings,
      // 模板里有 `($event.target as HTMLInputElement)` 这类 TS 断言
      expressionPlugins: ["typescript"],
    },
  });
  if (tpl.errors.length) throw new Error("template: " + tpl.errors.map(String).join("; "));

  const toComponentOptions = (code) =>
    code.replace("export default", "const __sfc =").replace("export function render", "function render");

  const bundled = esbuild.buildSync({
    stdin: {
      contents: [
        toComponentOptions(script.content),
        toComponentOptions(tpl.code),
        "__sfc.render = render;",
        "export default __sfc;",
      ].join("\n"),
      loader: "ts",
      resolveDir: path.dirname(COMPONENT),
      sourcefile: "ForbiddenToolCatalog.entry.ts",
    },
    bundle: true,
    write: false,
    format: "cjs",
    platform: "node",
    target: "node18",
    external: ["vue", "axios"],
    logLevel: "silent",
  });

  const moduleRef = { exports: {} };
  // axios 只为顶部的 import 服务：SSR 不跑 onMounted，这里给个不发请求的替身
  const harnessRequire = (id) =>
    id === "axios" ? { get: async () => ({ data: {} }) } : frontendRequire(id);
  new Function("module", "exports", "require", bundled.outputFiles[0].text)(
    moduleRef,
    moduleRef.exports,
    harnessRequire,
  );
  return moduleRef.exports.default || moduleRef.exports;
}

async function render(source, props) {
  const app = Vue.createSSRApp({ render: () => Vue.h(buildComponent(source), props) });
  return await renderToString(app);
}

const BUILTIN_TITLE = "选择要禁用的工具";
const DYNAMIC_TITLE = "自定义 API 与 MCP 扩展工具禁用";
const SKILLS_TITLE = "禁用选定的公共技能";
const ORPHAN_TITLE = "其他已禁用项（历史）";

const summary = (html) => ({
  hasBuiltin: html.includes(BUILTIN_TITLE),
  hasDynamic: html.includes(DYNAMIC_TITLE),
  hasSkills: html.includes(SKILLS_TITLE),
  toolPlaceholder: html.includes("搜索工具名..."),
  skillPlaceholder: html.includes("搜索技能名..."),
  orphanTitle: html.includes(ORPHAN_TITLE),
  orphanSaysTool: html.includes("这些工具已不在当前目录中"),
  orphanSaysSkill: html.includes("这些技能已不在当前目录中"),
});

(async () => {
  const source = fs.readFileSync(COMPONENT, "utf8");
  const orphanSelected = ["skill:retired"];

  process.stdout.write(
    JSON.stringify(
      {
        // 工具模式：不传 resource（默认）与显式 tools 必须完全一致
        toolsDefault: summary(await render(source, { modelValue: [] })),
        toolsExplicit: summary(await render(source, { modelValue: [], resource: "tools" })),
        // skills 模式：只有一个技能大组，工具的两个大组一个都不许出现
        skills: summary(await render(source, { modelValue: [], resource: "skills" })),
        // 目录尚未加载（SSR / 加载中）时，已禁用但查不到的项仍要可见可解除
        skillsWithOrphan: summary(await render(source, { modelValue: orphanSelected, resource: "skills" })),
        toolsWithOrphan: summary(await render(source, { modelValue: orphanSelected, resource: "tools" })),
      },
      null,
      2,
    ),
  );
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
