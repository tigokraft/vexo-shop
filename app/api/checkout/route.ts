import { badRequest, ok, serverError } from '@/lib/http';
import { getOrCreateCart, computeTotals, reserveStock } from '@/lib/cart';
import { getCurrentUser } from '@/lib/auth';
import { prisma } from '@/lib/prisma';
import { z } from 'zod';

export const runtime = 'nodejs';

const bodySchema = z.object({
  email: z.string().email().optional(), // if not logged in
  payment: z.object({
    provider: z.literal('manual'),
    capture: z.boolean().default(true),
  }).default({ provider: 'manual', capture: true }),
  shippingAddressId: z.string().uuid().optional(),
  billingAddressId: z.string().uuid().optional(),
});

export async function POST(req: Request) {
  const user = await getCurrentUser();
  const payload = await req.json().catch(() => null);
  const parsed = bodySchema.safeParse(payload);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());

  try {
    const cart = await getOrCreateCart();
    if (cart.items.length === 0) return badRequest('Cart is empty');

    const email = user?.email ?? parsed.data.email;
    if (!email) return badRequest('Email required');

    // Final availability check
    for (const it of cart.items) {
      const v = await prisma.productVariant.findUnique({ where: { id: it.variantId }, include: { stockLevels: true } });
      if (!v) return badRequest(`Variant ${it.variantId} missing`);
      const available = v.stockLevels.reduce((acc, s) => acc + (s.onHand - s.reserved), 0);
      if (v.trackInventory && it.quantity > available) {
        return badRequest(`Insufficient stock for ${v.sku}`);
      }
    }

    const totals = await computeTotals(cart);

    const order = await prisma.$transaction(async (tx) => {
      // Create order
      const o = await tx.order.create({
        data: {
          userId: user?.id ?? null,
          email,
          currency: totals.currency,
          subtotalCents: totals.subtotal,
          discountCents: totals.discount,
          shippingCents: totals.shipping,
          taxCents: totals.tax,
          totalCents: totals.total,
          status: 'PAID', // manual provider
          couponId: cart.couponId ?? null,
          shippingAddressId: parsed.data.shippingAddressId ?? null,
          billingAddressId: parsed.data.billingAddressId ?? null,
        },
      });

      // Items
      for (const it of cart.items) {
        const v = await tx.productVariant.findUnique({
          where: { id: it.variantId },
          include: { product: true },
        });
        if (!v) throw new Error('Variant vanished during checkout');
        await tx.orderItem.create({
          data: {
            orderId: o.id,
            variantId: v.id,
            sku: v.sku,
            title: v.title,
            priceCents: v.priceCents,
            currency: v.currency,
            quantity: it.quantity,
          },
        });
      }

      // Reduce onHand and release reserved
      for (const it of cart.items) {
        // Reserve was already held; convert reserved -> onHand reduction
        await commitStockForCheckout(tx, it.variantId, it.quantity);
      }

      // Clear cart
      await tx.cartItem.deleteMany({ where: { cartId: cart.id } });
      await tx.cart.update({ where: { id: cart.id }, data: { couponId: null } });

      return o;
    });

    return ok({ orderId: order.id, status: order.status, totalCents: totals.total });
  } catch (e: any) {
    return serverError('Checkout failed', e);
  }
}

// helper: adjust per default warehouse
async function commitStockForCheckout(tx: any, variantId: string, qty: number) {
  const { getDefaultWarehouseId } = await import('@/lib/warehouse');
  const wh = await getDefaultWarehouseId();
  const level = await tx.stockLevel.upsert({
    where: { variantId_warehouseId: { variantId, warehouseId: wh } },
    update: {},
    create: { variantId, warehouseId: wh, onHand: 0, reserved: 0 },
  });
  const newReserved = Math.max(0, level.reserved - qty);
  const newOnHand = Math.max(0, level.onHand - qty);
  await tx.stockLevel.update({
    where: { variantId_warehouseId: { variantId, warehouseId: wh } },
    data: { onHand: newOnHand, reserved: newReserved },
  });
  await tx.stockMovement.create({
    data: { variantId, warehouseId: wh, type: 'ADJUSTMENT', delta: -qty, reason: 'checkout_commit' },
  });
}
