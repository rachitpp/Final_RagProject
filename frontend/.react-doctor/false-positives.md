# React Doctor — confirmed false positives

Patterns here are suppressed on every scan. Each entry explains *why* it is a
false positive so a future reviewer can re-evaluate.

## react-doctor/async-await-in-loop — src/lib/api.ts (streamChat)

`while (true) { const { done, value } = await reader.read(); ... }` reads a
`ReadableStream` body sequentially. Stream reads are inherently ordered — each
`read()` must resolve before the next — so they cannot be fanned out with
`Promise.all`. The rule's own validation prompt says to suppress when
"iterations must complete in order for correctness." Converting this would break
token streaming.

## deslop/unused-dev-dependency — react-doctor, shadcn

Both are CLI tools, never `import`ed from source, so the "no importer" heuristic
flags them:

- `react-doctor` — run via `npm run doctor` / `npx react-doctor` and in CI.
- `shadcn` — the component-scaffolding CLI (`npx shadcn add ...`). Lives in
  `devDependencies` because it's build-time tooling, not shipped code.

Keep both.
