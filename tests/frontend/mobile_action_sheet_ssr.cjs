/**
 * 真渲染 MobileActionSheet.vue：验证抽屉只在 open 时出现，且带着壳应有的语义。
 *
 * 为什么用真编译而不是字符串断言：这是单文件组件，Node 不能直接 require。
 * 这里用 vue/compiler-sfc 编译真实源码、esbuild 剥 TS、@vue/server-renderer 真渲染，
 * 不复制任何模板逻辑。
 *
 * 为什么看 ctx.teleports：壳把内容 Teleport 到 body，SSR 下 teleport 内容不落在
 * renderToString 的返回值里，而在 SSR context 的 teleports 上。
 *
 * 事件绑定（点击遮罩关闭）SSR 渲染不出来，那部分由 pytest 的源码契约覆盖。
 *
 * 输出 JSON（断言交给 pytest）：{ closed: {...}, opened: {...} }
 * cwd 必须是 frontend。
 */
const fs = require("fs");
const path = require("path");

const fromFrontend = (name) => require(require.resolve(name, { paths: [process.cwd()] }));
const { parse, compileScript, compileTemplate } = fromFrontend("vue/compiler-sfc");
const Vue = fromFrontend("vue");
const { renderToString } = fromFrontend("@vue/server-renderer");
const esbuild = fromFrontend("esbuild");

const COMPONENT = path.resolve("src/components/chat/MobileActionSheet.vue");
const VUE_IMPORT = /import\s*\{([^}]*)\}\s*from\s*['"]vue['"];?/g;

function buildComponent(source) {
  const { descriptor, errors } = parse(source, { filename: COMPONENT });
  if (errors.length) throw new Error("parse: " + errors.map(String).join("; "));

  const script = compileScript(descriptor, { id: "mobile-action-sheet" });
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename: COMPONENT,
    id: "mobile-action-sheet",
    compilerOptions: { bindingMetadata: script.bindings },
  });
  if (tpl.errors.length) throw new Error("template: " + tpl.errors.map(String).join("; "));

  const toDestructure = (code) =>
    code
      .replace(VUE_IMPORT, (_match, names) => `const {${names.replace(/\s+as\s+/g, ": ")}} = Vue;`)
      .replace("export default", "const __sfc =")
      .replace("export function render", "function render");

  const tsCode = toDestructure(script.content) + "\n" + toDestructure(tpl.code);
  const jsCode = esbuild.transformSync(tsCode, { loader: "ts", format: "esm" }).code;
  return new Function("Vue", `${jsCode}\n__sfc.render = render;\nreturn __sfc;`)(Vue);
}

async function render(source, props) {
  const app = Vue.createSSRApp({
    render: () => Vue.h(buildComponent(source), props, { default: () => "抽屉内容占位" }),
  });
  const ctx = {};
  const html = await renderToString(app, ctx);
  const teleport = (ctx.teleports && ctx.teleports.body) || "";

  return {
    bodyHtml: html,
    teleportHtml: teleport,
    hasDialog: /role="dialog"/.test(teleport),
    hasAriaModal: /aria-modal="true"/.test(teleport),
    hasBackdrop: /fixed inset-0 z-\[260\]/.test(teleport),
    hasSafeArea: /safe-area-inset-bottom/.test(teleport),
    hasTitle: teleport.includes("更多操作"),
    hasSubtitle: teleport.includes("解释一行"),
    hasSlot: teleport.includes("抽屉内容占位"),
    hasCancel: teleport.includes("取消"),
  };
}

(async () => {
  const source = fs.readFileSync(COMPONENT, "utf8");
  const closed = await render(source, { open: false, title: "更多操作" });
  const opened = await render(source, { open: true, title: "更多操作", subtitle: "解释一行" });
  process.stdout.write(JSON.stringify({ closed, opened }, null, 2));
})();
