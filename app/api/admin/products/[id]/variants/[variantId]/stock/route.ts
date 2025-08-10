import { prisma } from '@/lib/prisma';
import { ok, badRequest, notFound, serverError } from '@/lib/http';
import { requireAdminUser } from '@/lib/admin-guard';
import { z } from 'zod';
import { getDefaultWarehouseId } from '@/lib/warehouse';

export const runtime = 'nodejs';

const bodySchema = z.object({
  warehouseId: z.string().uuid().optional(), // default warehouse if omitted
  setOnHand: z.number().int().optional(),
  deltaOnHand: z.number().int().optional(),
  reason: z.string().max(200).optional(),
});

export async function POST(req: Request, ctx: { params: Promise<{ variantId: string }> }) {
  const { user, error } = await requireAdminUser();
  if (error) return error;

  const { variantId } = await ctx.params;
  const payload = await req.json().catch(() => null);
  const parsed = bodySchema.safeParse(payload);
  if (!parsed.success) return badRequest('Invalid payload', parsed.error.format());

  const variant = await prisma.productVariant.findUnique({ where: { id: variantId } });
  if (!variant) return notFound('Variant not found');

  const whId = parsed.data.warehouseId ?? (await getDefaultWarehouseId());

  try {
    const level = await prisma.stockLevel.upsert({
      where: { variantId_warehouseId: { variantId, warehouseId: whId } },
      update: {},
      create: { variantId, warehouseId: whId },
    });

    let newOnHand = level.onHand;
    if (typeof parsed.data.setOnHand === 'number') {
      const delta = parsed.data.setOnHand - level.onHand;
      newOnHand = parsed.data.setOnHand;
      if (delta !== 0) {
        await prisma.stockMovement.create({
          data: { variantId, warehouseId: whId, type: 'ADJUSTMENT', delta, reason: parsed.data.reason ?? 'setOnHand' },
        });
      }
    } else if (typeof parsed.data.deltaOnHand === 'number' && parsed.data.deltaOnHand !== 0) {
      newOnHand = level.onHand + parsed.data.deltaOnHand;
      await prisma.stockMovement.create({
        data: { variantId, warehouseId: whId, type: 'ADJUSTMENT', delta: parsed.data.deltaOnHand, reason: parsed.data.reason ?? 'deltaOnHand' },
      });
    }

    const updated = await prisma.stockLevel.update({
      where: { variantId_warehouseId: { variantId, warehouseId: whId } },
      data: { onHand: newOnHand },
    });

    return ok(updated);
  } catch (e: any) {
    return serverError('Failed to update stock', e);
  }
}
