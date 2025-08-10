import { NextResponse } from 'next/server';
import { z } from 'zod';
import { prisma } from '@/lib/prisma';
import { createSessionRecord, setSessionCookie, verifyPassword } from '@/lib/auth';

export const runtime = 'nodejs';

const bodySchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

export async function POST(req: Request) {
  const data = bodySchema.safeParse(await req.json());
  if (!data.success) {
    return NextResponse.json({ error: 'Invalid payload', issues: data.error.format() }, { status: 400 });
  }
  const { email, password } = data.data;
  const lower = email.toLowerCase().trim();

  const user = await prisma.user.findUnique({ where: { email: lower } });
  if (!user || !user.hashedPassword) {
    return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 });
  }

  const ok = await verifyPassword(password, user.hashedPassword);
  if (!ok) {
    return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 });
  }

  const { token, expiresAt } = await createSessionRecord(user.id, req.headers);
  const res = NextResponse.json({
    user: { id: user.id, email: user.email, role: user.role, name: user.name, createdAt: user.createdAt },
  });
  await setSessionCookie(res, token, expiresAt);
  return res;
}
