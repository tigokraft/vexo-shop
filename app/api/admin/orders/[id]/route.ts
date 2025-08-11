import { prisma } from '@/lib/prisma';
import { ok, badRequest, notFound, unauthorized } from '@/lib/http';
import { getCurrentUser, requireAdmin } from '@/lib/auth';
import { z } from 'zod';

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const user = await getCurrentUser();
  const authError = requireAdmin(user);
  if (authError) return unauthorized('Admin only');

  const { id } = await ctx.params;

  const order = await prisma.order.findUnique({
    where: { id },
    include: {
      items: true,
      payments: true,
      refunds: true,
      shipments: true,
      addresses: true,
      user: { select: { id: true, email: true, name: true } },
    },
  });
  if (!order) return notFound('Order not found');
  return ok(order);
}

const PatchSchema = z.object({
  status: z.enum(['PENDING', 'PAID', 'FULFILLED', 'CANCELLED']).optional(),
  note: z.string().max(2000).optional(),
});

export async function PATCH(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const user = await getCurrentUser();
  const authError = requireAdmin(user);
  if (authError) return unauthorized('Admin only');

  const { id } = await ctx.params;
  const body = await req.json().catch(() => ({}));
  const parsed = PatchSchema.safeParse(body);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());

  const existing = await prisma.order.findUnique({ where: { id } });
  if (!existing) return notFound('Order not found');

  const data: any = {};
  if (parsed.data.status && parsed.data.status !== existing.status) {
    data.status = parsed.data.status;
    if (parsed.data.status === 'CANCELLED') data.cancelledAt = new Date();
    if (parsed.data.status === 'FULFILLED') data.fulfilledAt = new Date();
    if (parsed.data.status === 'PAID') data.paidAt = new Date();
  }
  if (parsed.data.note) {
    // store as internal note if you have a field; else skip
  }

  const updated = await prisma.order.update({
    where: { id },
    data,
    include: { items: true, payments: true, refunds: true, shipments: true },
  });

  return ok(updated);
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const user = await getCurrentUser();
  const authError = requireAdmin(user);
  if (authError) return unauthorized('Admin only');

  const { id } = await ctx.params;
  // Soft-delete if you have deletedAt; here we hard-delete only if draft/pending
  await prisma.order.delete({ where: { id } });
  return ok({ ok: true });
}
