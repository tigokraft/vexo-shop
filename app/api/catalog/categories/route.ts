import { prisma } from '@/lib/prisma';
import { ok } from '@/lib/http';

export const runtime = 'nodejs';

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const parent = searchParams.get('parent'); // slug of parent or "root"
  const page = Math.max(1, Number(searchParams.get('page') ?? '1'));
  const pageSize = Math.min(100, Math.max(1, Number(searchParams.get('pageSize') ?? '50')));

  let where: any = {};
  if (parent === 'root') where.parentId = null;
  else if (parent) {
    const parentCat = await prisma.category.findUnique({ where: { slug: parent } });
    if (!parentCat) return ok({ items: [], page, pageSize, total: 0, hasMore: false }, { headers: { 'Cache-Control': 'public, s-maxage=60' } });
    where.parentId = parentCat.id;
  }

  const [total, items] = await Promise.all([
    prisma.category.count({ where }),
    prisma.category.findMany({
      where,
      orderBy: [{ position: 'asc' }, { name: 'asc' }],
      skip: (page - 1) * pageSize,
      take: pageSize,
      include: { parent: true },
    }),
  ]);

  return ok({ items, page, pageSize, total, hasMore: page * pageSize < total }, { headers: { 'Cache-Control': 'public, s-maxage=60' } });
}
