import { ok, serverError } from '@/lib/http';
import { getOrCreateCart, computeTotals, reserveStock } from '@/lib/cart';
import { prisma } from '@/lib/prisma';

export const runtime = 'nodejs';
// optional but avoids cache shenanigans for carts:
export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const cart = await getOrCreateCart();
    const totals = await computeTotals(cart);
    return ok({ cart: shape(cart), totals });
  } catch (e: any) {
    return serverError('Failed to load cart', e);
  }
}

export async function DELETE() {
  try {
    const cart = await getOrCreateCart();
    // release reserved stock
    for (const it of cart.items) {
      await reserveStock(it.variantId, -it.quantity);
    }
    await prisma.cartItem.deleteMany({ where: { cartId: cart.id } });
    const fresh = await getOrCreateCart(); // return empty cart
    const totals = await computeTotals(fresh);
    return ok({ cart: shape(fresh), totals });
  } catch (e: any) {
    return serverError('Failed to clear cart', e);
  }
}

/* ---------------- helpers ---------------- */

function shape(cart: NonNullable<Awaited<ReturnType<typeof getOrCreateCart>>>) {
  return {
    id: cart.id,
    currency: cart.currency,
    coupon: cart.coupon
      ? { id: (cart.coupon as any).id, code: (cart.coupon as any).code ?? null }
      : null,
    items: cart.items.map((it: any) => ({
      id: it.id,
      variantId: it.variantId,
      quantity: it.quantity,
      // prefer snapshot stored on CartItem; fall back to live variant
      unitPriceCents: it.priceCents ?? it.variant?.priceCents ?? 0,
      title: it.title ?? it.variant?.title ?? '',
      sku: it.sku ?? it.variant?.sku ?? '',
      product: it.variant?.product
        ? {
            id: it.variant.product.id,
            title: it.variant.product.title,
            slug: it.variant.product.slug,
            image: it.variant.product.images?.[0]?.url ?? null,
          }
        : null,
    })),
  };
}
