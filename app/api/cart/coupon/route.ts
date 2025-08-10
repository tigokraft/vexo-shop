import { badRequest, notFound, ok, serverError } from '@/lib/http';
import { getOrCreateCart } from '@/lib/cart';
import { prisma } from '@/lib/prisma';
import { z } from 'zod';

export const runtime = 'nodejs';

const applySchema = z.object({
  code: z.string().min(2).max(64),
});

export async function POST(req: Request) {
  const body = await req.json().catch(() => null);
  const parsed = applySchema.safeParse(body);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());

  try {
    const cart = await getOrCreateCart();
    const code = parsed.data.code.trim().toUpperCase();

    const coupon = await prisma.coupon.findFirst({ where: { code } });
    if (!coupon) return notFound('Coupon not found');

    // Basic activity window check if fields exist
    const now = new Date();
    const active =
      ((coupon as any).isActive ?? true) &&
      (!('startsAt' in coupon) || !(coupon as any).startsAt || (coupon as any).startsAt <= now) &&
      (!('endsAt' in coupon) || !(coupon as any).endsAt || (coupon as any).endsAt >= now);

    if (!active) return badRequest('Coupon is not active');

    const updated = await prisma.cart.update({ where: { id: cart.id }, data: { couponId: coupon.id } });
    return ok({ ok: true, coupon: { id: coupon.id, code: (coupon as any).code } });
  } catch (e: any) {
    return serverError('Failed to apply coupon', e);
  }
}

export async function DELETE() {
  try {
    const cart = await getOrCreateCart();
    await prisma.cart.update({ where: { id: cart.id }, data: { couponId: null } });
    return ok({ ok: true });
  } catch (e: any) {
    return serverError('Failed to remove coupon', e);
  }
}
