import { prisma } from '@/lib/prisma';
import { ok, notFound } from '@/lib/http';
import { getCurrentUser, requireUser } from '@/lib/auth';

type Params = { id: string };

export async function GET(
  _req: Request,
  ctx: { params: Promise<Params> }
) {
  const user = await getCurrentUser();
  const err = requireUser(user);
  if (err) return err;

  const { id } = await ctx.params;

  const order = await prisma.order.findFirst({
    where: { id, userId: user!.id },
    select: {
      id: true,
      seq: true,
      status: true,
      currency: true,
      subtotalCents: true,
      discountCents: true,
      shippingCents: true,
      taxCents: true,
      totalCents: true,
      createdAt: true,
      couponCode: true,
      items: {
        select: {
          id: true,
          variantId: true,
          sku: true,
          title: true,
          quantity: true,
          priceCents: true,
          currency: true,
        },
      },
      payments: {
        select: {
          id: true,
          provider: true,
          amountCents: true,
          currency: true,
          status: true,
          createdAt: true,
        },
      },
      shipments: {
        select: {
          id: true,
          carrier: true,
          service: true,
          trackingNumber: true,
          status: true,
          createdAt: true,
        },
      },
      addresses: {
        select: {
          id: true,
          type: true, // SHIPPING / BILLING
          firstName: true,
          lastName: true,
          line1: true, line2: true,
          city: true, region: true, postalCode: true, country: true,
        },
      },
    },
  });

  if (!order) return notFound('Order not found');
  return ok(order);
}
