import { badRequest, ok, serverError } from '@/lib/http';
import { getOrCreateCart, ensureAvailability, reserveStock } from '@/lib/cart';
import { z } from 'zod';
import { prisma } from '@/lib/prisma';

export const runtime = 'nodejs';

const bodySchema = z.object({
  variantId: z.string().uuid(),
  quantity: z.number().int().min(1).max(999).default(1),
});

export async function POST(req: Request) {
  const body = await req.json().catch(() => null);
  const parsed = bodySchema.safeParse(body);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());

  try {
    const cart = await getOrCreateCart();
    const { variantId, quantity } = parsed.data;

    const existing = cart.items.find((i) => i.variantId === variantId);
    const need = (existing?.quantity ?? 0) + quantity;
    const avail = await ensureAvailability(variantId, need);
    if (!avail.ok) return badRequest(avail.reason);

    await prisma.$transaction(async (tx) => {
      const variant = await tx.productVariant.findUnique({ where: { id: variantId } });
      if (!variant) throw new Error('Variant missing');

      if (existing) {
        await tx.cartItem.update({
          where: { id: existing.id },
          data: { quantity: existing.quantity + quantity },
        });
      } else {
        await tx.cartItem.create({
          data: {
            cartId: cart.id,
            variantId,
            quantity,
            // snapshots required by your schema:
            priceCentsAtAdd: variant.priceCents,
            priceCents: variant.priceCents,    // ✅ add this
            sku: variant.sku,                  // ✅ already added before
            title: variant.title,              // ✅ already added before
            // if your schema has currency on CartItem, set it too:
            // currency: variant.currency ?? cart.currency,
          },
        });
      }
    });

    await reserveStock(variantId, quantity);

    const fresh = await getOrCreateCart();
    return ok({ cartId: fresh.id, items: fresh.items.length });
  } catch (e: any) {
    return serverError('Failed to add item', e);
  }
}
