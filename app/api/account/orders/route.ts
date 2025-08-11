import { prisma } from '@/lib/prisma';
import { ok, unauthorized } from '@/lib/http';
import { getCurrentUser, requireUser } from '@/lib/auth';

export async function GET() {
  const user = await getCurrentUser();
  const err = requireUser(user);
  if (err) return err;

  const orders = await prisma.order.findMany({
    where: { userId: user!.id },
    orderBy: { createdAt: 'desc' },
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
      items: {
        select: {
          id: true,
          sku: true,
          title: true,
          quantity: true,
          priceCents: true,
          currency: true,
        },
      },
    },
  });

  return ok({ items: orders });
}
