import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

async function inspect(directory) {
  const failures = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) failures.push(...await inspect(path));
    else if (/\.(ts|tsx)$/.test(path)) {
      const count = (await readFile(path, 'utf8')).trimEnd().split('\n').length;
      if (count > 150) failures.push(`${path}: ${count} satır (sınır 150)`);
    }
  }
  return failures;
}
const failures = await inspect('src');
if (failures.length) { console.error(failures.join('\n')); process.exitCode = 1; }
else console.log('Kaynak dosyaları 150 satır sınırına uyuyor.');
