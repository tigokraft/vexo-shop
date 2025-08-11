import { prisma } from '@/lib/prisma';
import { ok, badRequest, unauthorized } from '@/lib/http';
import { getCurrentUser, requireAdmin } from '@/lib/auth';
import { z } from 'zod';

const CreateSchema = z.object({
  code: z.string().min(3).max(64),
  type: z.enum(['PERCENT', 'FIXED']),          // matches your cart logic
  percentOff: z.number().int().min(1).max(100).nullable().optional(),
  amountOffCents: z.number().int().min(1).nullable().optional(),
  minSubtotalCents: z.number().int().min(0).default(0),
  startsAt: z.string().datetime().nullable().optional(),
  endsAt: z.string().datetime().nullable().optional(),
  active: z.boolean().default(true),
  maxRedemptions: z.number().int().min(0).nullable().optional(),
  onePerCustomer: z.boolean().default(false),
});

export async function GET(req: Request) {
  const user = await getCurrentUser();
  const authError = requireAdmin(user);
  if (authError) return unauthorized('Admin only');

  const { searchParams } = new URL(req.url);
  const page = Math.max(parseInt(searchParams.get('page') || '1', 10), 1);
  const pageSize = Math.min(Math.max(parseInt(searchParams.get('pageSize') || '20', 10), 1), 100);
  const q = (searchParams.get('q') || '').trim();

  const where: any = q ? { code: { contains: q, mode: 'insensitive' } } : {};

  const [total, items] = await Promise.all([
    prisma.coupon.count({ where }),
    prisma.coupon.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      skip: (page - 1) * pageSize,
      take: pageSize,
    }),
  ]);

  return ok({ items, page, pageSize, total, hasMore: page * pageSize < total });
}

export async function POST(req: Request) {
  const user = await getCurrentUser();
  const authError = requireAdmin(user);
  if (authError) return unauthorized('Admin only');

  const json = await req.json().catch(() => ({}));
  const parsed = CreateSchema.safeParse(json);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());

  const data = parsed.data;
  if (data.type === 'PERCENT' && !data.percentOff) {
    return badRequest('percentOff is required for PERCENT coupons');
  }
  if (data.type === 'FIXED' && !data.amountOffCents) {
    return badRequest('amountOffCents is required for FIXED coupons');
  }

  const created = await prisma.coupon.create({
    data: {
      code: data.code,
      type: data.type,
      percentOff: data.type === 'PERCENT' ? data.percentOff! : null,
      amountOffCents: data.type === 'FIXED' ? data.amountOffCents! : null,
      minSubtotalCents: data.minSubtotalCents ?? 0,
      startsAt: data.startsAt ? new Date(data.startsAt) : null,
      endsAt: data.endsAt ? new Date(data.endsAt) : null,
      active: data.active ?? true,
      maxRedemptions: data.maxRedemptions ?? null,
      onePerCustomer: data.onePerCustomer ?? false,
    },
  });

  return ok(created);
}
