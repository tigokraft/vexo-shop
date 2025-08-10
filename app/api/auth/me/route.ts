import { NextResponse } from 'next/server';
import { getCurrentUser } from '@/lib/auth';

export const runtime = 'nodejs';

export async function GET() {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ user: null }, { status: 401 });
  const { id, email, role, name, createdAt } = user;
  return NextResponse.json({ user: { id, email, role, name, createdAt } });
}
