import { existsSync } from 'node:fs';

export function isPublicKey(key) {
  if (/^sb_publishable_[A-Za-z0-9_-]+$/.test(key ?? '')) return true;
  try {
    const parts = key.split('.');
    return parts.length === 3 && JSON.parse(Buffer.from(parts[1], 'base64url')).role === 'anon';
  } catch { return false; }
}

export function validatePublicEnv(env) {
  const key = env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!isPublicKey(key)) throw new Error('공개용 Supabase publishable/anon 키가 필요합니다. 관리자·secret 키는 웹 빌드에 사용할 수 없습니다.');
  if (env.NEXT_PUBLIC_SUPABASE_ANON_KEY && !isPublicKey(env.NEXT_PUBLIC_SUPABASE_ANON_KEY)) {
    throw new Error('기존 NEXT_PUBLIC_SUPABASE_ANON_KEY의 관리자 키도 제거하세요.');
  }
  for (const [name, value] of Object.entries(env)) {
    if (!name.startsWith('NEXT_PUBLIC_') || !value) continue;
    let privileged = value.startsWith('sb_secret_');
    try { privileged ||= JSON.parse(Buffer.from(value.split('.')[1], 'base64url')).role === 'service_role'; } catch { /* not JWT */ }
    if (privileged) throw new Error(`${name}: 서버 자격증명을 공개 환경변수에 넣을 수 없습니다.`);
  }
  const url = new URL(env.NEXT_PUBLIC_SUPABASE_URL);
  if (url.protocol !== 'https:' && !['localhost', '127.0.0.1'].includes(url.hostname)) throw new Error('Supabase URL에는 HTTPS가 필요합니다.');
}

if (process.argv[1]?.endsWith('check-public-env.mjs')) {
  for (const file of ['.env.local', '.env']) if (existsSync(file)) process.loadEnvFile(file);
  try { validatePublicEnv(process.env); console.log('공개 환경변수 검사 통과'); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
