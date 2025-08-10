import { prisma } from '@/lib/prisma';
import { ok } from '@/lib/http';

export const runtime = 'nodejs';

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const q = (searchParams.get('q') ?? '').trim();
  const where = q ? { OR: [{ name: { contains: q, mode: 'insensitive' } }, { slug: { contains: q, mode: 'insensitive' } }] } : {};
  const items = await prisma.brand.findMany({ where, orderBy: { name: 'asc' } });
  return ok({ items }, { headers: { 'Cache-Control': 'public, s-maxage=120' } });
}
