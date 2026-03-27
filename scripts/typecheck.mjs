import path from "node:path";
import { spawnSync } from "node:child_process";

const repoRoot = process.cwd();
const nextBin = path.join(repoRoot, "node_modules", "next", "dist", "bin", "next");
const tscBin = path.join(repoRoot, "node_modules", "typescript", "bin", "tsc");

function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: repoRoot,
    stdio: "inherit",
  });

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

run(process.execPath, [nextBin, "typegen"]);
run(process.execPath, [tscBin, "--project", "tsconfig.typecheck.json", "--noEmit", "--incremental", "false"]);
