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

    // How many we’ll have after this add
    const existing = cart.items.find((i) => i.variantId === variantId);
    const need = (existing?.quantity ?? 0) + quantity;

    // Stock check
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
        // currency: prefer variant.currency, then cart.currency, finally EUR
        const itemCurrency = (variant as any).currency ?? (cart as any).currency ?? 'EUR';

        await tx.cartItem.create({
          data: {
            cartId: cart.id,
            variantId,
            quantity,
            // REQUIRED by your CartItem schema:
            priceCents: variant.priceCents,
            sku: variant.sku,
            title: variant.title ?? '',
            currency: itemCurrency,
          },
        });
      }
    });

    // reserve stock
    await reserveStock(variantId, quantity);

    const fresh = await getOrCreateCart();
    return ok({ cartId: fresh.id, items: fresh.items.length });
  } catch (e: any) {
    return serverError('Failed to add item', e);
  }
}
