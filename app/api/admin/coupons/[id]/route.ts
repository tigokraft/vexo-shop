import { prisma } from '@/lib/prisma';
import { ok, badRequest, notFound, unauthorized } from '@/lib/http';
import { getCurrentUser, requireAdmin } from '@/lib/auth';
import { z } from 'zod';

const UpdateSchema = z.object({
  code: z.string().min(3).max(64).optional(),
  type: z.enum(['PERCENT', 'FIXED']).optional(),
  percentOff: z.number().int().min(1).max(100).nullable().optional(),
  amountOffCents: z.number().int().min(1).nullable().optional(),
  minSubtotalCents: z.number().int().min(0).optional(),
  startsAt: z.string().datetime().nullable().optional(),
  endsAt: z.string().datetime().nullable().optional(),
  active: z.boolean().optional(),
  maxRedemptions: z.number().int().min(0).nullable().optional(),
  onePerCustomer: z.boolean().optional(),
});

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const user = await getCurrentUser();
  const authError = requireAdmin(user);
  if (authError) return unauthorized('Admin only');

  const { id } = await ctx.params;
  const c = await prisma.coupon.findUnique({ where: { id } });
  if (!c) return notFound('Coupon not found');
  return ok(c);
}

export async function PUT(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const user = await getCurrentUser();
  const authError = requireAdmin(user);
  if (authError) return unauthorized('Admin only');

  const { id } = await ctx.params;
  const json = await req.json().catch(() => ({}));
  const parsed = UpdateSchema.safeParse(json);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());

  const existing = await prisma.coupon.findUnique({ where: { id } });
  if (!existing) return notFound('Coupon not found');

  // Basic validation coherence
  if (parsed.data.type === 'PERCENT' && parsed.data.percentOff == null) {
    return badRequest('percentOff is required when type=PERCENT');
  }
  if (parsed.data.type === 'FIXED' && parsed.data.amountOffCents == null) {
    return badRequest('amountOffCents is required when type=FIXED');
  }

  const updated = await prisma.coupon.update({
    where: { id },
    data: {
      ...('code' in parsed.data ? { code: parsed.data.code } : {}),
      ...('type' in parsed.data ? { type: parsed.data.type } : {}),
      percentOff: 'percentOff' in parsed.data ? parsed.data.percentOff : existing.percentOff,
      amountOffCents: 'amountOffCents' in parsed.data ? parsed.data.amountOffCents : existing.amountOffCents,
      ...('minSubtotalCents' in parsed.data ? { minSubtotalCents: parsed.data.minSubtotalCents } : {}),
      ...('startsAt' in parsed.data ? { startsAt: parsed.data.startsAt ? new Date(parsed.data.startsAt) : null } : {}),
      ...('endsAt' in parsed.data ? { endsAt: parsed.data.endsAt ? new Date(parsed.data.endsAt) : null } : {}),
      ...('active' in parsed.data ? { active: parsed.data.active } : {}),
      ...('maxRedemptions' in parsed.data ? { maxRedemptions: parsed.data.maxRedemptions } : {}),
      ...('onePerCustomer' in parsed.data ? { onePerCustomer: parsed.data.onePerCustomer } : {}),
    },
  });

  return ok(updated);
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const user = await getCurrentUser();
  const authError = requireAdmin(user);
  if (authError) return unauthorized('Admin only');

  const { id } = await ctx.params;
  await prisma.coupon.delete({ where: { id } });
  return ok({ ok: true });
}
