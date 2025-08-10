import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { clearSessionCookie } from '@/lib/auth';
import { createHash } from 'crypto';
import { cookies } from 'next/headers';

export const runtime = 'nodejs';

const COOKIE_NAME = process.env.SESSION_COOKIE_NAME ?? 'auth_session';
const SESSION_SECRET = process.env.SESSION_SECRET ?? 'dev-secret-change-me';
function sha256(input: string) {
  return createHash('sha256').update(input + SESSION_SECRET).digest('hex');
}

export async function POST() {
  const cookieStore = await cookies();
  const token = cookieStore.get(COOKIE_NAME)?.value;

  const res = NextResponse.json({ ok: true });
  if (token) {
    const tokenHash = sha256(token);
    await prisma.session.updateMany({
      where: { tokenHash, revokedAt: null },
      data: { revokedAt: new Date() },
    });
  }
  await clearSessionCookie(res);
  return res;
}
