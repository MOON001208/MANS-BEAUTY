import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
let failures = 0;
function scan(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) { scan(path); continue; }
    if (!/\.(js|html|json|map|txt)$/.test(path)) continue;
    const content = readFileSync(path, 'utf8');
    let unsafe = /sb_secret_[A-Za-z0-9_-]{10,}/.test(content);
    for (const token of content.matchAll(/eyJ[A-Za-z0-9_-]+\.([A-Za-z0-9_-]+)\.[A-Za-z0-9_-]+/g)) {
      try { unsafe ||= JSON.parse(Buffer.from(token[1], 'base64url')).role === 'service_role'; } catch { /* not JWT */ }
    }
    if (unsafe) { console.error(`관리자 키가 포함된 배포 파일: ${path}`); failures++; }
  }
}
scan('out');
if (failures) process.exitCode = 1;
else console.log('배포 파일 관리자 키 검사 통과');
