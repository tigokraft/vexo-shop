import { badRequest, notFound, ok, serverError } from '@/lib/http';
import { getOrCreateCart, ensureAvailability, reserveStock } from '@/lib/cart';
import { z } from 'zod';
import { prisma } from '@/lib/prisma';

export const runtime = 'nodejs';

const bodySchema = z.object({
  quantity: z.number().int().min(0).max(999),
});

export async function PATCH(req: Request, ctx: { params: Promise<{ itemId: string }> }) {
  const { itemId } = await ctx.params;
  const body = await req.json().catch(() => null);
  const parsed = bodySchema.safeParse(body);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());

  try {
    const cart = await getOrCreateCart();
    const item = cart.items.find((i) => i.id === itemId);
    if (!item) return notFound('Cart item not found');

    const delta = parsed.data.quantity - item.quantity;
    if (delta > 0) {
      const need = item.quantity + delta;
      const avail = await ensureAvailability(item.variantId, need);
      if (!avail.ok) return badRequest(avail.reason);
    }

    if (parsed.data.quantity === 0) {
      await prisma.cartItem.delete({ where: { id: itemId } });
    } else {
      await prisma.cartItem.update({ where: { id: itemId }, data: { quantity: parsed.data.quantity } });
    }

    await reserveStock(item.variantId, delta);

    const fresh = await getOrCreateCart();
    return ok({ cart: { id: fresh.id, items: fresh.items.length } });
  } catch (e: any) {
    return serverError('Failed to update item', e);
  }
}

export async function DELETE(_req: Request, ctx: { params: Promise<{ itemId: string }> }) {
  const { itemId } = await ctx.params;
  try {
    const cart = await getOrCreateCart();
    const item = cart.items.find((i) => i.id === itemId);
    if (!item) return notFound('Cart item not found');

    await prisma.cartItem.delete({ where: { id: itemId } });
    await reserveStock(item.variantId, -item.quantity);

    const fresh = await getOrCreateCart();
    return ok({ cart: { id: fresh.id, items: fresh.items.length } });
  } catch (e: any) {
    return serverError('Failed to delete item', e);
  }
}
