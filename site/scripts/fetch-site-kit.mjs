// Sparse-fetch the shared @weft/site-kit into vendor/site-kit/.
//
// The kit lives in a SUBDIRECTORY (packages/site-kit) of a DIFFERENT repo
// (foundryside-dev/weft). npm cannot install a git subdirectory directly, so this
// is the sanctioned realization of the "git subdirectory dependency" decision
// (IA §1.3, §6): a depth-1, blobless, sparse clone of just packages/site-kit,
// copied into ./vendor/site-kit, which package.json then consumes as
// "@weft/site-kit": "file:./vendor/site-kit".
//
// Runs as a `preinstall` hook so the vendor copy exists before `npm install`
// resolves the file: dependency, and is re-run by the Pages deploy workflow.
// The vendor copy is .gitignored — it is regenerated, never committed.
import { rm, mkdir, cp } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';

const here = dirname(fileURLToPath(import.meta.url));
const siteRoot = join(here, '..');
const vendorDir = join(siteRoot, 'vendor', 'site-kit');

const REPO = process.env.WEFT_SITE_KIT_REPO || 'https://github.com/foundryside-dev/weft.git';
const REF = process.env.WEFT_SITE_KIT_REF || 'main';
const SUBDIR = 'packages/site-kit';

// Escape hatch: if the kit is already vendored and an offline build is wanted,
// set WEFT_SITE_KIT_SKIP_FETCH=1 to reuse the existing copy.
if (process.env.WEFT_SITE_KIT_SKIP_FETCH && existsSync(vendorDir)) {
  console.log(`[fetch-site-kit] WEFT_SITE_KIT_SKIP_FETCH set — reusing ${vendorDir}`);
  process.exit(0);
}

const git = (args, cwd) =>
  execFileSync('git', args, { cwd, stdio: ['ignore', 'pipe', 'inherit'] });

const tmp = join(tmpdir(), `weft-site-kit-${process.pid}-${Date.now()}`);

try {
  console.log(`[fetch-site-kit] sparse-fetching ${SUBDIR} from ${REPO}@${REF} …`);
  git(['clone', '--depth', '1', '--filter=blob:none', '--sparse', '--branch', REF, REPO, tmp]);
  git(['sparse-checkout', 'set', SUBDIR], tmp);

  const srcKit = join(tmp, SUBDIR);
  if (!existsSync(srcKit)) {
    throw new Error(`expected ${SUBDIR} in the sparse checkout but it is missing`);
  }

  await rm(vendorDir, { recursive: true, force: true });
  await mkdir(dirname(vendorDir), { recursive: true });
  await cp(srcKit, vendorDir, { recursive: true });
  console.log(`[fetch-site-kit] vendored -> ${vendorDir}`);
} catch (err) {
  if (existsSync(vendorDir)) {
    console.warn(
      `[fetch-site-kit] fetch failed (${err.message}); reusing existing ${vendorDir}`,
    );
  } else {
    console.error(`[fetch-site-kit] fetch failed and no vendored copy exists: ${err.message}`);
    process.exit(1);
  }
} finally {
  await rm(tmp, { recursive: true, force: true });
}
