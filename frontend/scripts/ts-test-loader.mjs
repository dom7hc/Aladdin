// Development-only TypeScript loader using the platform's existing compiler.
import ts from "typescript";
import { readFile } from "node:fs/promises";
const src = new URL("../src/", import.meta.url);
export async function resolve(specifier, context, next) {
  const mapped = specifier.startsWith("@/") ? new URL(specifier.slice(2), src).href : specifier;
  try { return await next(mapped, context); }
  catch (error) {
    for (const suffix of [".ts", ".tsx", "/index.ts"]) {
      try { return await next(mapped + suffix, context); } catch {}
    }
    throw error;
  }
}
export async function load(url, context, next) {
  // Vite imports JSON without attributes; mirror that for the app modules under test.
  if (url.endsWith(".json") && url.startsWith(src.href)) return {
    format: "module", shortCircuit: true,
    source: `export default ${await readFile(new URL(url), "utf8")};`,
  };
  if (/\.tsx?$/.test(url)) return {
    format: "module", shortCircuit: true,
    source: ts.transpileModule(await readFile(new URL(url), "utf8"), {
      compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022,
        jsx: ts.JsxEmit.ReactJSX },
    }).outputText,
  };
  return next(url, context);
}
