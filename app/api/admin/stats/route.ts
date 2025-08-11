import { prisma } from '@/lib/prisma';
import { ok } from '@/lib/http';
import { getCurrentUser, requireAdmin } from '@/lib/auth';

// helper: last N days ISO dates
function daysBack(n: number) {
  const out: string[] = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(now.getDate() - i);
    out.push(d.toISOString().slice(0, 10));
  }
  return out;
}

export async function GET() {
  const user = await getCurrentUser();
  const err = requireAdmin(user);
  if (err) return err;

  // Only paid/fulfilled should count toward revenue
  const revenueStatuses = ['PAID', 'FULFILLED', 'PARTIALLY_FULFILLED'] as const;

  // KPIs
  const [ordersCount, revenueAgg, itemsAgg] = await Promise.all([
    prisma.order.count({ where: { status: { in: revenueStatuses as any } } }),
    prisma.order.aggregate({
      where: { status: { in: revenueStatuses as any } },
      _sum: { totalCents: true, subtotalCents: true, shippingCents: true, taxCents: true, discountCents: true },
    }),
    prisma.orderItem.aggregate({
      _sum: { quantity: true },
    }),
  ]);

  const totalRevenueCents = revenueAgg._sum.totalCents ?? 0;
  const totalUnits = itemsAgg._sum.quantity ?? 0;

  // Orders by day (last 30d)
  const since = new Date();
  since.setDate(since.getDate() - 29);

  const recent = await prisma.order.findMany({
    where: { createdAt: { gte: since } },
    select: { id: true, createdAt: true, totalCents: true, status: true },
    orderBy: { createdAt: 'asc' },
  });

  const byDay = Object.fromEntries(daysBack(30).map(d => [d, { orders: 0, revenueCents: 0 }]));
  for (const o of recent) {
    const day = o.createdAt.toISOString().slice(0, 10);
    if (!byDay[day]) byDay[day] = { orders: 0, revenueCents: 0 };
    byDay[day].orders += 1;
    if (revenueStatuses.includes(o.status as any)) byDay[day].revenueCents += o.totalCents;
  }

  // Top SKUs (last 30d) by revenue + units
  const recentItems = await prisma.orderItem.findMany({
    where: { order: { createdAt: { gte: since } } },
    select: { sku: true, title: true, quantity: true, priceCents: true, currency: true },
  });

  const topMap = new Map<string, { sku: string; title: string; units: number; revenueCents: number; currency: string }>();
  for (const it of recentItems) {
    const key = it.sku;
    const curr = topMap.get(key) ?? { sku: it.sku, title: it.title, units: 0, revenueCents: 0, currency: it.currency };
    curr.units += it.quantity;
    curr.revenueCents += it.quantity * it.priceCents;
    topMap.set(key, curr);
  }
  const topSkus = Array.from(topMap.values())
    .sort((a, b) => b.revenueCents - a.revenueCents)
    .slice(0, 10);

  return ok({
    kpis: {
      orders: ordersCount,
      revenueCents: totalRevenueCents,
      units: totalUnits,
      aovCents: ordersCount ? Math.round(totalRevenueCents / ordersCount) : 0,
    },
    byDay,
    topSkus,
  });
}
