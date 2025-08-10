import { badRequest, ok, serverError } from '@/lib/http';
import { getOrCreateCart, computeTotals } from '@/lib/cart';
import { getCurrentUser } from '@/lib/auth';
import { getDefaultWarehouseId } from '@/lib/warehouse';
import { prisma } from '@/lib/prisma';
import { z } from 'zod';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const bodySchema = z.object({
  email: z.string().email().optional(),
});

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const parsed = bodySchema.safeParse(body);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());

  try {
    const user = await getCurrentUser();
    const cart = await getOrCreateCart();
    if (!cart.items.length) return badRequest('Cart is empty');

    const totals = await computeTotals(cart);
    const email = parsed.data.email ?? user?.email ?? 'buyer@local.test';
    const whId = await getDefaultWarehouseId();

    const order = await prisma.$transaction(async (tx) => {
      // 1) Create order + items (nested)
      const o = await tx.order.create({
        data: {
          ...(user ? { user: { connect: { id: user.id } } } : {}),
          email,
          currency: cart.currency,
          subtotalCents: totals.subtotal,
          discountCents: totals.discount,
          shippingCents: totals.shipping,
          taxCents: totals.tax,
          totalCents: totals.total,
          status: 'PAID',
          items: {
            create: cart.items.map((it: any) => {
              const unit = Number(it.priceCents ?? it.variant?.priceCents ?? 0);
              const qty = Number(it.quantity ?? 0);
              return {
                variantId: it.variantId,
                sku: it.sku ?? it.variant?.sku ?? '',
                title: it.title ?? it.variant?.title ?? '',
                quantity: qty,
                priceCents: unit,
                totalCents: unit * qty,   // ← REQUIRED by your schema
                currency: cart.currency,
              };
            }),
          },
        },
        include: { items: true },
      });

      // 2) Stock: consume reserved -> onHand, and release reservation
      for (const it of cart.items) {
        const key = { variantId_warehouseId: { variantId: it.variantId, warehouseId: whId } };
        const level = await tx.stockLevel.upsert({
          where: key,
          update: {},
          create: { variantId: it.variantId, warehouseId: whId, onHand: 0, reserved: 0 },
        });

        const qty = it.quantity;
        const newReserved = Math.max(0, level.reserved - qty);
        const newOnHand = Math.max(0, level.onHand - qty);

        await tx.stockLevel.update({ where: key, data: { reserved: newReserved, onHand: newOnHand } });
        await tx.stockMovement.create({
          data: {
            variantId: it.variantId,
            warehouseId: whId,
            type: 'ADJUSTMENT',
            delta: -qty,
            reason: 'order_paid',
          },
        });
      }

      // 3) Clear cart
      await tx.cartItem.deleteMany({ where: { cartId: cart.id } });
      return o;
    });

    return ok({
      order: {
        id: order.id,
        currency: cart.currency,
        totalCents: totals.total,
        items: order.items.map((i: any) => ({
          id: i.id,
          variantId: i.variantId,
          sku: i.sku,
          title: i.title,
          quantity: i.quantity,
          priceCents: i.priceCents,
          totalCents: i.totalCents,
        })),
      },
    });
  } catch (e: any) {
    return serverError('Checkout failed', e);
  }
}
