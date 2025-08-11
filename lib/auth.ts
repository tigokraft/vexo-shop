// src/lib/auth.ts
import { prisma } from '@/lib/prisma';
import bcrypt from 'bcryptjs';
import { NextResponse } from 'next/server';
import { createHash, randomBytes } from 'crypto';
import { cookies, headers } from 'next/headers';
import type { User, UserRole } from '@prisma/client';

const COOKIE_NAME = process.env.SESSION_COOKIE_NAME ?? 'auth_session';
const SESSION_SECRET = process.env.SESSION_SECRET ?? 'dev-secret-change-me';
const MAX_AGE_DAYS = Number(process.env.SESSION_MAX_AGE_DAYS ?? '30');

function sha256(input: string) {
  return createHash('sha256').update(input + SESSION_SECRET).digest('hex');
}

export async function hashPassword(pw: string) {
  return bcrypt.hash(pw, 12);
}
export async function verifyPassword(pw: string, hash: string) {
  return bcrypt.compare(pw, hash);
}

export async function createSessionRecord(userId: string, reqHeaders?: Headers) {
  const token = randomBytes(32).toString('hex');
  const tokenHash = sha256(token);
  const ua = reqHeaders?.get('user-agent') ?? undefined;
  const ip =
    (reqHeaders?.get('x-forwarded-for')?.split(',')[0]?.trim() ||
      reqHeaders?.get('x-real-ip') ||
      undefined) as string | undefined;

  const expiresAt = new Date(Date.now() + MAX_AGE_DAYS * 24 * 60 * 60 * 1000);

  await prisma.session.create({
    data: { userId, tokenHash, userAgent: ua, ip, expiresAt },
  });

  return { token, expiresAt };
}

export async function setSessionCookie(res: NextResponse, token: string, expiresAt: Date) {
  res.cookies.set(COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    expires: expiresAt,
  });
}

export async function clearSessionCookie(res: NextResponse) {
  res.cookies.set(COOKIE_NAME, '', {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: 0,
  });
}

export async function getCurrentUser() {
  const cookieStore = await cookies(); // <-- Next 15 requires await
  const c = cookieStore.get(COOKIE_NAME)?.value;
  if (!c) return null;

  const tokenHash = sha256(c);
  const now = new Date();
  const session = await prisma.session.findFirst({
    where: { tokenHash, revokedAt: null, expiresAt: { gt: now } },
    include: { user: true },
  });
  return session?.user ?? null;
}

export function requireRole(user: User | null, roles: UserRole[]) {
  if (!user) throw new Error('unauthenticated');
  if (!roles.includes(user.role)) throw new Error('forbidden');
}

export function requireAdmin(
  user: Awaited<ReturnType<typeof getCurrentUser>>
) {
  return requireRole(user, 'ADMIN');
}