import { prisma } from '@/lib/prisma';
import { ok, badRequest, unauthorized } from '@/lib/http';
import { getCurrentUser, requireAdmin } from '@/lib/auth';

export async function GET(req: Request) {
  const user = await getCurrentUser();
  const authError = requireAdmin(user);
  if (authError) return unauthorized('Admin only');

  const { searchParams } = new URL(req.url);
  const page = Math.max(parseInt(searchParams.get('page') || '1', 10), 1);
  const pageSize = Math.min(Math.max(parseInt(searchParams.get('pageSize') || '20', 10), 1), 100);
  const q = (searchParams.get('q') || '').trim();
  const status = (searchParams.get('status') || '').trim().toUpperCase();

  const where: any = {};
  if (q) {
    where.OR = [
      { email: { contains: q, mode: 'insensitive' } },
      { items: { some: { sku: { contains: q, mode: 'insensitive' } } } },
      { id: q.length >= 8 ? { equals: q } : undefined },
    ].filter(Boolean);
  }
  if (status) where.status = status;

  const [total, items] = await Promise.all([
    prisma.order.count({ where }),
    prisma.order.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      skip: (page - 1) * pageSize,
      take: pageSize,
      include: {
        items: true,
        payments: true,
        refunds: true,
        shipments: true,
      },
    }),
  ]);

  return ok({
    items,
    page,
    pageSize,
    total,
    hasMore: page * pageSize < total,
  });
}
