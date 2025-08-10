import { prisma } from '@/lib/prisma';
import { CART_COOKIE, COOKIE_MAX_AGE_DAYS } from '@/lib/constants';
import { cookies } from 'next/headers';
import { getCurrentUser } from '@/lib/auth';
import { getDefaultWarehouseId } from '@/lib/warehouse';

export type CartWithItems = Awaited<ReturnType<typeof loadCartRaw>>;

export async function loadCartRaw(cartId: string | null) {
  if (!cartId) return null;
  return prisma.cart.findUnique({
    where: { id: cartId },
    include: {
      items: {
        include: {
          variant: {
            include: {
              product: {
                select: {
                  id: true,
                  title: true,
                  slug: true,
                  images: { take: 1, orderBy: { position: 'asc' } },
                },
              },
              stockLevels: true,
            },
          },
        },
      },
      coupon: true,
    },
  });
}

export function cents(n: any) {
  const v = Number(n ?? 0);
  return Number.isFinite(v) ? Math.round(v) : 0;
}

export function nowPlusDays(days: number) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d;
}

export async function getOrCreateCart() {
  const ck = await cookies();
  const cookieId = ck.get(CART_COOKIE)?.value ?? null;
  const user = await getCurrentUser();

  let cart = await loadCartRaw(cookieId);

  if (user) {
    const userCart = await prisma.cart.findFirst({
      where: { userId: user.id },
      include: { items: true, coupon: true },
    });

    if (!cart && userCart) {
      cart = userCart;
    } else if (cart && userCart && cart.id !== userCart.id) {
      await mergeCarts(userCart.id, cart.id);
      await prisma.cart.delete({ where: { id: cart.id } });
      cart = await loadCartRaw(userCart.id);
    } else if (cart && !cart.userId) {
      cart = await prisma.cart.update({ where: { id: cart.id }, data: { userId: user.id } });
    }
  }

  if (!cart) {
    cart = await prisma.cart.create({
      data: { userId: user?.id ?? null, currency: 'EUR' },
    });
  }

  ck.set(CART_COOKIE, cart.id, {
    httpOnly: true,
    sameSite: 'lax',
    path: '/',
    expires: nowPlusDays(COOKIE_MAX_AGE_DAYS),
  });

  return (await loadCartRaw(cart.id))!;
}

export async function mergeCarts(targetCartId: string, fromCartId: string) {
  const [from, target] = await Promise.all([
    prisma.cart.findUnique({ where: { id: fromCartId }, include: { items: true } }),
    prisma.cart.findUnique({ where: { id: targetCartId }, select: { currency: true } }),
  ]);
  if (!from) return;

  for (const it of from.items as any[]) {
    const existing = await prisma.cartItem.findFirst({
      where: { cartId: targetCartId, variantId: it.variantId },
    });
    if (existing) {
      await prisma.cartItem.update({
        where: { id: existing.id },
        data: { quantity: existing.quantity + it.quantity },
      });
    } else {
      await prisma.cartItem.create({
        data: {
          cartId: targetCartId,
          variantId: it.variantId,
          quantity: it.quantity,
          priceCentsAtAdd: it.priceCentsAtAdd ?? it.priceCents ?? 0,
          priceCents: it.priceCents ?? it.priceCentsAtAdd ?? 0,
          sku: it.sku,
          title: it.title,
          currency: it.currency ?? target?.currency ?? 'EUR', // ✅ keep currency
        },
      });
    }
  }
}

export async function computeTotals(cart: NonNullable<CartWithItems>) {
  let subtotal = 0;
  for (const it of cart.items as any[]) {
    const unit =
      cents(it.priceCents) ||
      cents(it.variant?.priceCents) ||
      cents(it.priceCentsAtAdd);
    subtotal += unit * it.quantity;
  }

  let discount = 0;
  if (cart.coupon) {
    const c: any = cart.coupon;
    const value = Number(c.value ?? c.amount ?? c.percent ?? 0);
    const type = c.type ?? c.kind ?? (c.percent ? 'PERCENT' : 'FIXED');
    if (type === 'PERCENT') discount = Math.floor((subtotal * value) / 100);
    else discount = Math.min(subtotal, cents(value));
  }

  const shipping = 0;
  const tax = 0;
  const total = Math.max(0, subtotal - discount + shipping + tax);

  return { currency: cart.currency, subtotal, discount, shipping, tax, total };
}

export async function ensureAvailability(variantId: string, needQty: number) {
  const v = await prisma.productVariant.findUnique({
    where: { id: variantId },
    include: { stockLevels: true },
  });
  if (!v) return { ok: false as const, reason: 'Variant not found' };

  const available = v.stockLevels.reduce((acc, s) => acc + (s.onHand - s.reserved), 0);
  if (v.trackInventory && needQty > available) {
    return { ok: false as const, reason: `Insufficient stock: need ${needQty}, available ${available}` };
  }
  return { ok: true as const, variant: v, available };
}

export async function reserveStock(variantId: string, qtyDelta: number) {
  if (qtyDelta === 0) return;
  const wh = await getDefaultWarehouseId();
  await prisma.$transaction(async (tx) => {
    const level = await tx.stockLevel.upsert({
      where: { variantId_warehouseId: { variantId, warehouseId: wh } },
      update: {},
      create: { variantId, warehouseId: wh, onHand: 0, reserved: 0 },
    });
    const newReserved = Math.max(0, level.reserved + qtyDelta);
    await tx.stockLevel.update({
      where: { variantId_warehouseId: { variantId, warehouseId: wh } },
      data: { reserved: newReserved },
    });
    await tx.stockMovement.create({
      data: {
        variantId,
        warehouseId: wh,
        type: 'ADJUSTMENT',
        delta: qtyDelta,
        reason: qtyDelta >= 0 ? 'cart_reserve' : 'cart_release',
      },
    });
  });
}
