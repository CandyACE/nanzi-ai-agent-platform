/**
 * 真渲染 ModelSelect.vue：验证触发器文案与禁用态，以及未展开时不产生浮层。
 *
 * 为什么用真编译而不是字符串断言：这是单文件组件，Node 不能直接 require。
 * 这里用 vue/compiler-sfc 编译真实源码、esbuild 剥 TS、@vue/server-renderer 真渲染，
 * 不复制任何模板逻辑。
 *
 * 打开浮层、点击选中、键盘导航属于交互，SSR 渲染不出来，那部分由
 * test_model_select_contract.py（源码契约）与 test_model_select_behavior.py（纯函数行为）覆盖。
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

const COMPONENT = path.resolve("src/components/common/ModelSelect.vue");
const frontendRequire = (id) => require(require.resolve(id, { paths: [process.cwd()] }));

function buildComponent(source) {
  const { descriptor, errors } = parse(source, { filename: COMPONENT });
  if (errors.length) throw new Error("parse: " + errors.map(String).join("; "));

  const script = compileScript(descriptor, { id: "model-select" });
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename: COMPONENT,
    id: "model-select",
    compilerOptions: { bindingMetadata: script.bindings },
  });
  if (tpl.errors.length) throw new Error("template: " + tpl.errors.map(String).join("; "));

  // 组件还 import 了 utils/modelSelect，所以交给 esbuild 打包：
  // resolveDir 指向组件目录，相对导入能正常解析；vue 保持 external，保证与宿主同一实例。
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
      sourcefile: "ModelSelect.entry.ts",
    },
    bundle: true,
    write: false,
    format: "cjs",
    platform: "node",
    target: "node18",
    external: ["vue"],
    logLevel: "silent",
  });

  const moduleRef = { exports: {} };
  new Function("module", "exports", "require", bundled.outputFiles[0].text)(
    moduleRef,
    moduleRef.exports,
    frontendRequire,
  );
  return moduleRef.exports.default || moduleRef.exports;
}

const MODELS = [
  { model_id: "deepseek-v3-2", name: "DeepSeek-V3.2", type: "llm", is_active: true },
  { model_id: "qwen-vl-max", name: "Qwen-VL-Max", type: "multimodal", is_active: true },
];

async function render(source, props) {
  const app = Vue.createSSRApp({ render: () => Vue.h(buildComponent(source), props) });
  const ctx = {};
  const html = await renderToString(app, ctx);
  const teleport = (ctx.teleports && ctx.teleports.body) || "";
  return { html, teleport };
}

const summary = ({ html, teleport }) => ({
  html,
  hasListbox: /role="listbox"/.test(html) || /role="listbox"/.test(teleport),
  teleportEmpty: teleport.trim() === "",
});

(async () => {
  const source = fs.readFileSync(COMPONENT, "utf8");

  const selected = summary(await render(source, { modelValue: "deepseek-v3-2", models: MODELS }));
  const placeholder = summary(await render(source, {
    modelValue: "",
    models: MODELS,
    placeholder: "选择编排模型...",
  }));
  const followUpstream = summary(await render(source, {
    modelValue: "",
    models: MODELS,
    allowEmpty: true,
    emptyLabel: "跟随编排模型",
  }));
  const multimodalWithId = summary(await render(source, {
    modelValue: "qwen-vl-max",
    models: MODELS,
    showModelId: true,
  }));
  const disabled = summary(await render(source, {
    modelValue: "",
    models: MODELS,
    disabled: true,
    disabledHint: "当前版本不可编辑，无法切换模型",
  }));
  const unknownValue = summary(await render(source, {
    modelValue: "env-injected-model",
    models: MODELS,
    showModelId: true,
    unknownOptionLabel: "未知/环境变量",
  }));

  process.stdout.write(JSON.stringify({
    selected: { showsModelName: selected.html.includes("DeepSeek-V3.2"), closedNoListbox: !selected.hasListbox },
    placeholder: { showsPlaceholder: placeholder.html.includes("选择编排模型...") },
    followUpstream: { showsEmptyLabel: followUpstream.html.includes("跟随编排模型") },
    multimodalWithId: { showsId: multimodalWithId.html.includes("Qwen-VL-Max (qwen-vl-max)") },
    disabled: {
      triggerDisabled: /<button[^>]*disabled/.test(disabled.html),
      keepsHint: disabled.html.includes("当前版本不可编辑，无法切换模型"),
    },
    unknownValue: {
      showsUnknownLabel: unknownValue.html.includes("env-injected-model (未知/环境变量)"),
    },
  }, null, 2));
})();
