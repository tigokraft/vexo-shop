import { NextResponse } from 'next/server';
import { z } from 'zod';
import { prisma } from '@/lib/prisma';
import { createSessionRecord, hashPassword, setSessionCookie } from '@/lib/auth';

export const runtime = 'nodejs';

const bodySchema = z.object({
  email: z.string().email().max(255),
  password: z.string().min(8).max(100),
  name: z.string().min(1).max(100).optional(),
});

export async function POST(req: Request) {
  const data = bodySchema.safeParse(await req.json());
  if (!data.success) {
    return NextResponse.json({ error: 'Invalid payload', issues: data.error.format() }, { status: 400 });
  }
  const { email, password, name } = data.data;
  const lower = email.toLowerCase().trim();

  const existing = await prisma.user.findUnique({ where: { email: lower } });
  if (existing) {
    return NextResponse.json({ error: 'Email already in use' }, { status: 409 });
  }

  const hashed = await hashPassword(password);
  const user = await prisma.user.create({
    data: { email: lower, hashedPassword: hashed, name, role: 'CUSTOMER', status: 'ACTIVE' },
    select: { id: true, email: true, role: true, name: true, createdAt: true },
  });

  const { token, expiresAt } = await createSessionRecord(user.id, req.headers);
  const res = NextResponse.json({ user });
  await setSessionCookie(res, token, expiresAt);
  return res;
}
