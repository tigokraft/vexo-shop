import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET() {
  const brands = await prisma.brand.count();
  return NextResponse.json({ ok: true, brands, now: new Date().toISOString() });
}
